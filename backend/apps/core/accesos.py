"""
Protección y bitácora de accesos:

- IP real del cliente (detrás del proxy de Plesk), navegador y dispositivo en cada evento.
- Bloqueo por cuenta: 10 contraseñas equivocadas en 15 minutos (desde cualquier IP) bloquean esa cuenta 15 minutos.
- Evaluación de riesgo al entrar: un cambio de IP por sí solo NO bloquea. Suman: dispositivo nuevo, red nunca usada por esa persona,
  otra sesión activa desde otra red en la última media hora, hora poco habitual y fallos recientes. Con riesgo 2 o más se avisa a la
  persona y a quien supervisa la seguridad (permiso «Ver la auditoría»); nunca se bloquea solo por eso.
- Lista de IPs permitidas para las cuentas de empresa (IPS_ADMIN en el .env, opcional) y para /admin.
- Sesiones abiertas de cada persona, para verlas y cerrarlas a distancia.
"""
import ipaddress
import time
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

FALLOS_MAX = 10
VENTANA_FALLOS = 15 * 60
BLOQUEO_CUENTA = 15 * 60
RIESGO_ALERTA = 2


def ip_de(request):
    """La IP real del cliente: con proxy, la que agrega el proxy (NUM_PROXIES), igual que el límite de intentos de la API."""
    from rest_framework.settings import api_settings
    from rest_framework.throttling import SimpleRateThrottle
    if api_settings.NUM_PROXIES is not None:
        ip = SimpleRateThrottle().get_ident(request)
    else:
        ip = request.META.get('REMOTE_ADDR')
    try:
        return str(ipaddress.ip_address((ip or '').strip()))
    except ValueError:
        return None


def red_de(ip):
    """La red aproximada (/24 en IPv4, /48 en IPv6): dos IPs de la misma oficina o del mismo proveedor cuentan como la misma red."""
    if not ip:
        return ''
    try:
        return str(ipaddress.ip_network(f"{ip}/{24 if ':' not in ip else 48}", strict=False))
    except ValueError:
        return ''


def describir(ua):
    from .seguridad import _describir
    return _describir(ua)


def registrar(tipo, request=None, usuario=None, texto='', motivo='', riesgo=0, nuevo=False, sesion=''):
    from .models import EventoAcceso
    ua = (request.META.get('HTTP_USER_AGENT') or '')[:255] if request is not None else ''
    return EventoAcceso.objects.create(
        tipo=tipo, usuario=usuario if (usuario and usuario.pk) else None,
        usuario_texto=(texto or (usuario.username if usuario else ''))[:150], ip=ip_de(request) if request is not None else None,
        navegador=ua, dispositivo=describir(ua) if ua else '', dispositivo_nuevo=nuevo, sesion=sesion or '', riesgo=riesgo,
        motivo=motivo[:255], ruta=(request.path[:255] if request is not None else ''))


# ------------------------------------------------------------------ Bloqueo por cuenta
def _clave_fallos(cuenta):
    return f'acceso:fallos:{str(cuenta).lower()[:150]}'


def _clave_bloqueo(cuenta):
    return f'acceso:bloqueada:{str(cuenta).lower()[:150]}'


def cuenta_bloqueada(cuenta):
    hasta = cache.get(_clave_bloqueo(cuenta))
    return bool(hasta and hasta > time.time())


def anotar_fallo(request, cuenta, usuario=None):
    """Un intento fallido contra esta cuenta (desde cualquier IP). Al llegar al tope, la bloquea y avisa. Devuelve True si quedó bloqueada."""
    registrar('FALLO', request, usuario, texto=str(cuenta))
    clave = _clave_fallos(cuenta)
    cache.add(clave, 0, VENTANA_FALLOS)
    try:
        n = cache.incr(clave)
    except ValueError:
        cache.set(clave, 1, VENTANA_FALLOS)
        n = 1
    if n >= FALLOS_MAX:
        cache.set(_clave_bloqueo(cuenta), time.time() + BLOQUEO_CUENTA, BLOQUEO_CUENTA)
        cache.delete(clave)
        registrar('BLOQUEO', request, usuario, texto=str(cuenta), motivo=f'{n} contraseñas equivocadas en 15 minutos', riesgo=3)
        if usuario is not None:
            alertar_seguridad(usuario, 'Tu cuenta se bloqueó 15 minutos',
                              f'Hubo {n} intentos con contraseña equivocada (la última desde {ip_de(request) or "una IP desconocida"}). '
                              'Si no fuiste tú, alguien intenta entrar a tu cuenta: cambia tu contraseña en Mi cuenta.',
                              a_seguridad=f'Cuenta de {usuario.get_full_name() or usuario.username} bloqueada por {n} intentos fallidos')
        return True
    return False


def limpiar_fallos(cuenta):
    cache.delete(_clave_fallos(cuenta))


