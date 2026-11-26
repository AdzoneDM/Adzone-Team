import mimetypes
import os

from django.contrib.auth.models import User
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.archivos import entregar, es_video
from apps.desempeno.permisos import es_administrador

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
    puede_ver_vistos = serializers.SerializerMethodField()
    editable_hasta = serializers.SerializerMethodField()
    archivo = serializers.SerializerMethodField()
    menciones = serializers.SerializerMethodField()
    responde_a = serializers.SerializerMethodField()

    class Meta:
        model = Mensaje
        fields = ['id', 'conversacion', 'autor', 'autor_nombre', 'texto', 'archivo', 'menciones', 'creado', 'eliminado', 'puede_borrar', 'puede_ver_vistos',
                  'editado_en', 'editable_hasta', 'responde_a']

    def get_responde_a(self, o):
        """La cita del mensaje al que responde (texto recortado; nada del contenido si el original se borró)."""
        r = o.responde_a
        if o.eliminado or r is None:
            return None
        if r.eliminado:
            return {'id': r.id, 'autor': r.autor_id, 'autor_nombre': self.get_autor_nombre(r), 'texto': '', 'eliminado': True, 'archivo': None}
        archivo = None
        if r.archivo or r.archivo_purgado:
            archivo = {'nombre': r.archivo_nombre, 'es_imagen': r.archivo_es_imagen and not r.archivo_purgado}
        texto = r.texto if len(r.texto) <= 300 else r.texto[:300] + '…'
        return {'id': r.id, 'autor': r.autor_id, 'autor_nombre': self.get_autor_nombre(r), 'texto': texto, 'eliminado': False, 'archivo': archivo}

    def get_archivo(self, o):
        if o.eliminado:
            return None
        nombre = o.archivo_nombre or (o.archivo.name if o.archivo else '')
        es_zip = nombre.lower().endswith('.zip')
        if o.archivo_purgado:
            return {'nombre': o.archivo_nombre, 'es_imagen': False, 'es_video': not es_zip, 'es_zip': es_zip, 'purgado': True, 'tamano': o.archivo_tamano}
        if not o.archivo:
            return None
        datos = {'nombre': o.archivo_nombre, 'es_imagen': o.archivo_es_imagen, 'es_video': es_video(nombre), 'tamano': o.archivo_tamano}
        if es_zip:
            datos.update({'es_zip': True, 'items': o.archivo_items, 'revisado': o.archivo_escaneo == 'LIMPIO'})
        return datos

    def get_autor_nombre(self, o):
        return (o.autor.get_full_name() or o.autor.username) if o.autor else 'Persona eliminada'

    def get_texto(self, o):
        return '' if o.eliminado else o.texto

    def get_menciones(self, o):
        return [] if o.eliminado else (o.menciones or [])

    def get_editable_hasta(self, o):
        """Hasta cuándo puede editarlo quien lo pidió (None si no puede): la pantalla esconde «Editar» a esa hora."""
        if o.eliminado or o.autor_id != self.context['request'].user.id:
            return None
        from datetime import timedelta
        return o.creado + timedelta(minutes=servicios.MINUTOS_EDITAR)

    def get_puede_ver_vistos(self, o):
        return servicios.puede_ver_vistos(self.context['request'].user, o)

    def get_puede_borrar(self, o):
        return servicios.puede_borrar(self.context['request'].user, o)


class NuevoMensaje(serializers.Serializer):
    texto = serializers.CharField(max_length=LIMITE_TEXTO, trim_whitespace=True, required=False, allow_blank=True, default='')
    responde_a = serializers.IntegerField(required=False, allow_null=True, default=None)


def _serializar(request, qs):
    return MensajeSerializer(qs.select_related('autor', 'conversacion', 'responde_a__autor'), many=True, context={'request': request}).data


def _con_lectores(request, conv, datos):
    """Agrega a la respuesta quién ya leyó hasta dónde (para el «visto» de tus mensajes)."""
    leyeron, total = servicios.lectores(conv, request.user)
    return datos | {'lectores': leyeron, 'participantes': total}


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
    elif c.tipo == Conversacion.GRUPO:
        d.update(titulo=c.nombre, persona=None, grupo=_grupo(usuario, c, detalle=False))
    else:
        p = servicios.persona(c.otro(usuario))
        d.update(titulo=p['nombre'], persona=p)
    return d


