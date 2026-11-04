"""
Notificaciones en el celular (Web Push): cada aviso de la campanita llega también al celular de la persona,
aunque la app esté cerrada. Necesita las claves VAPID en .env (python manage.py generar_vapid).
"""
import json
import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

log = logging.getLogger(__name__)


# Solo los servicios de notificaciones de los navegadores (no se manda nada a otra dirección)
SERVICIOS = ('fcm.googleapis.com', 'updates.push.services.mozilla.com', 'push.services.mozilla.com', 'web.push.apple.com',
             'notify.windows.com', 'push.apple.com')
MAX_POR_PERSONA = 5
_hilos = None


def endpoint_valido(url):
    from urllib.parse import urlparse
    try:
        u = urlparse(url)
    except ValueError:
        return False
    host = (u.hostname or '').lower()
    return u.scheme == 'https' and u.port in (None, 443) and any(host == s or host.endswith('.' + s) for s in SERVICIOS)


def configurado():
    return bool(getattr(settings, 'VAPID_PRIVADA', '') and getattr(settings, 'VAPID_PUBLICA', ''))


class _SinRedirecciones:
    """Sesión de requests que nunca sigue redirecciones (para que nadie use los avisos para llegar a otra dirección)."""
    def __init__(self):
        import requests
        self._s = requests.Session()

    def post(self, url, **kw):
        kw['allow_redirects'] = False
        return self._s.post(url, **kw)


def _enviar(ids, datos):
    from django.db import connection
    from pywebpush import WebPushException, webpush
    from .models import SuscripcionPush
    try:
        _enviar_a(SuscripcionPush.objects.filter(pk__in=ids, usuario__is_active=True), datos, webpush, WebPushException)
    finally:
        connection.close()


def _enviar_a(suscripciones, datos, webpush, WebPushException):
    sesion = _SinRedirecciones()
    for s in suscripciones:
        if not endpoint_valido(s.endpoint):
            s.delete()
            continue
        try:
            webpush({'endpoint': s.endpoint, 'keys': {'p256dh': s.p256dh, 'auth': s.auth}}, json.dumps(datos),
                    vapid_private_key=settings.VAPID_PRIVADA, vapid_claims={'sub': f'mailto:{settings.VAPID_CORREO}'}, ttl=24 * 3600,
                    timeout=10, requests_session=sesion)
        except WebPushException as e:
            codigo = getattr(getattr(e, 'response', None), 'status_code', None)
            if codigo in (404, 410):  # el celular canceló la suscripción
                s.delete()
            else:
                log.warning('Push no enviado a %s: %s', s.pk, e)
        except Exception as e:  # noqa: BLE001 (un celular que falla no debe romper el aviso)
            log.warning('Push no enviado a %s: %s', s.pk, e)


def enviar(usuario_id, titulo, mensaje='', enlace=''):
    if not configurado():
        return
    from .models import SuscripcionPush
    ids = list(SuscripcionPush.objects.filter(usuario_id=usuario_id).values_list('pk', flat=True))
    if not ids:
        return
    datos = {'titulo': titulo[:120], 'mensaje': (mensaje or '')[:240], 'enlace': enlace or '/'}
    if getattr(settings, 'PUSH_SINCRONO', False):
        from pywebpush import WebPushException, webpush
        from .models import SuscripcionPush
        _enviar_a(SuscripcionPush.objects.filter(pk__in=ids, usuario__is_active=True), datos, webpush, WebPushException)
    else:
        global _hilos
        if _hilos is None:
            from concurrent.futures import ThreadPoolExecutor
            _hilos = ThreadPoolExecutor(max_workers=2, thread_name_prefix='push')
        _hilos.submit(_enviar, ids, datos)


@receiver(post_save, sender='desempeno.Notificacion')
def aviso_al_celular(sender, instance, created, **kwargs):
    if created:
        from django.db import transaction
        transaction.on_commit(lambda: enviar(instance.destinatario_id, instance.titulo, instance.mensaje, instance.enlace))
