from django.core.management.base import BaseCommand

from apps.asistencia.servicios import revisar_almuerzos


class Command(BaseCommand):
    help = "«Es tu hora de comer» justo a la hora (y minuto) que cada persona eligió, y «te quedan 5 minutos». Correr cada minuto."

    def handle(self, *args, **opciones):
        n = revisar_almuerzos()
        if n:
            self.stdout.write(f"{n} aviso(s) de almuerzo")
