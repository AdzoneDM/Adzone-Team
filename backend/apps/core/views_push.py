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
    if not endpoint.startswith('https://') or not claves.get('p256dh') or not claves.get('auth'):
        raise exceptions.ValidationError({'suscripcion': 'Suscripción no válida.'})
    if not push.configurado():
        raise exceptions.ValidationError({'suscripcion': 'Las notificaciones aún no están configuradas en el servidor.'})
    SuscripcionPush.objects.update_or_create(endpoint=endpoint[:600], defaults={
        'usuario': request.user, 'p256dh': str(claves['p256dh'])[:200], 'auth': str(claves['auth'])[:100],
        'navegador': (request.META.get('HTTP_USER_AGENT') or '')[:200]})
    push.enviar(request.user.pk, 'Avisos activados', 'Así te llegarán las tareas, entregas y recordatorios.', '/')
    return Response({'ok': True}, status=status.HTTP_201_CREATED)
