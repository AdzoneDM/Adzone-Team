from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import servicios
from .models import LIMITE_TEXTO, Mensaje


def _entero(valor, defecto=None):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


class MensajeSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.SerializerMethodField()
    texto = serializers.SerializerMethodField()
    puede_borrar = serializers.SerializerMethodField()

    class Meta:
        model = Mensaje
        fields = ['id', 'autor', 'autor_nombre', 'texto', 'creado', 'eliminado', 'puede_borrar']

    def get_autor_nombre(self, o):
        return (o.autor.get_full_name() or o.autor.username) if o.autor else 'Persona eliminada'

    def get_texto(self, o):
        return '' if o.eliminado else o.texto

    def get_puede_borrar(self, o):
        return servicios.puede_borrar(self.context['request'].user, o)


class NuevoMensaje(serializers.Serializer):
    texto = serializers.CharField(max_length=LIMITE_TEXTO, trim_whitespace=True)


def _serializar(request, qs):
    return MensajeSerializer(qs.select_related('autor'), many=True, context={'request': request}).data


@api_view(['GET', 'POST'])
def mensajes_view(request):
    """GET: ?despues=<id> trae lo nuevo; ?antes=<id> trae lo anterior; sin nada, lo más reciente.
    POST: envía un mensaje."""
    if request.method == 'POST':
        datos = NuevoMensaje(data=request.data)
        datos.is_valid(raise_exception=True)
        if servicios.excede_ritmo(request.user):
            return Response({'detail': 'Estás escribiendo muy rápido. Espera unos segundos.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        m = Mensaje.objects.create(autor=request.user, texto=datos.validated_data['texto'])
        servicios.marcar_leido(request.user, m.id)
        return Response(MensajeSerializer(m, context={'request': request}).data, status=status.HTTP_201_CREATED)

    limite = max(1, min(_entero(request.query_params.get('limite'), servicios.PAGINA), servicios.PAGINA_MAX))
    despues = _entero(request.query_params.get('despues'))
    antes = _entero(request.query_params.get('antes'))
    qs = Mensaje.objects.all()
    if despues is not None:
        # Lo nuevo, en orden; también refleja los mensajes borrados desde entonces (el cliente lo reconcilia por id).
        lista = list(qs.filter(id__gt=despues)[:servicios.PAGINA_MAX * 2])
        return Response({'mensajes': _serializar(request, Mensaje.objects.filter(id__in=[m.id for m in lista])), 'hay_mas': False})
    if antes is not None:
        qs = qs.filter(id__lt=antes)
    pagina = list(qs.order_by('-id')[:limite + 1])
    hay_mas = len(pagina) > limite
    ids = [m.id for m in pagina[:limite]]
    return Response({'mensajes': _serializar(request, Mensaje.objects.filter(id__in=ids)), 'hay_mas': hay_mas})


@api_view(['DELETE'])
def mensaje_view(request, pk):
    m = get_object_or_404(Mensaje, pk=pk)
    if not servicios.puede_borrar(request.user, m):
        return Response({'detail': 'Solo puedes borrar tus propios mensajes.'}, status=status.HTTP_403_FORBIDDEN)
    m.eliminado, m.eliminado_por = True, request.user
    m.save(update_fields=['eliminado', 'eliminado_por'])
    return Response(MensajeSerializer(m, context={'request': request}).data)


@api_view(['GET'])
def resumen_view(request):
    """Liviano: lo único que la campanita del chat consulta con el chat cerrado."""
    return Response({'no_leidos': servicios.no_leidos(request.user), 'ultimo_id': servicios.ultimo_id()})


@api_view(['POST'])
def leido_view(request):
    hasta = _entero(request.data.get('hasta'), 0)
    servicios.marcar_leido(request.user, max(hasta, 0))
    return Response({'no_leidos': servicios.no_leidos(request.user)})
