"""
Rutas de la API de Cashflow (cashflow.do) — EL ÚNICO LUGAR QUE HAY QUE AJUSTAR.

La documentación oficial está en https://cashflow.do/dev/iniciando (requiere la cuenta de Ad Zone).
Estas rutas siguen la convención REST habitual y los nombres de los módulos de Cashflow
(clientes, cotizaciones, facturas, recibos de ingreso). Cuando tengas la documentación, compara
y corrige aquí: método, ruta y, si hace falta, el mapeo de campos en mapeo.py.

{id} se reemplaza por el id del documento en Cashflow.
"""
RUTAS = {
    'probar': ('GET', '/v1/company'),                       # datos de la empresa: sirve para probar la conexión
    'buscar_cliente': ('GET', '/v1/customers'),              # ?search=<RNC>
    'crear_cliente': ('POST', '/v1/customers'),
    'crear_cotizacion': ('POST', '/v1/quotes'),
    'crear_factura': ('POST', '/v1/invoices'),
    'obtener_factura': ('GET', '/v1/invoices/{id}'),
    'pagos_factura': ('GET', '/v1/invoices/{id}/payments'),  # recibos de ingreso aplicados a la factura
    'facturas_cliente': ('GET', '/v1/invoices'),             # ?customer_id=<id>&status=open
}

# Parámetro de búsqueda de clientes y nombre del filtro por cliente en facturas.
PARAMETRO_BUSQUEDA = 'search'
PARAMETRO_CLIENTE = 'customer_id'
