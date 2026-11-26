from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import alertas, servicio
from .models import ConversacionIA, InformeIA

LIMITE_INFORMES_A_MANO = 5


def _mensaje(m):
    return {'id': m.id, 'rol': m.rol, 'texto': m.texto, 'herramientas': m.herramientas, 'creado': m.creado}


@api_view(['GET'])
def estado_view(request):
    from django.conf import settings
    return Response({'activo': servicio.activo(), 'modelo': settings.IA_MODELO, 'limite_diario': settings.IA_LIMITE_DIARIO,
                     'preguntas_hoy': servicio.preguntas_hoy(request.user),
                     'puede_ver': servicio.herramientas.Alcance(request.user).describir(),
                     'recibe_analisis': request.user in alertas.destinatarios()})


@api_view(['GET'])
def conversaciones_view(request):
    return Response([{'id': c.id, 'titulo': c.titulo, 'actualizada': c.actualizada}
                     for c in ConversacionIA.objects.filter(usuario=request.user)[:50]])


@api_view(['GET', 'DELETE'])
def conversacion_view(request, pk):
    c = get_object_or_404(ConversacionIA, pk=pk, usuario=request.user)   # cada quien solo ve las suyas
    if request.method == 'DELETE':
        c.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response({'id': c.id, 'titulo': c.titulo, 'mensajes': [_mensaje(m) for m in c.mensajes.filter(visible=True)]})


@api_view(['POST'])
def preguntar_view(request):
    conv = None
    if request.data.get('conversacion'):
        conv = get_object_or_404(ConversacionIA, pk=request.data['conversacion'], usuario=request.user)
    try:
        respuesta = servicio.preguntar(request.user, request.data.get('texto'), conv)
    except servicio.AsistenteNoConfigurado as e:
        return Response({'detail': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ValueError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'conversacion': respuesta.conversacion_id, 'titulo': respuesta.conversacion.titulo, 'respuesta': _mensaje(respuesta)})


@api_view(['GET', 'POST'])
def informe_view(request):
    """GET: el análisis más reciente de quien pregunta. POST: lo genera de nuevo ahora (pocas veces al día)."""
    if request.method == 'POST':
        if request.user not in alertas.destinatarios():
            return Response({'detail': 'El análisis diario es para Dirección y quien gestiona un área.'}, status=status.HTTP_403_FORBIDDEN)
        from django.core.cache import cache
        clave = f'informe-ia-{request.user.pk}-{timezone.localdate():%Y%m%d}'
        if cache.get(clave, 0) >= LIMITE_INFORMES_A_MANO:
            return Response({'detail': 'Ya actualizaste el análisis varias veces hoy.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        cache.set(clave, cache.get(clave, 0) + 1, 86400)
        i = alertas.generar_informe(request.user, avisar=False)
    else:
        i = InformeIA.objects.filter(usuario=request.user).first()
        if i is None:
            return Response({'informe': None})
    return Response({'informe': {'fecha': i.fecha, 'alertas': i.alertas, 'texto': i.texto, 'con_ia': i.con_ia, 'creado': i.creado}})
