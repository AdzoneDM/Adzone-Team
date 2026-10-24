"""
Deja los 7 departamentos oficiales de Adzone con sus colores y ubica cada puesto en el suyo.

    python manage.py departamentos_oficiales            # muestra lo que haría, sin cambiar nada
    python manage.py departamentos_oficiales --aplicar  # lo hace

Es seguro repetirlo. Los departamentos viejos solo se borran si quedan sin puestos ni Empleados del Mes.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Departamento
from apps.organizacion.models import PuestoDeTrabajo

# nombre, color del texto, color de fondo, descripción
OFICIALES = [
    ('Gerencia', '#2f3a4f', '#eef1f6', 'Dirección general y coordinación de la empresa.'),
    ('Marketing', '#1d4189', '#e6edfa', 'Estrategia, creatividad, diseño y redes sociales.'),
    ('Audiovisual', '#56298f', '#f0e9fb', 'Producción, fotografía, video y edición.'),
    ('Adzone TV', '#a3170f', '#fde8e7', 'Canal, programación, medios y podcast.'),
    ('Impresión', '#8a4300', '#fdeedd', 'Impresión digital, rotulación, instalación y eventos.'),
    ('Administración', '#7a5000', '#fff4d6', 'Finanzas, contabilidad y tesorería.'),
    ('Tecnología', '#0d6455', '#e2f4f1', 'Desarrollo, innovación y ciberseguridad.'),
]

# Puesto → departamento. Lo que no está aquí se decide por el departamento anterior.
POR_PUESTO = {
    'CEO / Director General': 'Gerencia',
    'Gerente de Marketing y Audiovisuales': 'Marketing',
    'Encargado de Creatividad': 'Marketing',
    'Community Manager': 'Marketing',
    'Diseñador Gráfico Junior': 'Marketing',
    'Diseñador Gráfico Senior': 'Marketing',
    'Editor Audiovisual': 'Audiovisual',
    'Encargado de Producción Audiovisual': 'Audiovisual',
    'Especialista en Fotografía y Video': 'Audiovisual',
    'Editor / Animador 3D VFX': 'Audiovisual',
    'Coordinador de Medios': 'Adzone TV',
    'Coordinador de Estudio de Contenido y Podcast': 'Adzone TV',
}

# Departamento anterior (o parte de su nombre) → departamento oficial.
POR_DEPARTAMENTO = [
    ('Dirección', 'Gerencia'),
    ('Tecnolog', 'Tecnología'),
    ('Eventos', 'Impresión'),
    ('Impresi', 'Impresión'),
    ('Financ', 'Administración'),
    ('Administra', 'Administración'),
    ('Audiovisual', 'Audiovisual'),
    ('Marketing', 'Marketing'),
    ('TV', 'Adzone TV'),
]


def destino(puesto):
    if puesto.nombre in POR_PUESTO:
        return POR_PUESTO[puesto.nombre]
    anterior = puesto.departamento.nombre if puesto.departamento_id else ''
    for parte, oficial in POR_DEPARTAMENTO:
        if parte.lower() in anterior.lower():
            return oficial
    return None


class Command(BaseCommand):
    help = 'Crea los 7 departamentos oficiales con sus colores y ubica los puestos.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help='Hacer los cambios (sin esto solo se muestran).')

    def handle(self, *args, aplicar=False, **opciones):
        with transaction.atomic():
            oficiales = {}
            for orden, (nombre, color, fondo, descripcion) in enumerate(OFICIALES):
                depto, creado = Departamento.objects.update_or_create(
                    nombre=nombre, defaults={'color': color, 'color_fondo': fondo, 'descripcion': descripcion, 'orden': orden})
                oficiales[nombre] = depto
                self.stdout.write(f"{'+ nuevo ' if creado else '  listo '} {nombre}")

            sin_ubicar = []
            for puesto in PuestoDeTrabajo.objects.select_related('departamento').order_by('nombre'):
                nuevo = destino(puesto)
                if nuevo is None:
                    sin_ubicar.append(puesto.nombre)
                    continue
                if puesto.departamento_id != oficiales[nuevo].pk:
                    self.stdout.write(f"  → {puesto.nombre}: {puesto.departamento} ⇒ {nuevo}")
                    puesto.departamento = oficiales[nuevo]
                    puesto.save(update_fields=['departamento'])

            for viejo in Departamento.objects.exclude(pk__in=[d.pk for d in oficiales.values()]):
                if PuestoDeTrabajo.objects.filter(departamento=viejo).exists():
                    self.stdout.write(self.style.WARNING(f"  Se queda (aún tiene puestos): {viejo.nombre}"))
                elif viejo.empleados_del_mes.exists():
                    # Borrarlo se llevaría los reconocimientos guardados: se deja para el historial.
                    self.stdout.write(self.style.WARNING(f"  Se queda (tiene Empleados del Mes guardados): {viejo.nombre}"))
                else:
                    self.stdout.write(f"  − se borra el departamento vacío «{viejo.nombre}»")
                    viejo.delete()

            for nombre in sin_ubicar:
                self.stdout.write(self.style.WARNING(f"  Sin ubicar, revísalo en Puestos: {nombre}"))

            if not aplicar:
                transaction.set_rollback(True)
                self.stdout.write(self.style.NOTICE('\nNo se cambió nada. Repite con --aplicar para hacerlo.'))
            else:
                self.stdout.write(self.style.SUCCESS('\nDepartamentos oficiales listos.'))
