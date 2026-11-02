"""
Revisa jornadas y actividad y avisa a los supervisores: tardanzas, entradas sin marcar, inactividad prolongada,
computadoras que no reportan y días con mucho tiempo improductivo.

Programar cada 10 minutos en horario laboral (Plesk → Tareas programadas):
    python manage.py revisar_jornadas
"""
from django.core.management.base import BaseCommand

from apps.monitoreo.servicios import revisar_alertas


class Command(BaseCommand):
    help = 'Avisos de asistencia y de actividad para los supervisores.'

    def handle(self, *args, **opciones):
        self.stdout.write(f'Avisos enviados: {revisar_alertas()}')
