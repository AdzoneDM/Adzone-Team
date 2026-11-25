"""Avisa los recordatorios personales que ya llegaron a su hora (cron: cada minuto).

    python manage.py revisar_recordatorios
"""
from django.core.management.base import BaseCommand

from apps.desempeno.servicios_recordatorios import avisar_recordatorios, limpiar_hechos


class Command(BaseCommand):
    help = "Avisa los recordatorios que llegaron a su hora y limpia los hechos hace mucho."

    def handle(self, *args, **options):
        avisados = avisar_recordatorios()
        if avisados:
            self.stdout.write(f'Recordatorios avisados: {avisados}.')
        limpiar_hechos()
