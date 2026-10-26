"""Lo que la plataforma hace con Cashflow. Cada llamada queda en la bitácora (SincronizacionCashflow)."""
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.integraciones.models import SincronizacionCashflow
from . import mapeo
from .cliente import CashflowError, conexion

METODOS = {'TRANSFERENCIA', 'EFECTIVO', 'CHEQUE', 'TARJETA'}


def _anotar(operacion, objeto, exito, detalle, usuario=None):
    SincronizacionCashflow.objects.create(operacion=operacion, objeto=objeto, exito=exito, detalle=str(detalle)[:2000],
                                          usuario=usuario, modo=settings.CASHFLOW_MODO)


def _llamar(operacion, objeto, usuario=None, **kw):
    try:
        r = conexion().llamar(operacion, **kw)
    except CashflowError as e:
        _anotar(operacion, objeto, False, e, usuario)
        raise
    _anotar(operacion, objeto, True, 'OK', usuario)
    return r


def estado():
    ultimo = SincronizacionCashflow.objects.first()
    errores = SincronizacionCashflow.objects.filter(exito=False, fecha__date=timezone.localdate()).count()
    return {'modo': settings.CASHFLOW_MODO, 'url': settings.CASHFLOW_API_URL, 'clave_configurada': bool(settings.CASHFLOW_API_KEY),
            'ultima_llamada': ultimo.fecha if ultimo else None, 'errores_hoy': errores}


def probar(usuario=None):
    r = _llamar('probar', 'conexion', usuario)
    datos = r.get('data', r) if isinstance(r, dict) else {}
    return datos.get('name') or datos.get('business_name') or 'Conexión correcta'


def sincronizar_cliente(cliente, usuario=None):
    """Vincula el cliente con Cashflow: lo busca por RNC y, si no existe, lo crea."""
    if cliente.cashflow_id:
        return cliente.cashflow_id
    rnc = (cliente.rnc or '').replace('-', '')
    if rnc:
        encontrados = mapeo.leer_clientes(_llamar('buscar_cliente', f"cliente:{cliente.pk}", usuario,
                                                  params={'search': rnc}))
        coincide = next((c for c in encontrados if c['rnc'] == rnc), None)
        if coincide:
            cliente.cashflow_id = coincide['id']
            cliente.save(update_fields=['cashflow_id'])
            return cliente.cashflow_id
    r = _llamar('crear_cliente', f"cliente:{cliente.pk}", usuario, cuerpo=mapeo.cliente(cliente))
    cliente.cashflow_id = mapeo.leer_id(r)
    if not cliente.cashflow_id:
        raise CashflowError("Cashflow no devolvió el id del cliente.")
    cliente.save(update_fields=['cashflow_id'])
    return cliente.cashflow_id


def enviar_cotizacion(cot, usuario=None):
    sincronizar_cliente(cot.cliente, usuario)
    doc = mapeo.leer_documento(_llamar('crear_cotizacion', f"cotizacion:{cot.pk}", usuario, cuerpo=mapeo.cotizacion(cot)))
    cot.cashflow_id, cot.cashflow_numero, cot.cashflow_estado = doc['id'], doc['numero'], doc['estado']
    cot.cashflow_sincronizado = timezone.now()
    cot.save(update_fields=['cashflow_id', 'cashflow_numero', 'cashflow_estado', 'cashflow_sincronizado'])
    return cot


@transaction.atomic
def emitir_factura(factura, usuario=None):
    """Crea la factura en Cashflow (que asigna el NCF / e-CF) y la deja emitida aquí."""
    from apps.finanzas import servicios as fin
    if factura.cashflow_id:
        raise CashflowError("Esta factura ya está en Cashflow.")
    if factura.total <= 0:
        raise CashflowError("La factura está en cero.")
    sincronizar_cliente(factura.cliente, usuario)
    doc = mapeo.leer_documento(_llamar('crear_factura', f"factura:{factura.pk}", usuario, cuerpo=mapeo.factura(factura)))
    factura.cashflow_id, factura.cashflow_numero, factura.cashflow_estado = doc['id'], doc['numero'], doc['estado']
    if doc['ncf']:
        factura.ncf = doc['ncf']
    factura.cashflow_sincronizado = timezone.now()
    factura.save(update_fields=['cashflow_id', 'cashflow_numero', 'cashflow_estado', 'ncf', 'cashflow_sincronizado'])
    if factura.estado == 'BORRADOR':
        fin.emitir(factura, usuario)
    return factura


def actualizar_factura(factura, usuario=None):
    """Trae de Cashflow el estado, el NCF y los pagos de una factura. Devuelve cuántos pagos nuevos llegaron."""
    from apps.finanzas import servicios as fin
    from apps.finanzas.models import Pago
    if not factura.cashflow_id:
        return 0
    doc = mapeo.leer_documento(_llamar('obtener_factura', f"factura:{factura.pk}", usuario, ids={'id': factura.cashflow_id}))
    cambios = ['cashflow_estado', 'cashflow_sincronizado']
    factura.cashflow_estado = doc['estado'] or factura.cashflow_estado
    if doc['ncf'] and doc['ncf'] != factura.ncf:
        factura.ncf = doc['ncf']
        cambios.append('ncf')
    factura.cashflow_sincronizado = timezone.now()
    factura.save(update_fields=cambios)
    nuevos = 0
    for p in mapeo.leer_pagos(_llamar('pagos_factura', f"factura:{factura.pk}", usuario, ids={'id': factura.cashflow_id})):
        if not p['id'] or Pago.objects.filter(cashflow_id=p['id']).exists() or p['monto'] <= 0:
            continue
        try:
            fecha = date.fromisoformat(p['fecha'])
        except ValueError:
            fecha = timezone.localdate()
        monto = min(p['monto'], factura.saldo) if factura.saldo > 0 else Decimal('0')
        if monto <= 0:
            continue
        fin.registrar_pago(factura, usuario, monto, fecha=fecha, metodo=p['metodo'] if p['metodo'] in METODOS else 'OTRO',
                           referencia=p['referencia'], cashflow_id=p['id'])
        factura.refresh_from_db()
        nuevos += 1
    return nuevos


def sincronizar_pendientes(usuario=None):
    """Para la tarea programada: actualiza todas las facturas abiertas que están en Cashflow."""
    from apps.finanzas.models import Factura
    from apps.operaciones.servicios_ot import revisar_anticipo
    resultado = {'facturas': 0, 'pagos': 0, 'errores': 0}
    for f in Factura.objects.filter(estado='EMITIDA').exclude(cashflow_id=''):
        try:
            resultado['pagos'] += actualizar_factura(f, usuario)
            resultado['facturas'] += 1
            if f.orden_id:
                revisar_anticipo(f.orden)
        except CashflowError:
            resultado['errores'] += 1
    return resultado