def _grupo(usuario, c, detalle=True):
    g = {'nombre': c.nombre, 'departamento': c.departamento.nombre if c.departamento_id else None, 'departamento_id': c.departamento_id,
         'creado_por': (c.creado_por.get_full_name() or c.creado_por.username) if c.creado_por_id else None,
         'puede_gestionar': servicios.puede_gestionar_grupo(usuario, c), 'n_miembros': c.miembros.count()}
    if detalle:
        g['miembros'] = [servicios.persona(u) for u in c.miembros.filter(is_active=True).select_related('perfil__puesto_trabajo__departamento').order_by('first_name', 'last_name')]
    return g


@api_view(['GET', 'POST'])
def conversaciones_view(request):
    """GET: la sala de la empresa y mis chats privados, lo más reciente primero.
    POST {persona: id}: abre (o recupera) el chat privado con esa persona."""
    if request.method == 'POST':
        otro = get_object_or_404(User, pk=_entero(request.data.get('persona'), 0), is_active=True)
        if otro.id == request.user.id:
            return Response({'detail': 'No puedes abrir un chat contigo mismo.'}, status=status.HTTP_400_BAD_REQUEST)
        from apps.core.permisos import ve_a
        if not ve_a(request.user, otro):
            raise PermissionDenied('No puedes escribirle a esa persona.')
        c = servicios.privado_con(request.user, otro)
        return Response(_ficha(request.user, c, servicios.no_leidos_por_conversacion(request.user, [c])))
    servicios.sala_global()
    convs = list(servicios.conversaciones_de(request.user).select_related('a', 'b', 'a__perfil__puesto_trabajo__departamento', 'b__perfil__puesto_trabajo__departamento'))
    # Un privado sin mensajes no estorba en la lista (se abrió pero nunca se escribió); un grupo nuevo sí aparece
    convs = [c for c in convs if c.tipo in (Conversacion.GLOBAL, Conversacion.GRUPO) or c.ultimo_id]
    leidos = servicios.no_leidos_por_conversacion(request.user, convs)
    fichas = [_ficha(request.user, c, leidos) for c in convs]
    fichas.sort(key=lambda f: (f['tipo'] != Conversacion.GLOBAL, -(f['ultima_actividad'].timestamp() if f['ultima_actividad'] else 0)))
    return Response({'conversaciones': fichas, 'no_leidos': sum(leidos.values()), 'puede_crear_grupos': servicios.puede_crear_grupos(request.user),
                     'departamentos': servicios.departamentos_para_grupos(request.user)})


@api_view(['GET'])
def personas_view(request):
    """Directorio para empezar un chat: personas activas, con su cargo y departamento."""
    return Response([servicios.persona(u) for u in servicios.personas_para_chatear(request.user, request.query_params.get('q', '').strip()[:60])])


def _departamento_o_none(valor):
    from apps.core.models import Departamento
    pk = _entero(valor)
    return get_object_or_404(Departamento, pk=pk) if pk else None


def _miembros(valor):
    if isinstance(valor, str):
        valor = [v for v in valor.split(',') if v.strip()]
    return [_entero(v) for v in (valor or []) if _entero(v)]


