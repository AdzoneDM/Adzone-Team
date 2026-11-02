from django.core.management.base import BaseCommand

from apps.monitoreo.comportamiento import reaplicar


class Command(BaseCommand):
    help = "Recalcula las incidencias de las reglas de comportamiento sobre la actividad de los últimos días."

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=30)

    def handle(self, *args, **o):
        n, borradas = reaplicar(o['dias'])
        self.stdout.write(f'{n} incidencias calculadas, {borradas} que ya no aplican borradas.')
