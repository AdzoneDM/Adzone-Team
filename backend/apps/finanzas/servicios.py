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
    from .rentabilidad import Conversor
    conv = Conversor()  # todo en RD$: lo que está en dólares se convierte con la tasa de su fecha
    facturas = [f for f in facturas if f.estado in ('EMITIDA', 'PAGADA')]
    facturado = sum((conv.a_dop(f.subtotal, f.moneda, f.fecha) for f in facturas), CERO)  # sin ITBIS: el impuesto no es ingreso
    cobrado = sum((conv.a_dop(f.pagado, f.moneda, f.fecha) for f in facturas), CERO)
    gasto = sum((conv.a_dop(g.monto, g.moneda, g.fecha) for g in gastos), CERO)
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
    de_donde = f"la cotización {origen.numero}" if isinstance(origen, Cotizacion) else f"la orden {origen.codigo}"
    historial(factura, quien, 'CREADA', f"{'Anticipo generado' if factura.es_anticipo else 'Generada'} desde {de_donde}")
    return factura


def historial(factura, quien, accion, detalle=''):
    """Una línea en el historial de la factura (quién, qué y cuándo)."""
    from .models import HistorialFactura
    return HistorialFactura.objects.create(factura=factura, usuario=quien if getattr(quien, 'pk', None) else None, accion=accion, detalle=str(detalle)[:2000])


def _fecha(d):
    return d.strftime('%d/%m/%Y') if d else 'sin definir'


def instantanea(f):
    """Cómo está la factura ahora, en texto legible, para poder decir después qué cambió («antes → después»)."""
    return {
        'Título': f.titulo or 'sin título', 'Cliente': str(f.cliente), 'Proyecto': str(f.proyecto) if f.proyecto_id else 'ninguno',
        'Fecha': _fecha(f.fecha), 'Vencimiento': _fecha(f.vencimiento), 'Moneda': f.moneda, 'NCF': f.ncf or 'sin NCF',
        'Notas': f.notas or '', 'Líneas': [(l.descripcion, str(l.cantidad), str(l.precio), l.aplica_itbis) for l in f.lineas.all()],
        'Total': f"{f.total:,.2f}",
    }


def detalle_de_cambios(antes, despues):
    """Una línea por cada dato que cambió. Las notas y las líneas solo dicen que cambiaron (las líneas, con el total nuevo)."""
    lineas = []
    for campo, valor in despues.items():
        previo = antes.get(campo)
        if previo == valor or campo == 'Total':
            continue
        if campo == 'Notas':
            lineas.append("Notas: actualizadas")
        elif campo == 'Líneas':
            lineas.append(f"Líneas: actualizadas (total {antes['Total']} → {despues['Total']})")
        else:
            lineas.append(f"{campo}: {previo} → {valor}")
    return '\n'.join(lineas)


def emitir(factura, quien, dias_credito=30):
    factura.estado = 'EMITIDA'
    factura.vencimiento = factura.vencimiento or factura.fecha + timedelta(days=dias_credito)
    factura.save(update_fields=['estado', 'vencimiento'])
    factura.actualizar_pagos()
    historial(factura, quien, 'EMITIDA', f"Vence: {_fecha(factura.vencimiento)}")
    disparar('FACTURA_EMITIDA', factura, quien)


def registrar_pago(factura, quien, monto, **datos):
    estado_antes = factura.estado
    pago = Pago.objects.create(factura=factura, monto=monto, registrado_por=quien, **datos)
    factura.actualizar_pagos()
    historial(factura, quien, 'PAGO', f"{pago.monto:,.2f} {factura.moneda} · {pago.get_metodo_display()}" + (f" · ref. {pago.referencia}" if pago.referencia else '') + f" · saldo {factura.saldo:,.2f}")
    if factura.estado != estado_antes:
        historial(factura, quien, 'ESTADO', f"Estado: {dict(Factura.ESTADOS)[estado_antes]} → {factura.get_estado_display()}")
    disparar('PAGO_RECIBIDO', pago, quien)
    if factura.orden_id:
        from apps.operaciones.servicios_ot import revisar_anticipo
        revisar_anticipo(factura.orden)
    if factura.orden and factura.orden.solicitada_por:
        avisar([factura.orden.solicitada_por], 'FINANZAS', f"Pago recibido: {factura.numero}",
               f"{factura.cliente} pagó {pago.monto:,.2f}. Saldo: {factura.saldo:,.2f}.", enlace=f"/ordenes/{factura.orden_id}",
               excepto=quien)
    return pago


# Días respecto al vencimiento en los que se recuerda el cobro (negativo = días de atraso): 3 antes, el mismo día, y 1, 7, 15 y 30 de atraso.
HITOS_VENCIMIENTO = (3, 0, -1, -7, -15, -30)


def _texto_hito(dias):
    if dias > 0:
        return f"vence en {dias} días"
    if dias == 0:
        return "vence hoy"
    return "venció ayer" if dias == -1 else f"lleva {-dias} días vencida"


def avisar_vencimientos(hoy=None):
    """Recordatorio para Finanzas de las facturas por cobrar que se acercan a vencer o ya vencieron (para el cron diario).
    Solo en los hitos de HITOS_VENCIMIENTO y una vez por hito: si el cron corre dos veces el mismo día no repite el aviso. Devuelve cuántos avisos creó."""
    from django.contrib.auth.models import User
    from apps.desempeno.models import Notificacion
    from apps.operaciones.permisos import es_finanzas
    hoy = hoy or timezone.localdate()
    facturas = [f for f in Factura.objects.filter(estado='EMITIDA', vencimiento__isnull=False).select_related('cliente')
                if f.saldo > 0 and (f.vencimiento - hoy).days in HITOS_VENCIMIENTO]
    if not facturas:
        return 0
    destinatarios = [u for u in User.objects.filter(is_active=True) if es_finanzas(u)]
    creados = 0
    for f in facturas:
        dias = (f.vencimiento - hoy).days
        titulo = f"{f.numero}: {_texto_hito(dias)}"
        mensaje = f"{f.cliente.nombre} · saldo {f.saldo:,.2f} {f.moneda} · vence el {f.vencimiento:%d/%m/%Y}"
        ya = set(Notificacion.objects.filter(tipo='FINANZAS', titulo=titulo, destinatario__in=destinatarios).values_list('destinatario_id', flat=True))
        nuevos = [u for u in destinatarios if u.pk not in ya]
        if nuevos:
            avisar(nuevos, 'FINANZAS', titulo, mensaje, enlace=f"/finanzas?ver=facturas&id={f.pk}")
            creados += len(nuevos)
    return creados


def gastos_de(proyecto=None, orden=None):
    qs = Gasto.objects.all()
    if proyecto:
        qs = qs.filter(proyecto=proyecto)
    if orden:
        qs = qs.filter(orden=orden)
    return qs
