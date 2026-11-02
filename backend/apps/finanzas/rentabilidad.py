"""
Rentabilidad real por OT, por cliente y por departamento.

Ingreso: lo facturado (sin ITBIS, emitidas o pagadas); si la OT aún no se factura, lo vendido (monto de la OT).
Costo: mano de obra (horas del cronómetro × costo por hora de cada persona) + materiales del almacén (vales despachados)
+ gastos registrados en la OT (materiales, equipos, freelance y pauta, transporte y otros). Todo en RD$: los montos en
dólares se convierten con la tasa del día (o la última anterior). Una hora nunca se cuenta dos veces.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Q, Sum

from .models import Factura, Gasto, TasaCambio, redondear

CERO = Decimal('0')
MARGEN_MINIMO = 30  # % por debajo del cual una OT o un cliente salen en alerta
GRUPO_GASTO = {'MATERIALES': 'materiales', 'EQUIPOS': 'equipos', 'PERSONAL': 'externos', 'PAUTA': 'externos',
               'TRANSPORTE': 'transporte'}  # el resto: «otros»


class Conversor:
    """Convierte a RD$ con la tasa vigente en cada fecha. Recuerda si faltó alguna tasa."""

    def __init__(self):
        self.tasas = list(TasaCambio.objects.order_by('fecha').values_list('fecha', 'usd_dop'))
        self.sin_tasa = 0

    def tasa(self, fecha):
        actual = None
        for f, t in self.tasas:
            if f > fecha:
                break
            actual = t
        return actual or (self.tasas[0][1] if self.tasas else None)

    def a_dop(self, monto, moneda, fecha):
        monto = monto or CERO
        if moneda != 'USD' or not monto:
            return monto
        t = self.tasa(fecha)
        if t is None:
            self.sin_tasa += 1
            return CERO  # sin tasa no se inventa: el monto queda fuera y se avisa
        return monto * t


def _f(v):
    return float(redondear(v)) if v is not None else None


def _vacio():
    return {'vendido': CERO, 'facturado': CERO, 'cobrado': CERO, 'mano_obra': CERO, 'materiales': CERO, 'equipos': CERO,
            'externos': CERO, 'transporte': CERO, 'otros': CERO, 'minutos': 0, 'minutos_sin_costo': 0, 'retrabajo': CERO}


def _calcular(ordenes, conv):
    """Suma por OT (toda su vida, no solo el período) cada concepto de ingreso y costo."""
    from apps.almacen.models import ValeMaterial
    from apps.operaciones.models import SolicitudCambio
    from apps.tiempo.models import RegistroTiempo
    ids = [o.pk for o in ordenes]
    datos = {o.pk: _vacio() for o in ordenes}
    for o in ordenes:
        moneda = o.cotizacion.moneda if o.cotizacion_id else 'DOP'
        datos[o.pk]['vendido'] = conv.a_dop(o.monto, moneda, (o.fecha_aprobacion or o.fecha_creacion).date())
    for f in Factura.objects.filter(orden_id__in=ids, estado__in=('EMITIDA', 'PAGADA')):
        d = datos[f.orden_id]
        d['facturado'] += conv.a_dop(f.subtotal, f.moneda, f.fecha)
        # lo cobrado se reparte en proporción del total sin ITBIS
        d['cobrado'] += conv.a_dop(f.pagado * (f.subtotal / f.total) if f.total else CERO, f.moneda, f.fecha)
    for g in Gasto.objects.filter(orden_id__in=ids):
        datos[g.orden_id][GRUPO_GASTO.get(g.categoria, 'otros')] += conv.a_dop(g.monto, g.moneda, g.fecha)
    for v in ValeMaterial.objects.filter(orden_id__in=ids, estado__in=('DESPACHADO', 'CERRADO')).prefetch_related('lineas'):
        datos[v.orden_id]['materiales'] += v.costo_total
    for r in RegistroTiempo.objects.filter(orden_id__in=ids, fin__isnull=False).select_related('usuario__perfil'):
        d = datos[r.orden_id]
        d['minutos'] += r.minutos
        costo = getattr(getattr(r.usuario, 'perfil', None), 'costo_hora', None)
        if costo:
            d['mano_obra'] += Decimal(r.minutos) / 60 * costo
        else:
            d['minutos_sin_costo'] += r.minutos
    for oid, total in SolicitudCambio.objects.filter(orden_id__in=ids).values_list('orden_id').annotate(t=Sum('costo_retrabajo')):
        datos[oid]['retrabajo'] = total or CERO
    return datos


def _fila(d):
    costo = d['mano_obra'] + d['materiales'] + d['equipos'] + d['externos'] + d['transporte'] + d['otros']
    ingreso = d['facturado'] if d['facturado'] else d['vendido']
    utilidad = ingreso - costo
    return {
        'vendido': _f(d['vendido']), 'facturado': _f(d['facturado']), 'cobrado': _f(d['cobrado']),
        'base': 'FACTURADO' if d['facturado'] else 'VENDIDO', 'ingreso': _f(ingreso),
        'mano_obra': _f(d['mano_obra']), 'materiales': _f(d['materiales']), 'equipos': _f(d['equipos']), 'externos': _f(d['externos']),
        'transporte': _f(d['transporte']), 'otros': _f(d['otros']), 'costo': _f(costo), 'utilidad': _f(utilidad),
        'margen': round(float(utilidad / ingreso * 100), 1) if ingreso else None,
        'horas': round(d['minutos'] / 60, 1), 'horas_sin_costo': round(d['minutos_sin_costo'] / 60, 1), 'retrabajo': _f(d['retrabajo']),
        'costo_hora_real': _f(costo / (Decimal(d['minutos']) / 60)) if d['minutos'] else None,
    }


def ordenes_del_periodo(desde, hasta):
    """OT con movimiento en el período: factura, gasto, horas, vale o entrega."""
    from apps.almacen.models import ValeMaterial
    from apps.operaciones.models import OrdenTrabajo
    from apps.tiempo.models import RegistroTiempo
    ids = set(Factura.objects.filter(fecha__range=(desde, hasta), orden__isnull=False).exclude(estado__in=('BORRADOR', 'ANULADA')).values_list('orden_id', flat=True))
    ids |= set(Gasto.objects.filter(fecha__range=(desde, hasta), orden__isnull=False).values_list('orden_id', flat=True))
    ids |= set(RegistroTiempo.objects.filter(inicio__date__range=(desde, hasta), orden__isnull=False).values_list('orden_id', flat=True))
    ids |= set(ValeMaterial.objects.filter(fecha__date__range=(desde, hasta)).values_list('orden_id', flat=True))
    ids |= set(OrdenTrabajo.objects.filter(fecha_entrega__range=(desde, hasta)).values_list('pk', flat=True))
    return list(OrdenTrabajo.objects.filter(pk__in=ids).exclude(estado='CANCELADA').select_related('cliente', 'departamento', 'cotizacion', 'proyecto'))


def _agrupar(filas, clave):
    grupos = defaultdict(lambda: {'ordenes': 0, **{k: 0.0 for k in ('ingreso', 'facturado', 'costo', 'mano_obra', 'materiales', 'utilidad', 'horas')}})
    nombres = {}
    for f in filas:
        k, nombre = clave(f)
        g = grupos[k]
        nombres[k] = nombre
        g['ordenes'] += 1
        for c in ('ingreso', 'facturado', 'costo', 'mano_obra', 'materiales', 'utilidad', 'horas'):
            g[c] += f[c] or 0
    salida = []
    for k, g in grupos.items():
        salida.append({'id': k, 'nombre': nombres[k], **{c: round(v, 2) for c, v in g.items()},
                       'margen': round(g['utilidad'] / g['ingreso'] * 100, 1) if g['ingreso'] else None})
    return sorted(salida, key=lambda x: -x['ingreso'])


def rentabilidad_ordenes(desde, hasta, margen_minimo=MARGEN_MINIMO):
    conv = Conversor()
    ordenes = ordenes_del_periodo(desde, hasta)
    datos = _calcular(ordenes, conv)
    filas = []
    for o in ordenes:
        f = _fila(datos[o.pk])
        f.update({'id': o.pk, 'numero': o.numero or o.solicitud, 'titulo': o.titulo, 'estado': o.get_estado_display(),
                  'cliente_id': o.cliente_id, 'cliente': o.cliente.nombre,
                  'departamento_id': o.departamento_id, 'departamento': o.departamento.nombre if o.departamento_id else 'Sin departamento',
                  'proyecto': f'{o.proyecto.codigo} · {o.proyecto.nombre}' if o.proyecto_id else None,
                  'cerrada': o.estado in ('ENTREGADA', 'CERRADA')})
        f['alerta'] = bool(f['ingreso'] and (f['utilidad'] < 0 or (f['margen'] is not None and f['margen'] < margen_minimo)))
        filas.append(f)
    filas.sort(key=lambda x: (x['margen'] if x['margen'] is not None else 999))
    clientes = _agrupar(filas, lambda f: (f['cliente_id'], f['cliente']))
    departamentos = _agrupar(filas, lambda f: (f['departamento_id'] or 0, f['departamento']))
    ingreso = sum(f['ingreso'] or 0 for f in filas)
    costo = sum(f['costo'] or 0 for f in filas)
    totales = {'ordenes': len(filas), 'ingreso': round(ingreso, 2), 'costo': round(costo, 2), 'utilidad': round(ingreso - costo, 2),
               'margen': round((ingreso - costo) / ingreso * 100, 1) if ingreso else None,
               'mano_obra': round(sum(f['mano_obra'] or 0 for f in filas), 2), 'materiales': round(sum(f['materiales'] or 0 for f in filas), 2),
               'retrabajo': round(sum(f['retrabajo'] or 0 for f in filas), 2), 'en_alerta': sum(1 for f in filas if f['alerta']),
               'horas_sin_costo': round(sum(f['horas_sin_costo'] for f in filas), 1)}
    return {'desde': desde, 'hasta': hasta, 'margen_minimo': margen_minimo, 'totales': totales, 'ordenes': filas,
            'clientes': clientes, 'departamentos': departamentos, 'montos_sin_tasa': conv.sin_tasa}


def detalle_orden(ot):
    """El desglose de una OT: personas y horas, vales, gastos y facturas."""
    from apps.almacen.models import ValeMaterial
    from apps.tiempo.models import RegistroTiempo
    conv = Conversor()
    fila = _fila(_calcular([ot], conv)[ot.pk])
    personas = defaultdict(lambda: {'minutos': 0, 'costo': CERO})
    for r in RegistroTiempo.objects.filter(orden=ot, fin__isnull=False).select_related('usuario__perfil'):
        p = personas[r.usuario]
        p['minutos'] += r.minutos
        ch = getattr(getattr(r.usuario, 'perfil', None), 'costo_hora', None)
        p['costo'] += Decimal(r.minutos) / 60 * ch if ch else CERO
    return {
        **fila, 'id': ot.pk, 'numero': ot.numero or ot.solicitud, 'titulo': ot.titulo, 'cliente': ot.cliente.nombre,
        'personas': sorted(({'nombre': u.get_full_name() or u.username, 'horas': round(v['minutos'] / 60, 1), 'costo': _f(v['costo'])}
                            for u, v in personas.items()), key=lambda x: -x['horas']),
        'vales': [{'numero': v.numero, 'estado': v.get_estado_display(), 'costo': _f(v.costo_total)}
                  for v in ValeMaterial.objects.filter(orden=ot, estado__in=('DESPACHADO', 'CERRADO')).prefetch_related('lineas')],
        'gastos': [{'fecha': g.fecha, 'concepto': g.concepto, 'categoria': g.get_categoria_display(), 'moneda': g.moneda,
                    'monto': _f(g.monto), 'en_dop': _f(conv.a_dop(g.monto, g.moneda, g.fecha))} for g in Gasto.objects.filter(orden=ot)],
        'facturas': [{'numero': f.numero, 'fecha': f.fecha, 'estado': f.get_estado_display(), 'moneda': f.moneda, 'subtotal': _f(f.subtotal),
                      'en_dop': _f(conv.a_dop(f.subtotal, f.moneda, f.fecha))} for f in Factura.objects.filter(orden=ot).exclude(estado='ANULADA')],
        'montos_sin_tasa': conv.sin_tasa,
    }


def costo_total_ordenes(ordenes):
    """Para el panel gerencial: costo total y vendido en RD$ de cada OT."""
    conv = Conversor()
    return {pk: _fila(d) for pk, d in _calcular(list(ordenes), conv).items()}


def convertir_existente(facturas, gastos):
    """Lo que usa la rentabilidad por proyecto/cliente de antes, ahora en RD$."""
    conv = Conversor()
    return ([(f, conv.a_dop(f.subtotal, f.moneda, f.fecha), conv.a_dop(f.pagado, f.moneda, f.fecha)) for f in facturas],
            [(g, conv.a_dop(g.monto, g.moneda, g.fecha)) for g in gastos], conv)
