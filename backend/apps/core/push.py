"""
Notificaciones en el celular (Web Push): cada aviso de la campanita llega también al celular de la persona,
aunque la app esté cerrada. Necesita las claves VAPID en .env (python manage.py generar_vapid).
"""
import json
import logging
import threading

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

log = logging.getLogger(__name__)


def configurado():
    return bool(getattr(settings, 'VAPID_PRIVADA', '') and getattr(settings, 'VAPID_PUBLICA', ''))


def _enviar(ids, datos):
    from pywebpush import WebPushException, webpush
    from .models import SuscripcionPush
    for s in SuscripcionPush.objects.filter(pk__in=ids):
        try:
            webpush({'endpoint': s.endpoint, 'keys': {'p256dh': s.p256dh, 'auth': s.auth}}, json.dumps(datos),
                    vapid_private_key=settings.VAPID_PRIVADA, vapid_claims={'sub': f'mailto:{settings.VAPID_CORREO}'}, ttl=24 * 3600,
                    timeout=10)
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
        _enviar(ids, datos)
    else:
        threading.Thread(target=_enviar, args=(ids, datos), daemon=True).start()


@receiver(post_save, sender='desempeno.Notificacion')
def aviso_al_celular(sender, instance, created, **kwargs):
    if created:
        from django.db import transaction
        transaction.on_commit(lambda: enviar(instance.destinatario_id, instance.titulo, instance.mensaje, instance.enlace))