# ------------------------------------------------------------------ Riesgo al entrar
def evaluar_riesgo(request, usuario, dispositivo_nuevo):
    """Puntos de riesgo y sus motivos. Ningún factor por sí solo bloquea: solo se avisa con 2 o más."""
    from .models import EventoAcceso
    ip = ip_de(request)
    red = red_de(ip)
    puntos, motivos = 0, []
    previas = EventoAcceso.objects.filter(usuario=usuario, tipo='ENTRADA', fecha__gte=timezone.now() - timedelta(days=90))
    redes = {red_de(i) for i in previas.exclude(ip=None).values_list('ip', flat=True)[:500]}
    if dispositivo_nuevo:
        puntos += 1
        motivos.append('dispositivo nuevo')
    if redes and red and red not in redes:
        puntos += 1
        motivos.append('red nunca usada por esta persona')
    recientes = previas.filter(fecha__gte=timezone.now() - timedelta(minutes=30)).exclude(ip=None).values_list('ip', flat=True)
    if red and any(red_de(i) != red for i in recientes):
        puntos += 1
        motivos.append('otra sesión desde otra red en los últimos 30 minutos')
    hora = timezone.localtime().hour
    if hora < 5 or hora >= 23:
        puntos += 1
        motivos.append('hora poco habitual')
    if EventoAcceso.objects.filter(usuario_texto__iexact=usuario.username, tipo='FALLO', fecha__gte=timezone.now() - timedelta(hours=1)).count() >= 3:
        puntos += 1
        motivos.append('varios intentos fallidos en la última hora')
    return puntos, motivos


def alertar_seguridad(usuario, titulo, mensaje, a_seguridad=None):
    """Aviso a la persona y, si se indica, a quienes supervisan la seguridad (permiso «Ver la auditoría»)."""
    from apps.desempeno.servicios import avisar
    from .permisos import con_permiso
    avisar([usuario], 'SEGURIDAD', titulo, mensaje, enlace='/mi-cuenta')
    if a_seguridad:
        avisar([u for u in con_permiso('auditoria.ver') if u.pk != usuario.pk], 'SEGURIDAD', a_seguridad, mensaje, enlace='/talento?ver=accesos')


def al_entrar(request, usuario, dispositivo_nuevo):
    """Registra la entrada (con la sesión recién abierta) y evalúa el riesgo."""
    puntos, motivos = evaluar_riesgo(request, usuario, dispositivo_nuevo)
    sesion = request.session.session_key or ''
    registrar('ENTRADA', request, usuario, riesgo=puntos, nuevo=dispositivo_nuevo, sesion=sesion, motivo=', '.join(motivos))
    limpiar_fallos(usuario.username)
    if puntos >= RIESGO_ALERTA:
        registrar('SOSPECHOSO', request, usuario, riesgo=puntos, nuevo=dispositivo_nuevo, sesion=sesion, motivo=', '.join(motivos))
        alertar_seguridad(usuario, 'Entrada poco habitual a tu cuenta',
                          f'{describir(request.META.get("HTTP_USER_AGENT"))} desde {ip_de(request) or "IP desconocida"} '
                          f'({", ".join(motivos)}), {timezone.localtime():%d/%m %H:%M}. Si no fuiste tú, cierra esa sesión en '
                          'Mi cuenta → Sesiones abiertas y cambia tu contraseña.',
                          a_seguridad=f'Entrada poco habitual: {usuario.get_full_name() or usuario.username}')


# ------------------------------------------------------------------ IPs permitidas
def _redes(texto):
    salida = []
    for parte in (texto or '').replace(',', ' ').split():
        try:
            salida.append(ipaddress.ip_network(parte, strict=False))
        except ValueError:
            continue
    return salida


def ip_permitida(ip, redes):
    if not redes:
        return True
    try:
        dir_ = ipaddress.ip_address(ip or '')
    except ValueError:
        return False
    return any(dir_ in r for r in redes)


def redes_admin():
    """IPS_ADMIN (opcional): redes desde donde pueden entrar las cuentas de empresa y /admin. Vacío = sin restricción."""
    return _redes(getattr(settings, 'IPS_ADMIN', ''))


# ------------------------------------------------------------------ Sesiones abiertas
def sesiones_abiertas(usuario):
    """Las sesiones vigentes de la persona, con el dispositivo, la IP y la hora de entrada."""
    from django.contrib.sessions.models import Session
    from .models import EventoAcceso
    entradas = {e.sesion: e for e in EventoAcceso.objects.filter(usuario=usuario, tipo='ENTRADA').exclude(sesion='').order_by('fecha')}
    vivas = set(Session.objects.filter(session_key__in=list(entradas), expire_date__gt=timezone.now()).values_list('session_key', flat=True))
    return [entradas[k] for k in entradas if k in vivas]


def cerrar_sesion(request, usuario, evento):
    from django.contrib.sessions.models import Session
    Session.objects.filter(session_key=evento.sesion).delete()
    registrar('SESION_CERRADA', request, usuario, motivo=f'{evento.dispositivo} · {evento.ip or ""} (entró {timezone.localtime(evento.fecha):%d/%m %H:%M})')
