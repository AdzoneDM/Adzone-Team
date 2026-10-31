"""
Crea o actualiza las cuentas del equipo desde un JSON privado (ver datos_iniciales/equipo.ejemplo.json).

    python manage.py cargar_equipo datos_privados/equipo.json            # muestra lo que haría
    python manage.py cargar_equipo datos_privados/equipo.json --aplicar  # lo hace

A cada cuenta nueva se le genera una contraseña inicial que se muestra una sola vez.
Las cuentas que ya existen conservan su contraseña.

Campos de cada persona: usuario, nombre, apellido, correo, puesto, administrador (sí/no), accesos (lista de roles,
p. ej. ["Gerente de Departamento", "Finanzas"]), salario_mensual, nomina, horas_semana, activo.
Con «activo»: false la cuenta se desactiva si existe y no se crea si no existe.
Si hay salario y no hay costo_hora, el costo por hora se calcula del salario (salario ÷ 23.83 ÷ 8).
Quien ocupa un puesto «Agente de Call Center…» recibe el acceso «Agente Call Center».
"""
from decimal import Decimal, InvalidOperation
import json
import secrets

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.organizacion.models import PerfilUsuario, PuestoDeTrabajo
from apps.organizacion.serializers import ROLES


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
                if p.get('activo') is False:
                    # Quien ya no está en el equipo: se desactiva su cuenta si existe; nunca se crea.
                    if user and user.is_active:
                        user.is_active = False
                        user.save(update_fields=['is_active'])
                        self.stdout.write(f"  − desactivada {usuario}")
                    continue
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
                accesos = list(p.get('accesos') or [])
                if p.get('administrador'):
                    accesos.append('Administrador')
                for rol in accesos:
                    if rol not in ROLES:
                        self.stdout.write(self.style.WARNING(f"  Acceso desconocido para {usuario}: {rol}"))
                        continue
                    user.groups.add(grupo_admin if rol == 'Administrador' else Group.objects.get_or_create(name=rol)[0])
                if 'Administrador' in accesos and not user.is_staff:
                    user.is_staff = True
                    user.save(update_fields=['is_staff'])
                puesto = puestos.get((p.get('puesto') or '').lower())
                if p.get('puesto') and puesto is None:
                    self.stdout.write(self.style.WARNING(f"  Puesto no encontrado para {usuario}: {p['puesto']}"))
                perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
                if puesto:
                    perfil.puesto_trabajo = puesto
                    if puesto.nombre.startswith('Agente de Call Center'):
                        user.groups.add(Group.objects.get_or_create(name='Agente Call Center')[0])
                if not user.groups.exists():
                    user.groups.add(Group.objects.get_or_create(name='Colaborador')[0])
                try:
                    if p.get('horas_semana'):
                        perfil.horas_semana = Decimal(str(p['horas_semana']))
                    if p.get('salario_mensual') is not None:
                        perfil.salario_mensual = Decimal(str(p['salario_mensual']))
                    if p.get('costo_hora') is not None:
                        perfil.costo_hora = Decimal(str(p['costo_hora']))
                    elif perfil.salario_mensual:
                        perfil.costo_hora = PerfilUsuario.costo_hora_de_salario(perfil.salario_mensual, perfil.horas_semana)
                except InvalidOperation:
                    self.stdout.write(self.style.WARNING(f"  Salario u horas no válidos para {usuario}: se dejan igual"))
                if 'nomina' in p:
                    perfil.nomina = p['nomina'] or ''
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
