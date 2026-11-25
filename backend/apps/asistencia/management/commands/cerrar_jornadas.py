"""
Cierra sola la jornada de quien cerró la plataforma (5 minutos sin señal de ningún dispositivo).
La salida queda a la hora de la última señal y se detiene el cronómetro de la tarea.

Programar cada minuto:
    python manage.py cerrar_jornadas
"""
from django.core.management.base import BaseCommand

from apps.asistencia.servicios import cerrar_jornadas_sin_senal


class Command(BaseCommand):
    help = 'Cierra las jornadas de quienes cerraron la plataforma.'

    def handle(self, *args, **opciones):
        n = cerrar_jornadas_sin_senal()
        if n:
            self.stdout.write(f'Jornadas cerradas: {n}')
