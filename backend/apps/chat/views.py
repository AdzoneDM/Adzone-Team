from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import servicios
from .models import LIMITE_TEXTO, Conversacion, Mensaje


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
        fields = ['id', 'conversacion', 'autor', 'autor_nombre', 'texto', 'creado', 'eliminado', 'puede_borrar']

    def get_autor_nombre(self, o):
        return (o.autor.get_full_name() or o.autor.username) if o.autor else 'Persona eliminada'

    def get_texto(self, o):
        return '' if o.eliminado else o.texto

    def get_puede_borrar(self, o):
        return servicios.puede_borrar(self.context['request'].user, o)


class NuevoMensaje(serializers.Serializer):
    texto = serializers.CharField(max_length=LIMITE_TEXTO, trim_whitespace=True)


def _serializar(request, qs):
    return MensajeSerializer(qs.select_related('autor', 'conversacion'), many=True, context={'request': request}).data


def _conversacion_o_404(request, pk):
    c = servicios.conversacion_de(request.user, pk)
    if c is None:
        # Igual que si no existiera: no se revela que hay un chat entre otras dos personas
        from django.http import Http404
        raise Http404
    return c


def _ficha(usuario, c, no_leidos):
    d = {
        'id': c.id, 'tipo': c.tipo, 'ultimo_texto': c.ultimo_texto, 'ultimo_autor': c.ultimo_autor_id,
        'ultima_actividad': c.ultima_actividad, 'no_leidos': no_leidos.get(c.id, 0),
    }
    if c.tipo == Conversacion.GLOBAL:
        d.update(titulo='Chat de Adzone', persona=None)
    else:
        p = servicios.persona(c.otro(usuario))
        d.update(titulo=p['nombre'], persona=p)
    return d


@api_view(['GET', 'POST'])
def conversaciones_view(request):
    """GET: la sala de la empresa y mis chats privados, lo más reciente primero.
    POST {persona: id}: abre (o recupera) el chat privado con esa persona."""
    if request.method == 'POST':
        otro = get_object_or_404(User, pk=_entero(request.data.get('persona'), 0), is_active=True)
        if otro.id == request.user.id:
            return Response({'detail': 'No puedes abrir un chat contigo mismo.'}, status=status.HTTP_400_BAD_REQUEST)
        c = servicios.privado_con(request.user, otro)
        return Response(_ficha(request.user, c, servicios.no_leidos_por_conversacion(request.user, [c])))
    servicios.sala_global()
    convs = list(servicios.conversaciones_de(request.user).select_related('a', 'b', 'a__perfil__puesto_trabajo__departamento', 'b__perfil__puesto_trabajo__departamento'))
    # Un privado sin mensajes no estorba en la lista (se abrió pero nunca se escribió)
    convs = [c for c in convs if c.tipo == Conversacion.GLOBAL or c.ultimo_id]
    leidos = servicios.no_leidos_por_conversacion(request.user, convs)
    fichas = [_ficha(request.user, c, leidos) for c in convs]
    fichas.sort(key=lambda f: (f['tipo'] != Conversacion.GLOBAL, -(f['ultima_actividad'].timestamp() if f['ultima_actividad'] else 0)))
    return Response({'conversaciones': fichas, 'no_leidos': sum(leidos.values())})


@api_view(['GET'])
def personas_view(request):
    """Directorio para empezar un chat: personas activas, con su cargo y departamento."""
    return Response([servicios.persona(u) for u in servicios.personas_para_chatear(request.user, request.query_params.get('q', '').strip()[:60])])


@api_view(['GET', 'POST'])
def mensajes_view(request, pk):
    """GET: ?despues=<id> trae lo nuevo; ?antes=<id> trae lo anterior; sin nada, lo más reciente.
    POST: envía un mensaje a esta conversación."""
    conv = _conversacion_o_404(request, pk)
    if request.method == 'POST':
        datos = NuevoMensaje(data=request.data)
        datos.is_valid(raise_exception=True)
        if servicios.excede_ritmo(request.user):
            return Response({'detail': 'Estás escribiendo muy rápido. Espera unos segundos.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        m = Mensaje.objects.create(conversacion=conv, autor=request.user, texto=datos.validated_data['texto'])
        servicios.registrar(m)
        servicios.marcar_leido(request.user, conv, m.id)
        return Response(MensajeSerializer(m, context={'request': request}).data, status=status.HTTP_201_CREATED)

    limite = max(1, min(_entero(request.query_params.get('limite'), servicios.PAGINA), servicios.PAGINA_MAX))
    despues = _entero(request.query_params.get('despues'))
    antes = _entero(request.query_params.get('antes'))
    qs = Mensaje.objects.filter(conversacion=conv)
    if despues is not None:
        # Lo nuevo, en orden; el cliente reconcilia por id (así se reflejan también los borrados)
        ids = list(qs.filter(id__gt=despues).values_list('id', flat=True)[:servicios.PAGINA_MAX * 2])
        return Response({'mensajes': _serializar(request, Mensaje.objects.filter(id__in=ids)), 'hay_mas': False})
    if antes is not None:
        qs = qs.filter(id__lt=antes)
    ids = list(qs.order_by('-id').values_list('id', flat=True)[:limite + 1])
    return Response({'mensajes': _serializar(request, Mensaje.objects.filter(id__in=ids[:limite])), 'hay_mas': len(ids) > limite})


@api_view(['DELETE'])
def mensaje_view(request, pk):
    m = get_object_or_404(Mensaje.objects.select_related('conversacion'), pk=pk)
    _conversacion_o_404(request, m.conversacion_id)
    if not servicios.puede_borrar(request.user, m):
        return Response({'detail': 'Solo puedes borrar tus propios mensajes.'}, status=status.HTTP_403_FORBIDDEN)
    m.eliminado, m.eliminado_por = True, request.user
    m.save(update_fields=['eliminado', 'eliminado_por'])
    servicios.al_borrar(m)
    return Response(MensajeSerializer(m, context={'request': request}).data)


@api_view(['GET'])
def resumen_view(request):
    """Liviano: lo único que el botón del chat consulta con el chat cerrado."""
    servicios.sala_global()
    convs = list(servicios.conversaciones_de(request.user))
    leidos = servicios.no_leidos_por_conversacion(request.user, convs)
    return Response({'no_leidos': sum(leidos.values())})


@api_view(['POST'])
def leido_view(request, pk):
    conv = _conversacion_o_404(request, pk)
    servicios.marcar_leido(request.user, conv, max(_entero(request.data.get('hasta'), 0), 0))
    return Response({'no_leidos': servicios.no_leidos_por_conversacion(request.user, [conv]).get(conv.id, 0)})
