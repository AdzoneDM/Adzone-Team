"""
Revisa las jornadas y avisa a los supervisores: tardanzas, entradas sin marcar y pausas que pasaron su límite.

Programar cada 10 minutos en horario laboral:
    python manage.py revisar_jornadas
"""
from django.core.management.base import BaseCommand

from apps.asistencia.servicios import revisar_asistencia


class Command(BaseCommand):
    help = 'Avisos de asistencia para los supervisores.'

    def handle(self, *args, **opciones):
        self.stdout.write(f'Avisos enviados: {revisar_asistencia()}')
