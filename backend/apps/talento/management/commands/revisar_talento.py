from django.core.management.base import BaseCommand

from apps.talento.politicas import revisar


class Command(BaseCommand):
    help = "Diario: avisa de documentos por vencer y recuerda (una vez por semana) las políticas pendientes de aceptar."

    def handle(self, *args, **o):
        self.stdout.write(f'{revisar()} aviso(s) enviados.')
