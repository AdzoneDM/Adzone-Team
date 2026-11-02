import io
import mimetypes
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import authentication, exceptions, serializers, viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.asistencia import servicios as asistencia
from apps.desempeno.permisos import EsAdministrador, equipo_gestionable, es_administrador, puede_gestionar
from apps.desempeno.views import periodo_desde_mes
from . import servicios
from .models import Actividad, Captura, ConfiguracionMonitoreo, Consentimiento, Dispositivo, Justificacion, ReglaProductividad


def _ip(request):
    return (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')) or None


def _fecha(texto):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return timezone.localdate()


def _quien(request):
    """La persona consultada: uno mismo, o alguien de su equipo si lo gestiona."""
    if not request.query_params.get('usuario'):
        return request.user
    if not str(request.query_params['usuario']).isdigit():
        raise exceptions.ValidationError({'usuario': 'Debe ser un número.'})
    u = get_object_or_404(User, pk=request.query_params['usuario'])
    if u.pk != request.user.pk and not puede_gestionar(request.user, u):
        raise exceptions.PermissionDenied("Solo ves la actividad de tu equipo.")
    return u


# ------------------------------------------------------------------ Agente de escritorio
class DispositivoAuth(authentication.BaseAuthentication):
    """Cabecera «Authorization: Dispositivo adz_…». El token se muestra una sola vez al vincular la computadora."""

    def authenticate(self, request):
        cabecera = request.META.get('HTTP_AUTHORIZATION', '')
        if not cabecera.startswith('Dispositivo '):
            return None
        token = cabecera.split(' ', 1)[1].strip()
        d = Dispositivo.objects.select_related('usuario').filter(token_hash=Dispositivo.hash(token)).first()
        if d is None or not d.activo or not d.usuario.is_active:
            raise exceptions.AuthenticationFailed('Equipo no vinculado o desactivado.')
        return d.usuario, d

    def authenticate_header(self, request):
        return 'Dispositivo'


def _dispositivo(request):
    if not isinstance(request.auth, Dispositivo):
        raise exceptions.NotAuthenticated('Falta el token del equipo.')
    d = request.auth
    d.ultimo_contacto = timezone.now()
    d.version_agente = (request.data.get('version') if request.method == 'POST' else request.query_params.get('version')) or d.version_agente
    d.sistema = (request.data.get('sistema') if request.method == 'POST' else request.query_params.get('sistema')) or d.sistema
    d.save(update_fields=['ultimo_contacto', 'version_agente', 'sistema'])
    return d


@api_view(['GET'])
@authentication_classes([DispositivoAuth])
@permission_classes([AllowAny])
def agente_estado_view(request):
    return Response(servicios.estado_agente(_dispositivo(request)))


@api_view(['POST'])
@authentication_classes([DispositivoAuth])
@permission_classes([AllowAny])
def agente_actividad_view(request):
    d = _dispositivo(request)
    minutos = request.data.get('minutos') or []
    if not isinstance(minutos, list):
        return Response({'detail': 'Formato no válido.'}, status=400)
    guardados, descartados = servicios.ingestar(d, minutos)
    return Response({'guardados': guardados, 'descartados': descartados, 'estado': servicios.estado_agente(d)})


@api_view(['POST'])
@authentication_classes([DispositivoAuth])
@permission_classes([AllowAny])
def agente_marcar_view(request):
    d = _dispositivo(request)
    if request.data.get('tipo') not in ('ENTRADA', 'PAUSA', 'REGRESO', 'SALIDA'):
        return Response({'detail': 'Marcaje no válido.'}, status=400)
    marcaje, error = asistencia.marcar(d.usuario, request.data.get('tipo'), 'AGENTE', _ip(request), request.data.get('motivo') or '')
    if error:
        return Response({'detail': error}, status=400)
    return Response(servicios.estado_agente(d), status=201)


@api_view(['POST'])
@authentication_classes([DispositivoAuth])
@permission_classes([AllowAny])
def agente_captura_view(request):
    d = _dispositivo(request)
    estado = servicios.estado_agente(d)
    if not estado['capturas']:
        return Response({'detail': 'Capturas apagadas o fuera de jornada.'}, status=409)
    archivo = request.FILES.get('archivo')
    if not archivo or archivo.size > 3 * 1024 * 1024:
        return Response({'detail': 'Falta la imagen o pasa de 3 MB.'}, status=400)
    try:
        from PIL import Image, ImageFilter
        img = Image.open(archivo)
        if img.width * img.height > 40_000_000:  # pantallas de hasta ~8K; más es sospechoso
            return Response({'detail': 'Imagen demasiado grande.'}, status=400)
        img.draft('RGB', (1600, 1600))
        img = img.convert('RGB')
        img.thumbnail((1600, 1600))
        if estado['desenfocar']:
            img = img.filter(ImageFilter.GaussianBlur(6))
        salida = io.BytesIO()
        img.save(salida, 'JPEG', quality=60)
    except Exception:
        return Response({'detail': 'La imagen no se pudo leer.'}, status=400)
    from django.core.files.base import ContentFile
    c = Captura(usuario=d.usuario, dispositivo=d, tomada_en=timezone.now(), desenfocada=estado['desenfocar'],
                app=(request.data.get('app') or '')[:100])
    c.archivo.save('captura.jpg', ContentFile(salida.getvalue()), save=True)
    return Response({'ok': True}, status=201)


# ------------------------------------------------------------------ Política y consentimiento
@api_view(['GET', 'POST'])
def politica_view(request):
    config = ConfiguracionMonitoreo.actual()
    if request.method == 'POST':
        Consentimiento.objects.get_or_create(usuario=request.user, version=config.version_politica, defaults={'ip': _ip(request)})
    ultimo = Consentimiento.objects.filter(usuario=request.user, version=config.version_politica).first()
    return Response({'version': config.version_politica, 'texto': config.texto_politica, 'aceptada': bool(ultimo),
                     'aceptada_en': ultimo.aceptado_en if ultimo else None, 'capturas': config.capturas})


# ------------------------------------------------------------------ Dispositivos
class DispositivoSerializer(serializers.ModelSerializer):
    persona = serializers.SerializerMethodField()

    class Meta:
        model = Dispositivo
        fields = ['id', 'usuario', 'persona', 'nombre', 'sistema', 'version_agente', 'prefijo', 'activo', 'creado', 'ultimo_contacto']
        read_only_fields = ['sistema', 'version_agente', 'prefijo', 'creado', 'ultimo_contacto']

    def get_persona(self, obj):
        return obj.usuario.get_full_name() or obj.usuario.username


class DispositivoViewSet(viewsets.ModelViewSet):
    """Cada quien ve sus equipos; la administración ve y vincula todos. El token sale una sola vez al crear."""
    serializer_class = DispositivoSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        qs = Dispositivo.objects.select_related('usuario')
        return qs if es_administrador(self.request.user) else qs.filter(usuario=self.request.user)

    def create(self, request, *args, **kwargs):
        usuario = request.user
        if request.data.get('usuario') and str(request.data['usuario']) != str(request.user.pk):
            if not es_administrador(request.user):
                raise exceptions.PermissionDenied("Solo la administración vincula equipos de otras personas.")
            usuario = get_object_or_404(User, pk=request.data['usuario'], is_active=True)
        nombre = (request.data.get('nombre') or '').strip() or 'Computadora'
        d, token = Dispositivo.crear(usuario, nombre)
        return Response({**DispositivoSerializer(d).data, 'token': token}, status=201)

    def perform_update(self, serializer):
        if not es_administrador(self.request.user):
            raise exceptions.PermissionDenied("Solo la administración edita equipos.")
        serializer.save(usuario=serializer.instance.usuario)  # un equipo no cambia de dueño

    def perform_destroy(self, instance):
        """Desvincular = desactivar. La actividad y las capturas ya registradas se conservan (nadie borra su historial)."""
        instance.activo = False
        instance.save(update_fields=['activo'])


# ------------------------------------------------------------------ Reglas y configuración
class ReglaSerializer(serializers.ModelSerializer):
    departamento_nombre = serializers.CharField(source='departamento.nombre', read_only=True, default=None)

    class Meta:
        model = ReglaProductividad
        fields = ['id', 'tipo', 'patron', 'categoria', 'departamento', 'departamento_nombre', 'nota']

    def validate_patron(self, v):
        v = v.strip()
        if len(v) < 2:
            raise serializers.ValidationError('Escribe al menos 2 letras.')
        return v


class ReglaViewSet(viewsets.ModelViewSet):
    queryset = ReglaProductividad.objects.select_related('departamento')
    serializer_class = ReglaSerializer

    def get_permissions(self):
        return [EsAdministrador()] if self.request.method not in ('GET', 'HEAD', 'OPTIONS') else super().get_permissions()


class ConfigSerializer(serializers.ModelSerializer):
    MINIMOS = {'umbral_inactivo_seg': 30, 'capturas_cada_min': 1, 'alerta_inactivo_min': 5, 'alerta_sin_pc_min': 5,
               'retencion_dias': 7, 'retencion_capturas_dias': 1}

    class Meta:
        model = ConfiguracionMonitoreo
        exclude = ['id']

    def validate(self, data):
        errores = {k: f'Mínimo {m}.' for k, m in self.MINIMOS.items() if k in data and data[k] < m}
        errores.update({k: 'Máximo 100.' for k in ('alerta_improductivo_pct', 'meta_productividad_pct') if k in data and data[k] > 100})
        if errores:
            raise serializers.ValidationError(errores)
        return data


@api_view(['GET', 'PATCH'])
@permission_classes([EsAdministrador])
def configuracion_view(request):
    config = ConfiguracionMonitoreo.actual()
    if request.method == 'PATCH':
        s = ConfigSerializer(config, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
    return Response(ConfigSerializer(config).data)


@api_view(['POST'])
@permission_classes([EsAdministrador])
def reclasificar_view(request):
    try:
        dias = max(1, min(int(request.data.get('dias') or 30), 90))
    except (TypeError, ValueError):
        return Response({'detail': 'Días no válidos.'}, status=400)
    desde = timezone.now() - timedelta(days=dias)
    return Response({'cambiados': servicios.reclasificar(desde)})


# ------------------------------------------------------------------ Consultas
@api_view(['GET'])
def dia_view(request):
    u = _quien(request)
    dia = _fecha(request.query_params.get('fecha'))
    r = servicios.resumen_dia(u, dia)
    capturas = Captura.objects.filter(usuario=u, tomada_en__range=asistencia.rango(dia)).order_by('tomada_en')
    r['capturas'] = [{'id': c.id, 'hora': timezone.localtime(c.tomada_en).strftime('%H:%M'), 'app': c.app, 'desenfocada': c.desenfocada}
                     for c in capturas]
    puesto = getattr(getattr(u, 'perfil', None), 'puesto_trabajo', None)
    r['persona'] = {'id': u.id, 'nombre': u.get_full_name() or u.username, 'puesto': puesto.nombre if puesto else None}
    r['fecha'] = dia
    r['equipos'] = [{'nombre': d.nombre, 'ultimo_contacto': d.ultimo_contacto} for d in u.dispositivos.filter(activo=True)]
    r['consentimiento'] = servicios.consintio(u)
    return Response(r)


@api_view(['GET'])
def periodo_view(request):
    u = _quien(request)
    desde, hasta = asistencia.mes(periodo_desde_mes(request.query_params.get('mes')))
    return Response(servicios.resumen_periodo(u, desde, hasta))


@api_view(['GET'])
def equipo_view(request):
    """En vivo: quién está trabajando, con qué app, y cómo va su día."""
    personas = equipo_gestionable(request.user).select_related('perfil__puesto_trabajo__departamento').order_by('first_name')
    if not es_administrador(request.user) and not personas.exists():
        raise exceptions.PermissionDenied("Esta vista es para supervisores y administración.")
    dia = _fecha(request.query_params.get('fecha'))
    ids = [p.pk for p in personas]
    contacto = servicios.ultimo_contacto_por_usuario(ids) if dia == timezone.localdate() else {}
    con_equipo = set(Dispositivo.objects.filter(usuario_id__in=ids, activo=True).values_list('usuario_id', flat=True))
    consentidos = set(Consentimiento.objects.filter(usuario_id__in=ids, version=ConfiguracionMonitoreo.actual().version_politica)
                      .values_list('usuario_id', flat=True))
    por_usuario = {}
    for a in Actividad.objects.filter(usuario_id__in=ids, minuto__range=asistencia.rango(dia)).order_by('minuto'):
        por_usuario.setdefault(a.usuario_id, []).append(a)
    filas = []
    for u in personas:
        j = asistencia.jornada(u, dia)
        r = servicios._resumir(por_usuario.get(u.pk, []), j['trabajados'])
        puesto = getattr(getattr(u, 'perfil', None), 'puesto_trabajo', None)
        filas.append({
            'id': u.pk, 'nombre': u.get_full_name() or u.username, 'puesto': puesto.nombre if puesto else None,
            'departamento': puesto.departamento.nombre if puesto else None,
            'jornada': j['estado'], 'llegada': j['llegada'], 'entrada': j['entrada'], 'trabajados': j['trabajados'],
            'tiene_equipo': u.pk in con_equipo, 'consentimiento': u.pk in consentidos, 'ahora': contacto.get(u.pk),
            **{k: r[k] for k in ('minutos_registrados', 'minutos_activos', 'actividad', 'productividad', 'improductividad',
                                 'intensidad', 'minutos_foco', 'cambios_por_hora', 'cobertura')},
            'app_principal': r['apps'][0]['nombre'] if r['apps'] else None,
        })
    return Response({'fecha': dia, 'personas': filas})


@api_view(['GET'])
def captura_view(request, pk):
    c = get_object_or_404(Captura.objects.select_related('usuario'), pk=pk)
    if c.usuario_id != request.user.pk and not puede_gestionar(request.user, c.usuario):
        raise Http404
    try:
        f = c.archivo.open('rb')
    except (FileNotFoundError, ValueError):
        raise Http404
    r = FileResponse(f, content_type=mimetypes.guess_type(c.archivo.name)[0] or 'image/jpeg')
    r['Cache-Control'] = 'private, max-age=3600'
    return r


# ------------------------------------------------------------------ Productividad por proyecto y OT
@api_view(['GET'])
def proyectos_view(request):
    from apps.desempeno.puntaje import rango_del_mes
    from apps.operaciones.permisos import es_finanzas
    from .proyectos import productividad
    admin = es_administrador(request.user)
    equipo = list(equipo_gestionable(request.user).values_list('pk', flat=True))
    if not admin and not equipo:
        raise exceptions.PermissionDenied("Esta vista es para supervisores y administración.")
    desde, hasta = rango_del_mes(periodo_desde_mes(request.query_params.get('mes')))
    usuarios = None if admin else equipo + [request.user.pk]
    datos = productividad(desde, hasta, usuarios=usuarios, con_costos=es_finanzas(request.user))
    return Response({'desde': desde, 'hasta': hasta, 'con_costos': es_finanzas(request.user), **datos})


# ------------------------------------------------------------------ Justificaciones
class JustificacionSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    revisada_por_nombre = serializers.SerializerMethodField()
    tarea_titulo = serializers.CharField(source='tarea.titulo', read_only=True, default=None)
    resumen = serializers.SerializerMethodField()

    class Meta:
        model = Justificacion
        fields = ['id', 'usuario', 'usuario_nombre', 'desde', 'hasta', 'motivo', 'tarea', 'tarea_titulo', 'estado',
                  'revisada_por_nombre', 'nota', 'minutos', 'creada', 'resumen']
        read_only_fields = ['usuario', 'estado', 'nota', 'minutos']

    def get_usuario_nombre(self, o):
        return o.usuario.get_full_name() or o.usuario.username

    def get_revisada_por_nombre(self, o):
        return (o.revisada_por.get_full_name() or o.revisada_por.username) if o.revisada_por else None

    def get_resumen(self, o):
        """Qué hay en ese tramo, para que el supervisor decida."""
        from collections import Counter
        filas = Actividad.objects.filter(usuario=o.usuario, minuto__gte=o.desde, minuto__lt=o.hasta)
        cats = Counter(filas.values_list('categoria', flat=True))
        apps = Counter(filas.values_list('app', flat=True)).most_common(3)
        return {'minutos': sum(cats.values()), 'productivos': cats.get('P', 0), 'neutrales': cats.get('N', 0),
                'improductivos': cats.get('I', 0), 'apps': [a or 'Desconocida' for a, _ in apps]}

    def validate(self, data):
        desde, hasta = data.get('desde'), data.get('hasta')
        if desde and hasta:
            if hasta <= desde:
                raise serializers.ValidationError({'hasta': 'El final es antes del inicio.'})
            if hasta - desde > timedelta(hours=10):
                raise serializers.ValidationError({'hasta': 'Justifica tramos de 10 horas como máximo.'})
            if desde < timezone.now() - timedelta(days=15):
                raise serializers.ValidationError({'desde': 'Solo se justifican los últimos 15 días.'})
        return data


class JustificacionViewSet(viewsets.ModelViewSet):
    serializer_class = JustificacionSerializer
    http_method_names = ['get', 'post']

    def get_queryset(self):
        u = self.request.user
        qs = Justificacion.objects.select_related('usuario', 'revisada_por', 'tarea')
        if self.request.query_params.get('ver') == 'equipo':
            qs = qs.filter(usuario__in=equipo_gestionable(u)).exclude(usuario=u)
            estado = self.request.query_params.get('estado')
            return qs.filter(estado=estado) if estado else qs
        return qs.filter(usuario=u)

    def perform_create(self, serializer):
        from apps.desempeno.permisos import revisores_de
        from apps.desempeno.servicios import avisar
        j = serializer.save(usuario=self.request.user)
        nombre = self.request.user.get_full_name() or self.request.user.username
        avisar(revisores_de(self.request.user), 'MONITOREO', f'{nombre} justificó un tramo de su computadora', j.motivo[:200],
               enlace='/monitoreo?ver=justificaciones', excepto=self.request.user)


@api_view(['POST'])
def revisar_justificacion_view(request, pk):
    j = get_object_or_404(Justificacion, pk=pk)
    if j.usuario_id == request.user.pk or not puede_gestionar(request.user, j.usuario):
        raise exceptions.PermissionDenied("La revisa su supervisor.")
    if j.estado != 'PENDIENTE':
        return Response({'detail': 'Ya se revisó.'}, status=400)
    servicios.justificar(j, bool(request.data.get('aprobar')), request.user, request.data.get('nota') or '')
    return Response(JustificacionSerializer(j).data)
