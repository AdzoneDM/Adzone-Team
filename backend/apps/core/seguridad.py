"""
Seguridad de las cuentas: verificación en dos pasos (TOTP, RFC 6238), cierre por inactividad y aviso de dispositivo nuevo.

- Dos pasos: solo para las áreas de Gerencia, Administración y Tecnología (y los superusuarios). Con
  DOS_PASOS_OBLIGATORIA=1 es obligatoria para ellas; si no, la activan en Mi cuenta. El resto de áreas no la usa.
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
# Áreas que usan la verificación en dos pasos (nombre del departamento, sin tildes ni mayúsculas)
AREAS_DOS_PASOS = {'gerencia', 'administracion', 'tecnologia'}


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


FALLOS_MAX = 5
BLOQUEO = 15 * 60


def bloqueado(dp):
    return bool(dp.bloqueado_hasta and dp.bloqueado_hasta > timezone.now())


def verificar(dp, codigo):
    """Código de la app o de respaldo (que se gasta). Con bloqueo por persona: 5 fallos seguidos = 15 minutos.
    Se hace con la fila bloqueada para que dos peticiones a la vez no usen el mismo código ni cuenten un solo fallo."""
    from datetime import timedelta
    from django.db import transaction
    from .models import DosPasos
    with transaction.atomic():
        dp = DosPasos.objects.select_for_update().get(pk=dp.pk)
        if bloqueado(dp):
            return False
        paso = paso_valido(dp.secreto, codigo, dp.ultimo_paso)
        h = _hash_respaldo(str(codigo or '').strip())
        if paso is not None:
            dp.ultimo_paso = paso
        elif h in (dp.respaldo or []):
            dp.respaldo = [x for x in dp.respaldo if x != h]
        else:
            dp.fallos += 1
            if dp.fallos >= FALLOS_MAX:
                dp.fallos, dp.bloqueado_hasta = 0, timezone.now() + timedelta(seconds=BLOQUEO)
                _avisar_bloqueo(dp.usuario)
            dp.save(update_fields=['fallos', 'bloqueado_hasta'])
            return False
        dp.fallos, dp.bloqueado_hasta = 0, None
        dp.save(update_fields=['ultimo_paso', 'respaldo', 'fallos', 'bloqueado_hasta'])
        return True


def _avisar_bloqueo(user):
    from apps.desempeno.servicios import avisar
    avisar([user], 'SEGURIDAD', 'Varios códigos de verificación equivocados',
           'Tu verificación en dos pasos se bloqueó 15 minutos. Si no fuiste tú, alguien tiene tu contraseña: cámbiala en Mi cuenta.',
           enlace='/mi-cuenta')


def cerrar_sesiones(user, excepto=None):
    """Cierra todas las sesiones abiertas de una persona (menos la indicada)."""
    from django.contrib.sessions.models import Session
    for s in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        if s.session_key != excepto and str(s.get_decoded().get('_auth_user_id')) == str(user.pk):
            s.delete()
    if excepto is None:  # sin sesiones abiertas, sus celulares tampoco deben seguir recibiendo sus avisos
        from .models import SuscripcionPush
        SuscripcionPush.objects.filter(usuario=user).delete()


# ------------------------------------------------------------------ Quién la necesita
def cuenta_de_empresa(user):
    """Quien maneja datos de la empresa (Dirección, personas, talento, salarios, configuración)."""
    from .permisos import permisos
    return bool(user and user.is_authenticated and (user.is_superuser or permisos(user) & EXIGEN))


def _sin_tildes(texto):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', texto or '') if unicodedata.category(c) != 'Mn').strip().lower()


def usa_dos_pasos(user):
    """Gerencia, Administración y Tecnología (por cualquiera de sus puestos) y los superusuarios."""
    if not (user and user.is_authenticated):
        return False
    if user.is_superuser:
        return True
    from apps.desempeno.permisos import puestos_de
    return any(p.departamento_id and _sin_tildes(p.departamento.nombre) in AREAS_DOS_PASOS for p in puestos_de(user))


def exige_dos_pasos(user):
    """Obligatoria para esas áreas si DOS_PASOS_OBLIGATORIA=1 en el .env; si no, la activan en Mi cuenta."""
    return bool(getattr(settings, 'DOS_PASOS_OBLIGATORIA', False)) and usa_dos_pasos(user)


def tiene_dos_pasos(user):
    from .models import DosPasos
    return DosPasos.objects.filter(usuario=user, activo=True).exists()


def minutos_inactividad(user):
    if cuenta_de_empresa(user):
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
PERMITIDO_SIN_DOS_PASOS = ('/api/auth/login/', '/api/auth/logout/', '/api/auth/session/', '/api/auth/dos-pasos/',
                           '/api/cuenta/dos-pasos/')


class SeguridadMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if request.method == 'POST' and request.path.startswith('/admin/login'):
            salida = self._limite_admin(request)
            if salida is not None:
                return salida
        if user is not None and user.is_authenticated:
            salida = self._revisar(request, user)
            if salida is not None:
                return salida
        return self.get_response(request)

    @staticmethod
    def _limite_admin(request):
        """El formulario de /admin no pasa por la API: 10 intentos por minuto por conexión."""
        from django.core.cache import cache
        from rest_framework.settings import api_settings
        from rest_framework.throttling import SimpleRateThrottle
        if settings.DEBUG:
            return None
        ip = SimpleRateThrottle().get_ident(request) if api_settings.NUM_PROXIES is not None else request.META.get('REMOTE_ADDR')
        clave = f'admin-login:{ip}:{int(time.time() // 60)}'
        n = cache.get_or_set(clave, 0, 70)
        cache.incr(clave)
        if n >= 10:
            from django.http import HttpResponse
            return HttpResponse('Demasiados intentos. Espera un minuto.', status=429)
        return None

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
