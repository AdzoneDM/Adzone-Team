"""
Dónde se marca: QR rotativo de la oficina (cambia cada 30 s en una pantalla) o ubicación del celular.

- OFICINA: vale el QR de la pantalla (escaneado hace menos de 90 s) o estar dentro del radio de un lugar activo.
- CALLE: vale desde cualquier sitio, pero el celular debe dar la ubicación (queda guardada con el marcaje).
- LIBRE: como siempre; si el celular manda la ubicación, se guarda.
La ubicación solo se pide en el momento de marcar: la plataforma no sigue a nadie.
"""
import hashlib
import hmac
import math
import time

from django.conf import settings

VENTANA = 30
VENTANAS_VALIDAS = 3  # el QR que se ve ahora y los dos anteriores (hasta 90 s)
PRECISION_MAXIMA = 150  # metros: una ubicación peor que esto no prueba que esté en el lugar


def token(sitio, ventana=None):
    v = int(time.time() // VENTANA) if ventana is None else ventana
    return hmac.new(settings.SECRET_KEY.encode(), f'qr:{sitio.pk}:{sitio.clave_pantalla}:{v}'.encode(), hashlib.sha256).hexdigest()[:16]


def token_valido(sitio, valor):
    actual = int(time.time() // VENTANA)
    return any(hmac.compare_digest(token(sitio, actual - i), str(valor or '')) for i in range(VENTANAS_VALIDAS))


def distancia_m(lat1, lng1, lat2, lng2):
    r = 6371000
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp, dl = p2 - p1, math.radians(float(lng2) - float(lng1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def sitio_cercano(lat, lng, precision):
    from .models import SitioMarcaje
    if lat is None or lng is None or (precision is not None and precision > PRECISION_MAXIMA):
        return None
    for s in SitioMarcaje.objects.filter(activo=True, latitud__isnull=False, longitud__isnull=False):
        if distancia_m(lat, lng, s.latitud, s.longitud) <= s.radio_m + (precision or 0):
            return s
    return None


def donde_marca(usuario):
    a = getattr(usuario, 'asignacion_horario', None)
    return a.donde_marca if a else 'LIBRE'


def _num(v, minimo, maximo):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if minimo <= n <= maximo else None


def validar(usuario, datos):
    """Devuelve ({sitio, latitud, longitud, precision_m, origen}, error)."""
    from .models import SitioMarcaje
    lat, lng = _num(datos.get('latitud'), -90, 90), _num(datos.get('longitud'), -180, 180)
    precision = _num(datos.get('precision'), 0, 100000)
    precision = int(precision) if precision is not None else None
    extra = {'latitud': round(lat, 6) if lat is not None else None, 'longitud': round(lng, 6) if lng is not None else None,
             'precision_m': precision, 'sitio': None, 'origen': None}
    qr = datos.get('qr') or {}
    if qr:
        sitio = SitioMarcaje.objects.filter(pk=qr.get('sitio'), activo=True).first() if str(qr.get('sitio') or '').isdigit() else None
        if sitio is None or not token_valido(sitio, qr.get('token')):
            return None, 'El código QR ya cambió: escanéalo de nuevo en la pantalla.'
        extra.update(sitio=sitio, origen='QR')
        return extra, None
    modo = donde_marca(usuario)
    if modo == 'OFICINA':
        sitio = sitio_cercano(lat, lng, precision)
        if sitio is None:
            if lat is None:
                return None, 'Marca con el QR de la pantalla de la oficina, o permite la ubicación del celular.'
            return None, 'No estás en la oficina según tu ubicación. Marca con el QR de la pantalla.'
        extra['sitio'] = sitio
    elif modo == 'CALLE' and lat is None:
        return None, 'Para marcar fuera de la oficina, permite la ubicación del celular.'
    else:
        extra['sitio'] = sitio_cercano(lat, lng, precision)
    return extra, None
