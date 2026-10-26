"""
Cómo se traducen los datos de Adzone Team a Cashflow y de vuelta. Ajusta los nombres de campo
aquí si la documentación de Cashflow los llama distinto.
"""
from decimal import Decimal

TIPO_NCF = {
    'EMPRESA': '31',   # e-CF crédito fiscal (B01 en NCF tradicional)
    'GOBIERNO': '45',  # e-CF gubernamental (B15)
    'ONG': '31',
    'PERSONA': '32',   # e-CF consumo (B02)
    'INTERNO': '32',
}


def cliente(c):
    return {
        'name': c.nombre,
        'tax_id': (c.rnc or '').replace('-', ''),
        'email': c.correo or None,
        'phone': c.telefono or None,
        'address': c.direccion or None,
        'contact_name': c.contacto or None,
        'external_id': f"adzone-cliente-{c.pk}",
    }


def _lineas(doc):
    return [{
        'description': l.descripcion,
        'quantity': float(l.cantidad),
        'price': float(l.precio),
        'tax': 'ITBIS 18%' if l.aplica_itbis else 'Exento',
    } for l in doc.lineas.all()]


def cotizacion(cot):
    return {
        'customer_id': cot.cliente.cashflow_id,
        'date': cot.fecha.isoformat(),
        'expiration_date': cot.valida_hasta.isoformat() if cot.valida_hasta else None,
        'currency': cot.moneda,
        'reference': cot.numero,
        'notes': cot.titulo,
        'terms': cot.condiciones,
        'items': _lineas(cot),
    }


def factura(f):
    orden = f.orden
    return {
        'customer_id': f.cliente.cashflow_id,
        'date': f.fecha.isoformat(),
        'due_date': f.vencimiento.isoformat() if f.vencimiento else None,
        'currency': f.moneda,
        'status': 'open',                       # Borrador o Abierta en Cashflow: «Abierta» afecta CxC e impuestos
        'ncf_type': TIPO_NCF.get(f.cliente.tipo, '31'),
        'reference': f"{f.numero}{f' · {orden.numero}' if orden and orden.numero else ''}",
        'notes': f.titulo,
        'items': _lineas(f),
    }


def _primero(d, *claves, defecto=None):
    for k in claves:
        if isinstance(d, dict) and d.get(k) not in (None, ''):
            return d[k]
    return defecto


def leer_id(respuesta):
    datos = respuesta.get('data', respuesta) if isinstance(respuesta, dict) else {}
    return str(_primero(datos, 'id', 'uuid', 'code', defecto=''))


def leer_documento(respuesta):
    """Normaliza la respuesta de una factura o cotización."""
    d = respuesta.get('data', respuesta) if isinstance(respuesta, dict) else {}
    total = Decimal(str(_primero(d, 'total', 'amount', defecto=0)))
    saldo = _primero(d, 'balance', 'amount_due', 'pending')
    return {
        'id': str(_primero(d, 'id', 'uuid', defecto='')),
        'numero': str(_primero(d, 'number', 'document_number', 'code', defecto='')),
        'ncf': str(_primero(d, 'ncf', 'encf', 'e_ncf', 'fiscal_number', defecto='')),
        'estado': str(_primero(d, 'status', 'state', defecto='')),
        'total': total,
        'saldo': Decimal(str(saldo)) if saldo is not None else None,
    }


def leer_pagos(respuesta):
    lista = respuesta.get('data', respuesta) if isinstance(respuesta, dict) else respuesta
    pagos = []
    for p in lista or []:
        pagos.append({
            'id': str(_primero(p, 'id', 'uuid', defecto='')),
            'fecha': str(_primero(p, 'date', 'payment_date', defecto=''))[:10],
            'monto': Decimal(str(_primero(p, 'amount', 'total', defecto=0))),
            'metodo': str(_primero(p, 'method', 'payment_method', defecto='TRANSFERENCIA')).upper(),
            'referencia': str(_primero(p, 'reference', 'number', defecto=''))[:100],
        })
    return pagos


def leer_clientes(respuesta):
    lista = respuesta.get('data', respuesta) if isinstance(respuesta, dict) else respuesta
    return [{'id': str(_primero(c, 'id', 'uuid', defecto='')), 'rnc': str(_primero(c, 'tax_id', 'rnc', defecto='')).replace('-', ''),
             'nombre': _primero(c, 'name', 'business_name', defecto='')} for c in (lista or [])]
