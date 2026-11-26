"""Análisis diario con alertas (y lectura con IA si está configurada) para Dirección y quien gestiona un área."""
from django.core.management.base import BaseCommand

from apps.asistente.alertas import analisis_diario


class Command(BaseCommand):
    help = 'Genera el análisis diario de cada responsable.'

    def handle(self, *args, **opciones):
        self.stdout.write(f'Informes generados: {analisis_diario()}')
