"""Tarea programada diaria (cron de Plesk): crea las tareas recurrentes y avisa lo que vence mañana.

    python manage.py tareas_diarias
"""
from django.core.management.base import BaseCommand

from apps.desempeno.servicios import avisar_por_vencer, generar_recurrentes


class Command(BaseCommand):
    help = "Genera las tareas recurrentes de la próxima semana y avisa las tareas que vencen mañana."

    def handle(self, *args, **options):
        creadas = generar_recurrentes()
        avisos = avisar_por_vencer()
        self.stdout.write(self.style.SUCCESS(f"Tareas recurrentes creadas: {creadas}. Avisos de vencimiento: {avisos}."))
