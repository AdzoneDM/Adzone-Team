"""Mi cuenta → Avisos en este celular: suscribirse o no a las notificaciones."""
from rest_framework import exceptions, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.conf import settings

from . import push
from .models import SuscripcionPush


@api_view(['GET', 'POST', 'DELETE'])
def push_view(request):
    if request.method == 'GET':
        return Response({'configurado': push.configurado(), 'publica': settings.VAPID_PUBLICA or None,
                         'suscripciones': SuscripcionPush.objects.filter(usuario=request.user).count()})
    datos = request.data.get('suscripcion') or {}
    endpoint = str(datos.get('endpoint') or '')
    if request.method == 'DELETE':
        SuscripcionPush.objects.filter(usuario=request.user, endpoint=endpoint).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    claves = datos.get('keys') or {}
    if not push.endpoint_valido(endpoint) or not claves.get('p256dh') or not claves.get('auth'):
        raise exceptions.ValidationError({'suscripcion': 'Suscripción no válida.'})
    if not push.configurado():
        raise exceptions.ValidationError({'suscripcion': 'Las notificaciones aún no están configuradas en el servidor.'})
    otra = SuscripcionPush.objects.filter(endpoint=endpoint[:600]).exclude(usuario=request.user).first()
    if otra is not None:
        raise exceptions.ValidationError({'suscripcion': 'Este dispositivo está registrado a otra persona: que cierre su sesión primero.'})
    mias = SuscripcionPush.objects.filter(usuario=request.user)
    if not mias.filter(endpoint=endpoint[:600]).exists() and mias.count() >= push.MAX_POR_PERSONA:
        for vieja in mias.order_by('creada')[:mias.count() - push.MAX_POR_PERSONA + 1]:
            vieja.delete()  # se quedan los 5 dispositivos más recientes
    SuscripcionPush.objects.update_or_create(endpoint=endpoint[:600], usuario=request.user, defaults={
        'p256dh': str(claves['p256dh'])[:200], 'auth': str(claves['auth'])[:100],
        'navegador': (request.META.get('HTTP_USER_AGENT') or '')[:200]})
    push.enviar(request.user.pk, 'Avisos activados', 'Así te llegarán las tareas, entregas y recordatorios.', '/')
    return Response({'ok': True}, status=status.HTTP_201_CREATED)
