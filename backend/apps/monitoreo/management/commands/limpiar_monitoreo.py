"""
Borra la actividad y las capturas más viejas que la retención (90 y 30 días por defecto). Programar una vez al día:
    python manage.py limpiar_monitoreo
"""
from django.core.management.base import BaseCommand

from apps.monitoreo.servicios import limpiar


class Command(BaseCommand):
    help = 'Aplica la retención de datos del monitoreo.'

    def handle(self, *args, **opciones):
        minutos, capturas = limpiar()
        self.stdout.write(f'Borrados: {minutos} minutos de actividad y {capturas} capturas.')
