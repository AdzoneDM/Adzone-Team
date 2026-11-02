"""
Crea las reglas de productividad iniciales que falten (las de cada departamento necesitan que existan los
departamentos: corre antes `departamentos_oficiales --aplicar`). No cambia las reglas existentes.
    python manage.py reglas_productividad
"""
from django.core.management.base import BaseCommand

from apps.core.models import Departamento
from apps.monitoreo.models import ReglaProductividad
from apps.monitoreo.reglas_iniciales import sembrar


class Command(BaseCommand):
    help = 'Crea las reglas de productividad iniciales que falten.'

    def handle(self, *args, **opciones):
        self.stdout.write(f'Reglas creadas: {sembrar(ReglaProductividad, Departamento)}')