@api_view(['POST'])
def grupos_view(request):
    """Crear un grupo (por área o con las personas que elijas). Solo las jefaturas: se valida aquí, no solo en la pantalla."""
    if not servicios.puede_crear_grupos(request.user):
        return Response({'detail': 'Solo las jefaturas pueden crear grupos de chat.'}, status=status.HTTP_403_FORBIDDEN)
    c = servicios.crear_grupo(request.user, request.data.get('nombre'), _departamento_o_none(request.data.get('departamento')), _miembros(request.data.get('miembros')))
    return Response(_ficha(request.user, c, {}), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
def grupo_view(request, pk):
    """GET: datos y participantes (cualquier participante). PATCH y DELETE: solo quien administra el grupo."""
    from django.http import Http404
    c = servicios.conversacion_de(request.user, pk)
    if c is None and es_administrador(request.user):  # Dirección administra todos los grupos, aunque no participe en ellos
        c = Conversacion.objects.filter(pk=pk, tipo=Conversacion.GRUPO).first()
    if c is None or c.tipo != Conversacion.GRUPO:
        raise Http404
    if request.method == 'GET':
        return Response(_ficha(request.user, c, {}) | {'grupo': _grupo(request.user, c)})
    if not servicios.puede_gestionar_grupo(request.user, c):
        return Response({'detail': 'Solo quien administra el grupo (su creador o Dirección) puede cambiarlo o eliminarlo.'}, status=status.HTTP_403_FORBIDDEN)
    if request.method == 'DELETE':
        for m in c.mensajes.exclude(archivo=''):
            m.archivo.delete(save=False)
        c.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    if 'nombre' in request.data:
        nombre = (request.data.get('nombre') or '').strip()
        if len(nombre) < 3:
            return Response({'nombre': ['Ponle un nombre al grupo (mínimo 3 letras).']}, status=status.HTTP_400_BAD_REQUEST)
        c.nombre = nombre[:80]
    if 'departamento' in request.data:
        c.departamento = _departamento_o_none(request.data.get('departamento'))
    c.save(update_fields=['nombre', 'departamento'])
    if 'miembros' in request.data:
        personas = set(User.objects.filter(pk__in=_miembros(request.data.get('miembros')), is_active=True).values_list('pk', flat=True))
        if request.user.pk not in personas and c.creado_por_id == request.user.pk:
            personas.add(request.user.pk)  # quien administra el grupo no se saca a sí mismo por accidente
        if len(personas) < 2:
            return Response({'miembros': ['Un grupo necesita al menos dos personas.']}, status=status.HTTP_400_BAD_REQUEST)
        c.miembros.set(personas)
    return Response(_ficha(request.user, c, {}) | {'grupo': _grupo(request.user, c)})


@api_view(['GET'])
def archivo_view(request, pk):
    """El archivo de un mensaje, solo para quienes participan en esa conversación (verlo en pantalla o descargarlo)."""
    m = get_object_or_404(Mensaje.objects.select_related('conversacion'), pk=pk)
    _conversacion_o_404(request, m.conversacion_id)
    if m.eliminado or not m.archivo:
        if m.archivo_purgado:
            return Response({'detail': 'Este video se borró solo para liberar espacio.'}, status=status.HTTP_410_GONE)
        from django.http import Http404
        raise Http404
    tipo = mimetypes.guess_type(m.archivo.name)[0] or 'application/octet-stream'
    if request.query_params.get('descargar') == '1':
        servicios.registrar_abierto(request.user, m)   # descargarlo cuenta como abrirlo
    if es_video(m.archivo_nombre or m.archivo.name):  # los videos se entregan por tramos (se reproducen y avanzan sin bajarlos completos)
        return entregar(m.archivo.open('rb'), m.archivo_nombre or os.path.basename(m.archivo.name), tipo, request)
    if (m.archivo_nombre or m.archivo.name).lower().endswith('.zip'):
        # Se valida otra vez antes de entregarlo: siempre como descarga, sin que el navegador lo interprete ni lo abra
        with m.archivo.open('rb') as f:
            if f.read(4) not in (b'PK\x03\x04', b'PK\x05\x06'):
                return Response({'detail': 'Este archivo ya no es un ZIP válido y no se entrega.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        resp = FileResponse(m.archivo.open('rb'), filename=m.archivo_nombre or 'archivo.zip', content_type='application/zip', as_attachment=True)
        resp['X-Content-Type-Options'] = 'nosniff'
        resp['Content-Security-Policy'] = "sandbox; default-src 'none'"
        return resp
    resp = FileResponse(m.archivo.open('rb'), filename=m.archivo_nombre or os.path.basename(m.archivo.name), content_type=tipo,
                        as_attachment=request.query_params.get('descargar') == '1' or not m.archivo_es_imagen and tipo != 'application/pdf')
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp


@api_view(['GET', 'POST'])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def mensajes_view(request, pk):
    """GET: ?despues=<id> trae lo nuevo; ?antes=<id> trae lo anterior; sin nada, lo más reciente.
    POST: envía un mensaje a esta conversación."""
    conv = _conversacion_o_404(request, pk)
    if request.method == 'POST':
        datos = NuevoMensaje(data=request.data)
        datos.is_valid(raise_exception=True)
        archivo = request.FILES.get('archivo')
        if not datos.validated_data['texto'] and not archivo:
            return Response({'texto': ['Escribe un mensaje o adjunta un archivo.']}, status=status.HTTP_400_BAD_REQUEST)
        es_imagen = servicios.revisar_archivo(archivo) if archivo else False
        if servicios.excede_ritmo(request.user):
            return Response({'detail': 'Estás escribiendo muy rápido. Espera unos segundos.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        responde_a = None
        if datos.validated_data.get('responde_a'):
            # Solo se responde a un mensaje de esta misma conversación (y que no esté borrado)
            responde_a = Mensaje.objects.filter(pk=datos.validated_data['responde_a'], conversacion=conv, eliminado=False).first()
            if responde_a is None:
                return Response({'responde_a': ['Ese mensaje ya no está disponible para responder.']}, status=status.HTTP_400_BAD_REQUEST)
        m = Mensaje.objects.create(conversacion=conv, autor=request.user, texto=datos.validated_data['texto'], responde_a=responde_a)
        if archivo:
            m.archivo, m.archivo_nombre, m.archivo_es_imagen, m.archivo_tamano = archivo, archivo.name[:150], es_imagen, archivo.size
            info = getattr(archivo, '_zip_info', None)   # solo ZIP: cuántos archivos trae y si el antivirus lo revisó
            if info:
                m.archivo_items, m.archivo_escaneo = info['items'], info['escaneo']
            m.save(update_fields=['archivo', 'archivo_nombre', 'archivo_es_imagen', 'archivo_tamano', 'archivo_items', 'archivo_escaneo'])
        servicios.registrar(m)
        servicios.avisar_menciones(m)
        servicios.marcar_leido(request.user, conv, m.id)
        return Response(MensajeSerializer(m, context={'request': request}).data, status=status.HTTP_201_CREATED)

    limite = max(1, min(_entero(request.query_params.get('limite'), servicios.PAGINA), servicios.PAGINA_MAX))
    despues = _entero(request.query_params.get('despues'))
    antes = _entero(request.query_params.get('antes'))
    qs = Mensaje.objects.filter(conversacion=conv)
    if despues is not None:
        # Lo nuevo, en orden; el cliente reconcilia por id (así se reflejan también los borrados)
        from datetime import timedelta
        from django.db.models import Q
        from django.utils import timezone as tz
        ids = list(qs.filter(Q(id__gt=despues) | Q(editado_en__gte=tz.now() - timedelta(minutes=servicios.MINUTOS_EDITAR + 2)))
                   .values_list('id', flat=True)[:servicios.PAGINA_MAX * 2])
        nuevos = Mensaje.objects.filter(id__in=ids)
        servicios.registrar_entregados(request.user, nuevos)
        return Response(_con_lectores(request, conv, {'mensajes': _serializar(request, nuevos), 'hay_mas': False}))
    if antes is not None:
        qs = qs.filter(id__lt=antes)
    ids = list(qs.order_by('-id').values_list('id', flat=True)[:limite + 1])
    pagina = Mensaje.objects.filter(id__in=ids[:limite])
    servicios.registrar_entregados(request.user, pagina)
    return Response(_con_lectores(request, conv, {'mensajes': _serializar(request, pagina), 'hay_mas': len(ids) > limite}))


@api_view(['DELETE', 'PATCH'])
def mensaje_view(request, pk):
    """DELETE: borra tu mensaje. PATCH {texto}: lo edita (solo el tuyo y solo durante 5 minutos desde que lo enviaste)."""
    m = get_object_or_404(Mensaje.objects.select_related('conversacion'), pk=pk)
    _conversacion_o_404(request, m.conversacion_id)
    if request.method == 'PATCH':
        if m.autor_id != request.user.id:
            return Response({'detail': 'Solo puedes editar tus propios mensajes.'}, status=status.HTTP_403_FORBIDDEN)
        if not servicios.puede_editar(request.user, m):
            return Response({'detail': f'Ya pasaron los {servicios.MINUTOS_EDITAR} minutos para editar este mensaje.'}, status=status.HTTP_403_FORBIDDEN)
        datos = NuevoMensaje(data=request.data)
        datos.is_valid(raise_exception=True)
        texto = datos.validated_data['texto']
        if not texto and not m.archivo_nombre:
            return Response({'texto': ['El mensaje no puede quedar vacío (si ya no hace falta, bórralo).']}, status=status.HTTP_400_BAD_REQUEST)
        if texto != m.texto:
            servicios.editar(m, texto)
        return Response(MensajeSerializer(m, context={'request': request}).data)
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


@api_view(['GET'])
def vistos_view(request, pk):
    """Quién vio el mensaje (con fecha y hora), quién lo tiene pendiente y, si trae archivo, quién lo abrió.
    Lo consulta quien lo envió, quien administra el grupo y Dirección."""
    m = get_object_or_404(Mensaje.objects.select_related('conversacion'), pk=pk)
    _conversacion_o_404(request, m.conversacion_id)
    if not servicios.puede_ver_vistos(request.user, m):
        raise PermissionDenied('Solo quien envió el mensaje (o quien administra el grupo) ve quién lo leyó.')
    return Response(servicios.vistos_de(m))


@api_view(['POST'])
def abierto_view(request, pk):
    """La persona abrió, reprodujo o descargó el archivo de este mensaje: queda como evidencia."""
    m = get_object_or_404(Mensaje.objects.select_related('conversacion'), pk=pk)
    _conversacion_o_404(request, m.conversacion_id)
    servicios.registrar_abierto(request.user, m)
    return Response({'ok': True})
