"""
Seguridad de las cuentas: verificación en dos pasos (TOTP, RFC 6238), cierre por inactividad y aviso de dispositivo nuevo.

- Dos pasos: obligatoria para quien maneja la empresa (Dirección, personas y accesos, Gestión del Talento, salarios
  y configuración del sistema). Para el resto es opcional.
- Inactividad: la sesión se cierra tras N minutos sin que la persona use la app (no cuentan los avisos que la app
  consulta sola). Más corto para las cuentas con permisos de empresa.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.utils import timezone

PASO = 30
EMISOR = 'Adzone Team'
SESION_OK = 'dos_pasos_ok'
SESION_ACTIVIDAD = 'ultima_actividad'
EXIGEN = {'direccion', 'personal.usuarios', 'talento.rrhh', 'personal.salarios', 'sistema.configurar'}


# ------------------------------------------------------------------ TOTP
def nuevo_secreto():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def _codigo(secreto, contador):
    clave = base64.b32decode(secreto + '=' * (-len(secreto) % 8))
    h = hmac.new(clave, struct.pack('>Q', contador), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return f"{(struct.unpack('>I', h[o:o + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def paso_valido(secreto, codigo, ultimo=0, ahora=None, margen=1):
    """Devuelve el intervalo usado si el código es válido (±30 s de margen) y no se usó antes; si no, None."""
    codigo = ''.join(ch for ch in str(codigo or '') if ch.isdigit())
    if len(codigo) != 6:
        return None
    actual = int((ahora or time.time()) // PASO)
    for c in range(actual - margen, actual + margen + 1):
        if c > ultimo and hmac.compare_digest(_codigo(secreto, c), codigo):
            return c
    return None


def uri(usuario, secreto):
    cuenta = quote(f'{EMISOR}:{usuario.username}')
    return f'otpauth://totp/{cuenta}?secret={secreto}&issuer={quote(EMISOR)}&digits=6&period={PASO}'


def qr_svg(texto):
    import io
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(texto, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    b = io.BytesIO()
    img.save(b)
    return b.getvalue().decode()


def _hash_respaldo(codigo):
    return hashlib.sha256((settings.SECRET_KEY + codigo.replace('-', '').lower()).encode()).hexdigest()


def nuevos_respaldo(n=10):
    codigos = [f'{secrets.token_hex(2)}-{secrets.token_hex(2)}' for _ in range(n)]
    return codigos, [_hash_respaldo(c) for c in codigos]


def verificar(dp, codigo):
    """Código de la app o de respaldo (que se gasta). Guarda el intervalo para que no se repita."""
    paso = paso_valido(dp.secreto, codigo, dp.ultimo_paso)
    if paso is not None:
        dp.ultimo_paso = paso
        dp.save(update_fields=['ultimo_paso'])
        return True
    h = _hash_respaldo(str(codigo or '').strip())
    if h in (dp.respaldo or []):
        dp.respaldo = [x for x in dp.respaldo if x != h]
        dp.save(update_fields=['respaldo'])
        return True
    return False


# ------------------------------------------------------------------ Quién la necesita
def exige_dos_pasos(user):
    from .permisos import permisos
    return bool(user and user.is_authenticated and (user.is_superuser or permisos(user) & EXIGEN))


def tiene_dos_pasos(user):
    from .models import DosPasos
    return DosPasos.objects.filter(usuario=user, activo=True).exists()


def minutos_inactividad(user):
    if exige_dos_pasos(user):
        return int(getattr(settings, 'INACTIVIDAD_EMPRESA_MIN', 30))
    return int(getattr(settings, 'INACTIVIDAD_MIN', 12 * 60))


# ------------------------------------------------------------------ Dispositivo nuevo
COOKIE = 'adz_disp'


def registrar_dispositivo(request, response, user):
    """Marca el navegador con una cookie propia. Si la persona ya tenía otros y este es nuevo, le avisa."""
    from .models import DispositivoConocido
    valor = request.COOKIES.get(COOKIE) or secrets.token_urlsafe(24)
    huella = hashlib.sha256((settings.SECRET_KEY + valor).encode()).hexdigest()
    navegador = (request.META.get('HTTP_USER_AGENT') or '')[:200]
    ip = request.META.get('REMOTE_ADDR')
    tenia = DispositivoConocido.objects.filter(usuario=user).exists()
    d, nuevo = DispositivoConocido.objects.get_or_create(usuario=user, huella=huella, defaults={'navegador': navegador, 'ip': ip})
    if not nuevo:
        d.navegador, d.ip = navegador, ip
        d.save(update_fields=['navegador', 'ip', 'ultimo'])
    elif tenia:
        from apps.desempeno.servicios import avisar
        avisar([user], 'SEGURIDAD', 'Entraste desde un dispositivo nuevo',
               f'{_describir(navegador)} · {timezone.localtime():%d/%m %H:%M}. Si no fuiste tú, cambia tu contraseña en Mi cuenta y avisa a la Dirección.',
               enlace='/mi-cuenta')
    response.set_cookie(COOKIE, valor, max_age=5 * 365 * 24 * 3600, httponly=True, samesite='Lax',
                        secure=not settings.DEBUG)


def _describir(ua):
    ua = ua or ''
    sistema = next((n for k, n in (('iPhone', 'iPhone'), ('iPad', 'iPad'), ('Android', 'Android'), ('Windows', 'Windows'),
                                   ('Mac OS', 'Mac'), ('Linux', 'Linux')) if k in ua), 'Otro sistema')
    nav = next((n for k, n in (('Edg/', 'Edge'), ('OPR/', 'Opera'), ('Chrome/', 'Chrome'), ('Firefox/', 'Firefox'),
                               ('Safari/', 'Safari')) if k in ua), 'navegador')
    return f'{nav} en {sistema}'


# ------------------------------------------------------------------ Middleware
# Lo que se permite mientras falta activar la verificación en dos pasos
PERMITIDO_SIN_DOS_PASOS = ('/api/auth/', '/api/cuenta/dos-pasos/')


class SeguridadMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and not getattr(request, '_agente', False):
            salida = self._revisar(request, user)
            if salida is not None:
                return salida
        return self.get_response(request)

    def _revisar(self, request, user):
        ruta = request.path
        if not (ruta.startswith('/api/') or ruta.startswith('/admin')):
            return None
        s = request.session
        # 1) Quien tiene la verificación activa debe haberla pasado en esta sesión (cubre también /admin)
        if not s.get(SESION_OK) and tiene_dos_pasos(user):
            logout(request)
            return JsonResponse({'detail': 'Entra de nuevo con tu código de verificación.'}, status=401)
        # 2) Cierre por inactividad (solo cuenta la actividad real: la app envía X-Actividad al usarla)
        ahora = int(time.time())
        ultima = s.get(SESION_ACTIVIDAD)
        if ultima and ahora - ultima > minutos_inactividad(user) * 60:
            logout(request)
            return JsonResponse({'detail': 'Tu sesión se cerró por inactividad. Entra de nuevo.', 'inactividad': True}, status=401)
        if not ultima or request.method != 'GET' or request.headers.get('X-Actividad') == '1':
            s[SESION_ACTIVIDAD] = ahora
        # 3) Cuentas que la exigen y aún no la activaron: solo pueden activarla
        if exige_dos_pasos(user) and not s.get(SESION_OK) and not ruta.startswith(PERMITIDO_SIN_DOS_PASOS):
            if ruta.startswith('/admin'):
                logout(request)
            return JsonResponse({'detail': 'Activa la verificación en dos pasos para seguir.', 'activar_dos_pasos': True}, status=403)
        return None
