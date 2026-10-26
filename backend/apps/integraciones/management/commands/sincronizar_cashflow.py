"""Trae de Cashflow el estado, el NCF y los pagos de las facturas abiertas (y confirma anticipos de OT).

    python manage.py sincronizar_cashflow            # sincroniza
    python manage.py sincronizar_cashflow --probar   # solo prueba la conexión
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.integraciones.cashflow import servicios
from apps.integraciones.cashflow.cliente import CashflowError


class Command(BaseCommand):
    help = "Sincroniza facturas y pagos con Cashflow."

    def add_arguments(self, parser):
        parser.add_argument('--probar', action='store_true', help="Solo prueba la conexión.")

    def handle(self, *args, **options):
        self.stdout.write(f"Modo: {settings.CASHFLOW_MODO} · {settings.CASHFLOW_API_URL}")
        try:
            if options['probar']:
                self.stdout.write(self.style.SUCCESS(f"Conectado: {servicios.probar()}"))
                return
            r = servicios.sincronizar_pendientes()
        except CashflowError as e:
            raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS(f"Facturas revisadas: {r['facturas']}. Pagos nuevos: {r['pagos']}. Errores: {r['errores']}."))
