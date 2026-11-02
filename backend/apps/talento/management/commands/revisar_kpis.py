"""
Avisa a cada supervisor de los KPIs de su gente que quedaron por debajo de su umbral el mes anterior.
Programar los días 1 a 5 de cada mes (se puede repetir: no duplica avisos):
    python manage.py revisar_kpis
    python manage.py revisar_kpis --mes 2026-10
"""
from datetime import datetime

from django.core.management.base import BaseCommand

from apps.talento.servicios import revisar_kpis


class Command(BaseCommand):
    help = 'Avisos de KPIs por debajo de su umbral.'

    def add_arguments(self, parser):
        parser.add_argument('--mes', help='AAAA-MM (por defecto, el mes anterior)')

    def handle(self, *args, mes=None, **opciones):
        periodo = datetime.strptime(mes, '%Y-%m').date() if mes else None
        self.stdout.write(f'Avisos enviados: {revisar_kpis(periodo)}')
