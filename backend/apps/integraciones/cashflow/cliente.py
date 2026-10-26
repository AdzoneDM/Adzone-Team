"""Cliente HTTP de Cashflow y simulador para el modo de prueba."""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from .rutas import RUTAS

log = logging.getLogger('adzone')


class CashflowError(Exception):
    """Error legible para mostrar en pantalla."""


class CashflowAPI:
    modo = 'real'

    def __init__(self):
        self.base = settings.CASHFLOW_API_URL.rstrip('/')
        self.clave = settings.CASHFLOW_API_KEY
        self.timeout = settings.CASHFLOW_TIMEOUT

    def llamar(self, operacion, cuerpo=None, ids=None, params=None):
        metodo, ruta = RUTAS[operacion]
        url = self.base + ruta.format(**(ids or {}))
        if params:
            url += '?' + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, '')})
        datos = json.dumps(cuerpo, default=str).encode() if cuerpo is not None else None
        cabeceras = {'Accept': 'application/json', 'User-Agent': 'AdzoneTeam/6',
                     settings.CASHFLOW_AUTH_HEADER: f"{settings.CASHFLOW_AUTH_PREFIX}{self.clave}"}
        if datos is not None:
            cabeceras['Content-Type'] = 'application/json'
        pedido = urllib.request.Request(url, data=datos, headers=cabeceras, method=metodo)
        try:
            with urllib.request.urlopen(pedido, timeout=self.timeout) as r:  # noqa: S310 (URL configurada por el administrador)
                texto = r.read().decode() or '{}'
                return json.loads(texto)
        except urllib.error.HTTPError as e:
            cuerpo_error = e.read().decode(errors='replace')[:500]
            if e.code in (401, 403):
                raise CashflowError("Cashflow rechazó la API key. Revísala en el servidor (CASHFLOW_API_KEY).") from e
            if e.code == 404:
                raise CashflowError(f"Cashflow no encontró «{ruta}». Revisa la ruta en integraciones/cashflow/rutas.py.") from e
            if e.code == 422 or e.code == 400:
                raise CashflowError(f"Cashflow no aceptó los datos: {cuerpo_error}") from e
            raise CashflowError(f"Cashflow respondió con error {e.code}.") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise CashflowError("No se pudo conectar con Cashflow. Revisa el internet del servidor o CASHFLOW_API_URL.") from e
        except json.JSONDecodeError as e:
            raise CashflowError("Cashflow respondió algo que no es JSON. Revisa CASHFLOW_API_URL.") from e


class CashflowSimulado:
    """Responde como Cashflow para poder usar el flujo completo sin API key. No envía nada a ningún lado."""
    modo = 'prueba'
    PAGOS = {}  # pagos simulados por id de factura de Cashflow (para probar la lectura de pagos)

    def pagar(self, factura_id, monto, metodo='TRANSFERENCIA'):
        """Simula que el cliente pagó en Cashflow (pantalla de prueba de la integración)."""
        from django.utils import timezone
        lista = self.PAGOS.setdefault(factura_id, [])
        lista.append({'id': f"SIM-PAG-{factura_id}-{len(lista) + 1}", 'date': timezone.localdate().isoformat(), 'amount': str(monto),
                      'method': metodo, 'reference': f"Simulado {len(lista) + 1}"})
        return lista[-1]

    def llamar(self, operacion, cuerpo=None, ids=None, params=None):
        from apps.finanzas.models import Factura
        if operacion == 'probar':
            return {'data': {'name': 'Ad Zone Marketing SRL (simulado)'}}
        if operacion == 'buscar_cliente':
            return {'data': []}
        if operacion == 'crear_cliente':
            return {'data': {'id': f"SIM-{cuerpo['external_id'].rsplit('-', 1)[1]}"}}
        if operacion == 'crear_cotizacion':
            return {'data': {'id': f"SIM-COT-{cuerpo['reference']}", 'number': cuerpo['reference'].replace('COT', 'CF-COT'), 'status': 'open'}}
        if operacion == 'crear_factura':
            n = Factura.objects.exclude(ncf='').count() + 1
            tipo = cuerpo.get('ncf_type', '31')
            return {'data': {'id': f"SIM-FAC-{cuerpo['reference'].split(' ')[0]}", 'number': f"CF-{n:06d}",
                             'ncf': f"E{tipo}{n:010d}", 'status': 'open'}}
        if operacion == 'obtener_factura':
            f = Factura.objects.filter(cashflow_id=ids['id']).first()
            return {'data': {'id': ids['id'], 'number': f.cashflow_numero if f else '', 'ncf': f.ncf if f else '',
                             'status': 'paid' if f and f.saldo <= 0 else 'open', 'total': str(f.total if f else 0),
                             'balance': str(f.saldo if f else 0)}}
        if operacion == 'pagos_factura':
            return {'data': list(self.PAGOS.get(ids['id'], []))}
        if operacion == 'facturas_cliente':
            return {'data': []}
        raise CashflowError(f"Operación desconocida: {operacion}")


def conexion():
    return CashflowAPI() if settings.CASHFLOW_MODO == 'real' else CashflowSimulado()
