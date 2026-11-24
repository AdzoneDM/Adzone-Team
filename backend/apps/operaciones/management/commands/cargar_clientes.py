"""Carga el catálogo inicial de clientes sin duplicar ni tocar los que ya existen.

    python manage.py cargar_clientes            # solo muestra el plan (no cambia nada)
    python manage.py cargar_clientes --aplicar  # crea únicamente los que faltan

Compara por nombre sin importar mayúsculas, acentos, espacios ni signos («Dulcería  Rodríguez» = «dulceria rodriguez»). Si un nombre se parece a un
cliente existente sin ser igual (uno contiene al otro), NO se crea: se informa para decidir a mano (o se pasa con --distintos «Nombre»).
Nunca borra, renombra ni cambia clientes existentes."""
import re
import unicodedata

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.operaciones.models import Cliente

# Nombre comercial aprobado → tipo. «AdZone» y «AdZone TV» son las marcas propias de ADZONE (clientes internos: sus órdenes no cuentan como ingreso).
CATALOGO = [
    ('Falcondo', 'EMPRESA'), ('Destreza', 'EMPRESA'), ('Coopdemón', 'EMPRESA'), ('AdZone TV', 'INTERNO'), ('Solymar', 'EMPRESA'),
    ('Merengue', 'EMPRESA'), ('Tavares', 'EMPRESA'), ('Cenllabo', 'EMPRESA'), ('Electro Centro Bonao', 'EMPRESA'),
    ('Dulcería Rodríguez', 'EMPRESA'), ('Cabinsa', 'EMPRESA'), ('Centro Médico Carolina de Jesús', 'EMPRESA'),
    ('Huellitas', 'EMPRESA'), ('AdZone', 'INTERNO'), ('Plaza Merengue', 'EMPRESA'),
]


def clave(texto):
    """«Dulcería  Rodríguez» → «dulceriarodriguez»: sin acentos, mayúsculas, espacios ni signos."""
    sin = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', sin.lower())


def planificar(catalogo=CATALOGO, distintos=()):
    """Devuelve (existen, nuevos, dudosos): existen = [(nombre, cliente)], nuevos = [(nombre, tipo)], dudosos = [(nombre, parecidos)]."""
    existentes = [(c, clave(c.nombre)) for c in Cliente.objects.all()]
    permitidos = {clave(d) for d in distintos}
    existen, nuevos, dudosos, vistos = [], [], [], set()
    for nombre, tipo in catalogo:
        k = clave(nombre)
        if k in vistos:
            continue
        vistos.add(k)
        igual = next((c for c, ck in existentes if ck == k), None)
        if igual:
            existen.append((nombre, igual))
            continue
        parecidos = [c for c, ck in existentes if len(ck) >= 4 and len(k) >= 4 and (ck in k or k in ck)]
        if parecidos and k not in permitidos:
            dudosos.append((nombre, parecidos))
            continue
        nuevos.append((nombre, tipo))
    return existen, nuevos, dudosos


class Command(BaseCommand):
    help = "Carga el catálogo de clientes sin duplicar (por defecto solo muestra el plan)."

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help='Crea los clientes que faltan (sin esto solo se muestra el plan).')
        parser.add_argument('--distintos', nargs='*', default=[], help='Nombres que, aunque se parezcan a un cliente existente, son clientes distintos.')

    def handle(self, *args, **opciones):
        existen, nuevos, dudosos = planificar(distintos=opciones['distintos'])
        self.stdout.write(f'Clientes ya en el catálogo: {Cliente.objects.count()}')
        self.stdout.write(f'\nYa existen ({len(existen)}) — no se tocan:')
        for nombre, c in existen:
            self.stdout.write(f'  = {nombre}  →  id {c.id} «{c.nombre}»')
        self.stdout.write(f'\nPosibles variantes de un cliente existente ({len(dudosos)}) — NO se crean, hay que decidir:')
        for nombre, parecidos in dudosos:
            self.stdout.write(f'  ? {nombre}  ~  ' + ', '.join(f'id {c.id} «{c.nombre}»' for c in parecidos))
        self.stdout.write(f'\nFaltan y se crearán ({len(nuevos)}):')
        for nombre, tipo in nuevos:
            self.stdout.write(f'  + {nombre}  ({tipo})')
        if not opciones['aplicar']:
            self.stdout.write(self.style.WARNING('\nSolo era el plan: no se cambió nada. Para crearlos: --aplicar'))
            return
        with transaction.atomic():
            for nombre, tipo in nuevos:
                if not Cliente.objects.filter(nombre__iexact=nombre).exists():  # última comprobación contra la base, dentro de la transacción
                    Cliente.objects.create(nombre=nombre, tipo=tipo)
        self.stdout.write(self.style.SUCCESS(f'\nListo: {len(nuevos)} cliente(s) creado(s). Clientes ahora: {Cliente.objects.count()}.'))
