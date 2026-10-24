"""
Crea o actualiza las cuentas del equipo desde un JSON privado (ver datos_iniciales/equipo.ejemplo.json).

    python manage.py cargar_equipo datos_privados/equipo.json            # muestra lo que haría
    python manage.py cargar_equipo datos_privados/equipo.json --aplicar  # lo hace

A cada cuenta nueva se le genera una contraseña inicial que se muestra una sola vez.
Las cuentas que ya existen conservan su contraseña.
"""
import json
import secrets

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.organizacion.models import PerfilUsuario, PuestoDeTrabajo


def clave_inicial():
    return 'Adz-' + secrets.token_urlsafe(9)


class Command(BaseCommand):
    help = 'Crea o actualiza las cuentas del equipo desde un archivo JSON privado.'

    def add_arguments(self, parser):
        parser.add_argument('archivo')
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, archivo, aplicar=False, **opciones):
        try:
            with open(archivo, encoding='utf-8') as f:
                personas = json.load(f).get('personas', [])
        except (OSError, ValueError) as e:
            raise CommandError(f'No se pudo leer {archivo}: {e}')

        puestos = {p.nombre.lower(): p for p in PuestoDeTrabajo.objects.all()}
        grupo_admin, _ = Group.objects.get_or_create(name='Administrador')
        claves = []
        with transaction.atomic():
            for p in personas:
                usuario = (p.get('usuario') or '').strip().lower()
                if not usuario:
                    self.stdout.write(self.style.WARNING(f'  Sin «usuario», se salta: {p}'))
                    continue
                user = User.objects.filter(username=usuario).first()
                nuevo = user is None
                if nuevo:
                    user = User(username=usuario)
                    clave = clave_inicial()
                    user.set_password(clave)
                    claves.append((usuario, clave))
                user.first_name = p.get('nombre', user.first_name)
                user.last_name = p.get('apellido', user.last_name)
                user.email = p.get('correo', user.email)
                user.is_active = p.get('activo', True)
                user.save()
                if p.get('administrador'):
                    user.groups.add(grupo_admin)
                puesto = puestos.get((p.get('puesto') or '').lower())
                if p.get('puesto') and puesto is None:
                    self.stdout.write(self.style.WARNING(f"  Puesto no encontrado para {usuario}: {p['puesto']}"))
                perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
                if puesto:
                    perfil.puesto_trabajo = puesto
                    perfil.save()
                self.stdout.write(f"{'+ nueva ' if nuevo else '  actualizada '} {usuario} · {puesto.nombre if puesto else 'sin puesto'}")

            if not aplicar:
                transaction.set_rollback(True)
                self.stdout.write(self.style.NOTICE('\nNo se cambió nada. Repite con --aplicar para hacerlo.'))
                return
        if claves:
            self.stdout.write(self.style.SUCCESS('\nContraseñas iniciales (entrégalas en persona; cada quien la cambia en «Mi cuenta»):'))
            for usuario, clave in claves:
                self.stdout.write(f'  {usuario}: {clave}')
