from django.core.management.base import BaseCommand

from apps.activos.servicios import revisar


class Command(BaseCommand):
    help = "Diario: avisa de mantenimientos vencidos o en los próximos 7 días."

    def handle(self, *args, **o):
        self.stdout.write(f'{revisar()} aviso(s) enviados.')
