from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.desempeno.servicios import avisar
from .models import Factura, Gasto, LineaFactura, Pago, redondear

CERO = Decimal('0')


def disparar(evento, objeto, quien=None):
    from apps.automatizaciones.motor import disparar as _d
    _d(evento, objeto, quien=quien)


def costo_horas(registros):
    """Horas × costo por hora de cada persona (si Finanzas lo cargó)."""
    total = CERO
    for r in registros:
        costo = getattr(getattr(r.usuario, 'perfil', None), 'costo_hora', None)
        if costo:
            total += Decimal(r.minutos) / 60 * costo
    return redondear(total)


def rentabilidad(facturas, gastos, registros):
    facturas = [f for f in facturas if f.estado in ('EMITIDA', 'PAGADA')]
    facturado = sum((f.subtotal for f in facturas), CERO)  # sin ITBIS: el impuesto no es ingreso
    cobrado = sum((f.pagado for f in facturas), CERO)
    gasto = sum((g.monto for g in gastos), CERO)
    registros = list(registros)
    horas = sum(r.minutos for r in registros) / 60
    costo = costo_horas(registros)
    margen = facturado - gasto - costo
    return {'facturado': redondear(facturado), 'cobrado': redondear(cobrado), 'gastos': redondear(gasto),
            'horas': round(horas, 1), 'costo_horas': costo, 'margen': redondear(margen),
            'margen_pct': round(float(margen / facturado * 100), 1) if facturado else None}


def rentabilidad_proyecto(proyecto):
    from apps.tiempo.models import RegistroTiempo
    datos = rentabilidad(proyecto.facturas.all(), proyecto.gastos.all(),
                         RegistroTiempo.objects.filter(proyecto=proyecto, fin__isnull=False).select_related('usuario__perfil'))
    datos['presupuesto'] = proyecto.presupuesto
    return datos


def antiguedad(hoy=None):
    """Cuentas por cobrar por días de atraso."""
    hoy = hoy or timezone.localdate()
    tramos = {'al_dia': CERO, '1_30': CERO, '31_60': CERO, '61_90': CERO, 'mas_90': CERO}
    for f in Factura.objects.filter(estado='EMITIDA'):
        saldo = f.saldo
        if saldo <= 0:
            continue
        dias = (hoy - f.vencimiento).days if f.vencimiento else 0
        clave = 'al_dia' if dias <= 0 else '1_30' if dias <= 30 else '31_60' if dias <= 60 else '61_90' if dias <= 90 else 'mas_90'
        tramos[clave] += saldo
    return {k: redondear(v) for k, v in tramos.items()}


@transaction.atomic
def factura_desde(origen, quien, lineas=None, **campos):
    """Crea una factura en borrador a partir de una cotización o de una orden."""
    from .models import Cotizacion
    if isinstance(origen, Cotizacion):
        factura = Factura.objects.create(cliente=origen.cliente, proyecto=origen.proyecto, titulo=origen.titulo,
                                         moneda=origen.moneda, cotizacion=origen, creada_por=quien, notas=origen.notas, **campos)
        for l in origen.lineas.all():
            LineaFactura.objects.create(documento=factura, descripcion=l.descripcion, cantidad=l.cantidad,
                                        precio=l.precio, aplica_itbis=l.aplica_itbis, orden=l.orden)
    else:  # OT Maestra
        anticipo = campos.pop('anticipo', False)
        monto_anticipo = campos.pop('monto_anticipo', None)
        titulo = f"{origen.codigo} · {origen.titulo}"
        factura = Factura.objects.create(cliente=origen.cliente, proyecto=origen.proyecto, orden=origen, es_anticipo=anticipo,
                                         cotizacion=origen.cotizacion, titulo=("Anticipo · " if anticipo else "") + titulo[:180],
                                         creada_por=quien, **campos)
        if anticipo:
            LineaFactura.objects.create(documento=factura, descripcion=f"Anticipo {origen.codigo}: {origen.titulo}"[:255],
                                        cantidad=1, precio=monto_anticipo or origen.anticipo_requerido or 0)
        else:
            previos = Factura.objects.filter(orden=origen, es_anticipo=True).exclude(estado__in=['ANULADA', 'BORRADOR'])
            ya = sum((f.subtotal for f in previos), Decimal('0'))
            if origen.cotizacion_id and not ya and origen.monto == origen.cotizacion.subtotal:
                for l in origen.cotizacion.lineas.all():
                    LineaFactura.objects.create(documento=factura, descripcion=l.descripcion, cantidad=l.cantidad,
                                                precio=l.precio, aplica_itbis=l.aplica_itbis, orden=l.orden)
            else:
                nota = f" (menos anticipo {', '.join(f.ncf or f.numero for f in previos)})" if ya else ''
                LineaFactura.objects.create(documento=factura, descripcion=f"{origen.titulo}{nota}"[:255], cantidad=1,
                                            precio=max(Decimal('0'), (origen.monto or Decimal('0')) - ya))
    factura.recalcular()
    return factura


def emitir(factura, quien, dias_credito=30):
    factura.estado = 'EMITIDA'
    factura.vencimiento = factura.vencimiento or factura.fecha + timedelta(days=dias_credito)
    factura.save(update_fields=['estado', 'vencimiento'])
    factura.actualizar_pagos()
    disparar('FACTURA_EMITIDA', factura, quien)


def registrar_pago(factura, quien, monto, **datos):
    pago = Pago.objects.create(factura=factura, monto=monto, registrado_por=quien, **datos)
    factura.actualizar_pagos()
    disparar('PAGO_RECIBIDO', pago, quien)
    if factura.orden_id:
        from apps.operaciones.servicios_ot import revisar_anticipo
        revisar_anticipo(factura.orden)
    if factura.orden and factura.orden.solicitada_por:
        avisar([factura.orden.solicitada_por], 'FINANZAS', f"Pago recibido: {factura.numero}",
               f"{factura.cliente} pagó {pago.monto:,.2f}. Saldo: {factura.saldo:,.2f}.", enlace=f"/ordenes/{factura.orden_id}",
               excepto=quien)
    return pago


def gastos_de(proyecto=None, orden=None):
    qs = Gasto.objects.all()
    if proyecto:
        qs = qs.filter(proyecto=proyecto)
    if orden:
        qs = qs.filter(orden=orden)
    return qs
