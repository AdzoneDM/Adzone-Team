from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import exceptions, serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.desempeno.permisos import EsAdministrador, TienePermiso, equipo_gestionable, es_administrador, puede_gestionar, tiene


def _rrhh(user):
    from .politicas import es_rrhh
    return es_rrhh(user)
from apps.desempeno.servicios import avisar
from . import servicios
from .models import COMPETENCIAS, ESCALA, AuditoriaCambio, CambioSalarial, CicloEvaluacion, EventoExpediente, Evaluacion, PlanMejora


def _nombre(u):
    return (u.get_full_name() or u.username) if u else None


def _persona_param(request, campo='usuario'):
    valor = request.query_params.get(campo)
    if not valor:
        return None
    if not str(valor).isdigit():
        raise exceptions.ValidationError({campo: 'Debe ser un número.'})
    return get_object_or_404(User, pk=valor)


def _puede_ver(request, persona):
    if persona.pk != request.user.pk and not (_rrhh(request.user) or puede_gestionar(request.user, persona, 'equipo.ver')):
        raise exceptions.PermissionDenied("Solo ves la información de tu equipo.")


# ------------------------------------------------------------------ Ciclos de evaluación
class CicloSerializer(serializers.ModelSerializer):
    avance = serializers.SerializerMethodField()

    class Meta:
        model = CicloEvaluacion
        fields = ['id', 'nombre', 'tipo', 'desde', 'hasta', 'cierre', 'con_pares', 'abierto', 'avance']

    def get_avance(self, obj):
        total = obj.evaluaciones.count()
        hechas = obj.evaluaciones.exclude(estado='PENDIENTE').count()
        return {'total': total, 'hechas': hechas}

    def validate(self, data):
        desde, hasta = data.get('desde', getattr(self.instance, 'desde', None)), data.get('hasta', getattr(self.instance, 'hasta', None))
        if desde and hasta and hasta < desde:
            raise serializers.ValidationError({'hasta': 'El final es antes del inicio.'})
        return data


class CicloViewSet(viewsets.ModelViewSet):
    queryset = CicloEvaluacion.objects.all()
    serializer_class = CicloSerializer
    http_method_names = ['get', 'post', 'patch']

    def get_permissions(self):
        return [TienePermiso.de('talento.rrhh')()] if self.request.method not in ('GET', 'HEAD', 'OPTIONS') else super().get_permissions()

    def perform_create(self, serializer):
        ciclo = serializer.save(creado_por=self.request.user)
        servicios.generar(ciclo)


# ------------------------------------------------------------------ Evaluaciones
class EvaluacionSerializer(serializers.ModelSerializer):
    evaluado_nombre = serializers.SerializerMethodField()
    evaluador_nombre = serializers.SerializerMethodField()
    ciclo_nombre = serializers.CharField(source='ciclo.nombre', read_only=True)
    puesto = serializers.SerializerMethodField()
    promedio = serializers.FloatField(read_only=True)

    class Meta:
        model = Evaluacion
        fields = ['id', 'ciclo', 'ciclo_nombre', 'evaluado', 'evaluado_nombre', 'puesto', 'evaluador', 'evaluador_nombre', 'tipo',
                  'estado', 'puntajes', 'fortalezas', 'a_mejorar', 'comentario', 'enviada', 'promedio', 'nota_revision']

    def get_evaluado_nombre(self, obj):
        return _nombre(obj.evaluado)

    def get_evaluador_nombre(self, obj):
        return _nombre(obj.evaluador)

    def get_puesto(self, obj):
        p = getattr(getattr(obj.evaluado, 'perfil', None), 'puesto_trabajo', None)
        return p.nombre if p else None


@api_view(['GET'])
def mis_evaluaciones_view(request):
    """Las que me toca hacer (incluida mi autoevaluación) en ciclos abiertos."""
    qs = Evaluacion.objects.filter(evaluador=request.user, ciclo__abierto=True).select_related('evaluado__perfil__puesto_trabajo', 'evaluador', 'ciclo')
    return Response({'evaluaciones': EvaluacionSerializer(qs, many=True).data,
                     'competencias': [{'clave': c, 'nombre': n} for c, n in COMPETENCIAS], 'escala': ESCALA})


@api_view(['POST'])
def enviar_evaluacion_view(request, pk):
    e = get_object_or_404(Evaluacion, pk=pk)
    if e.evaluador_id != request.user.pk:
        raise exceptions.PermissionDenied("Esta evaluación no te toca.")
    d = request.data
    error = servicios.enviar(e, d.get('puntajes') if isinstance(d.get('puntajes'), dict) else {}, d.get('fortalezas') or '',
                             d.get('a_mejorar') or '', d.get('comentario') or '')
    if error:
        return Response({'detail': error}, status=400)
    return Response(EvaluacionSerializer(e).data)


@api_view(['GET'])
@permission_classes([TienePermiso.de('talento.rrhh')])
def por_revisar_view(request):
    qs = Evaluacion.objects.filter(estado='EN_REVISION').exclude(evaluado=request.user).select_related('evaluado__perfil__puesto_trabajo', 'evaluador', 'ciclo')
    return Response(EvaluacionSerializer(qs, many=True).data)


@api_view(['POST'])
@permission_classes([TienePermiso.de('talento.rrhh')])
def confirmar_evaluacion_view(request, pk):
    """La dirección confirma (o devuelve al evaluador) una evaluación baja antes de que la vea la persona."""
    e = get_object_or_404(Evaluacion, pk=pk, estado='EN_REVISION')
    if e.evaluado_id == request.user.pk:
        raise exceptions.PermissionDenied("Tu propia evaluación la valida otra persona de la dirección.")
    nota = str(request.data.get('nota') or '')[:255]
    if request.data.get('devolver'):
        e.estado = 'PENDIENTE'
        e.nota_revision = nota
        e.save(update_fields=['estado', 'nota_revision'])
        avisar([e.evaluador], 'TALENTO', f'Revisa de nuevo la evaluación de {_nombre(e.evaluado)}', nota, enlace='/talento?ver=evaluar', excepto=request.user)
    else:
        e.estado = 'CERRADA'
        e.revisada_por = request.user
        e.nota_revision = nota
        e.save(update_fields=['estado', 'revisada_por', 'nota_revision'])
    return Response(EvaluacionSerializer(e).data)


@api_view(['GET'])
def resultados_view(request):
    persona = _persona_param(request) or request.user
    _puede_ver(request, persona)
    ciclos = CicloEvaluacion.objects.filter(evaluaciones__evaluado=persona).distinct()
    if request.query_params.get('ciclo', '').isdigit():
        ciclos = ciclos.filter(pk=request.query_params['ciclo'])
    return Response({'persona': {'id': persona.pk, 'nombre': _nombre(persona)},
                     'ciclos': [servicios.resultados(c, persona, anonimo=True) for c in ciclos[:8]]})


@api_view(['GET'])
def avance_view(request):
    """Para la dirección y supervisores: quién falta por evaluar en el ciclo."""
    ciclo = get_object_or_404(CicloEvaluacion, pk=request.query_params.get('ciclo') or 0) if str(request.query_params.get('ciclo', '')).isdigit() else CicloEvaluacion.objects.first()
    if ciclo is None:
        return Response({'ciclo': None, 'personas': []})
    from django.contrib.auth.models import User as _U
    equipo = _U.objects.filter(is_active=True) if _rrhh(request.user) else equipo_gestionable(request.user, 'equipo.evaluar')
    filas = []
    for u in equipo.filter(perfil__puesto_trabajo__isnull=False).order_by('first_name'):
        evs = list(Evaluacion.objects.filter(ciclo=ciclo, evaluado=u))
        if not evs:
            continue
        sup = [e.promedio for e in evs if e.tipo == 'SUPERVISOR' and e.estado in ('ENVIADA', 'CERRADA') and e.promedio]
        filas.append({'id': u.pk, 'nombre': _nombre(u), 'total': len(evs), 'hechas': sum(1 for e in evs if e.estado != 'PENDIENTE'),
                      'en_revision': sum(1 for e in evs if e.estado == 'EN_REVISION'),
                      'supervisor': round(sum(sup) / len(sup), 2) if sup else None})
    return Response({'ciclo': CicloSerializer(ciclo).data, 'personas': filas})


# ------------------------------------------------------------------ Planes de mejora
class PlanSerializer(serializers.ModelSerializer):
    colaborador_nombre = serializers.SerializerMethodField()
    creado_por_nombre = serializers.SerializerMethodField()
    kpi_nombre = serializers.CharField(source='kpi.nombre', read_only=True, default=None)

    class Meta:
        model = PlanMejora
        fields = ['id', 'colaborador', 'colaborador_nombre', 'creado_por_nombre', 'motivo', 'kpi', 'kpi_nombre', 'objetivos',
                  'capacitacion', 'inicio', 'revision', 'estado', 'resultado', 'creado']

    def get_colaborador_nombre(self, obj):
        return _nombre(obj.colaborador)

    def get_creado_por_nombre(self, obj):
        return _nombre(obj.creado_por)

    def validate_objetivos(self, v):
        if not isinstance(v, list) or not v:
            raise serializers.ValidationError('Agrega al menos un objetivo.')
        limpios = []
        for o in v:
            if not isinstance(o, dict) or not str(o.get('texto', '')).strip():
                raise serializers.ValidationError('Cada objetivo necesita texto.')
            limpios.append({'texto': str(o['texto'])[:300], 'meta': str(o.get('meta') or '')[:120],
                            'fecha': str(o.get('fecha') or '')[:10], 'cumplido': bool(o.get('cumplido'))})
        return limpios

    def validate(self, data):
        inicio, revision = data.get('inicio', getattr(self.instance, 'inicio', None)), data.get('revision', getattr(self.instance, 'revision', None))
        if inicio and revision and revision < inicio:
            raise serializers.ValidationError({'revision': 'La revisión es antes del inicio.'})
        return data


class PlanViewSet(viewsets.ModelViewSet):
    serializer_class = PlanSerializer
    http_method_names = ['get', 'post', 'patch']

    def get_queryset(self):
        u = self.request.user
        qs = PlanMejora.objects.select_related('colaborador', 'creado_por', 'kpi')
        persona = _persona_param(self.request)
        if persona:
            _puede_ver(self.request, persona)
            return qs.filter(colaborador=persona)
        if _rrhh(u):
            return qs
        return qs.filter(Q(colaborador=u) | Q(colaborador__in=equipo_gestionable(u, 'equipo.ver')))

    def _gestiona(self, colaborador):
        if colaborador.pk == self.request.user.pk or not (_rrhh(self.request.user) or puede_gestionar(self.request.user, colaborador, 'equipo.evaluar')):
            raise exceptions.PermissionDenied("Los planes de mejora los abre y sigue el supervisor o la dirección.")

    def perform_create(self, serializer):
        self._gestiona(serializer.validated_data['colaborador'])
        plan = serializer.save(creado_por=self.request.user)
        avisar([plan.colaborador], 'TALENTO', 'Tienes un plan de mejora', f'Revisión el {plan.revision:%d/%m}.',
               enlace='/ficha', excepto=self.request.user)

    def perform_update(self, serializer):
        self._gestiona(serializer.instance.colaborador)
        serializer.save(colaborador=serializer.instance.colaborador)


# ------------------------------------------------------------------ Expediente
class EventoSerializer(serializers.ModelSerializer):
    registrado_por_nombre = serializers.SerializerMethodField()
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = EventoExpediente
        fields = ['id', 'colaborador', 'tipo', 'tipo_nombre', 'fecha', 'titulo', 'descripcion', 'monto', 'horas',
                  'visible_al_colaborador', 'justificacion', 'registrado_por_nombre', 'creado']

    def get_registrado_por_nombre(self, obj):
        return _nombre(obj.registrado_por)

    def to_representation(self, obj):
        d = super().to_representation(obj)
        if not tiene(self.context['request'].user, 'personal.salarios'):
            d['monto'] = None  # los montos de bonos solo los ve quien maneja salarios
        return d


class ExpedienteViewSet(viewsets.ModelViewSet):
    serializer_class = EventoSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        u = self.request.user
        if self.action != 'list':
            # Detalle, edición y borrado: lo propio visible y lo del equipo que gestiono.
            base = EventoExpediente.objects.select_related('registrado_por')
            if _rrhh(u):
                return base
            return base.filter(Q(colaborador=u, visible_al_colaborador=True) | Q(colaborador__in=equipo_gestionable(u, 'equipo.ver')))
        persona = _persona_param(self.request) or u
        _puede_ver(self.request, persona)
        qs = EventoExpediente.objects.filter(colaborador=persona).select_related('registrado_por')
        return qs.filter(visible_al_colaborador=True) if persona.pk == u.pk and not es_administrador(u) else qs

    def _registra(self, colaborador):
        return _rrhh(self.request.user) or puede_gestionar(self.request.user, colaborador, 'equipo.expediente')

    def perform_create(self, serializer):
        c = serializer.validated_data['colaborador']
        if c.pk == self.request.user.pk or not self._registra(c):
            raise exceptions.PermissionDenied("Lo registra quien tiene ese permiso sobre la persona o Gestión del Talento.")
        if serializer.validated_data.get('tipo') == 'BONO' and not tiene(self.request.user, 'personal.salarios'):
            raise exceptions.PermissionDenied("Los bonos los registra quien maneja salarios.")
        e = serializer.save(registrado_por=self.request.user)
        if e.visible_al_colaborador:
            avisar([c], 'TALENTO', f'{e.get_tipo_display()}: {e.titulo}', e.descripcion[:300], enlace='/ficha', excepto=self.request.user)

    def perform_update(self, serializer):
        e = serializer.instance
        if e.colaborador_id == self.request.user.pk:
            # La persona solo puede escribir su descargo o justificación.
            extra = set(serializer.validated_data) - {'justificacion'}
            if extra:
                raise exceptions.PermissionDenied("Solo puedes agregar tu justificación.")
            serializer.save()
            return
        if not self._registra(e.colaborador):
            raise exceptions.PermissionDenied("No puedes editar este registro.")
        d = serializer.validated_data
        if not tiene(self.request.user, 'personal.salarios') and (e.tipo == 'BONO' or d.get('tipo') == 'BONO' or 'monto' in d):
            raise exceptions.PermissionDenied("Los bonos y sus montos los maneja quien maneja salarios.")
        serializer.save(colaborador=e.colaborador)

    def perform_destroy(self, instance):
        if not _rrhh(self.request.user) or instance.colaborador_id == self.request.user.pk:
            raise exceptions.PermissionDenied("Solo Gestión del Talento borra registros del expediente (nunca del suyo).")
        instance.delete()


# ------------------------------------------------------------------ Salario y auditoría (administración)
@api_view(['GET'])
@permission_classes([TienePermiso.de('personal.salarios')])
def salarios_view(request):
    persona = _persona_param(request)
    qs = CambioSalarial.objects.select_related('usuario', 'registrado_por')
    if persona:
        qs = qs.filter(usuario=persona)
    return Response([{'id': c.id, 'persona': _nombre(c.usuario), 'fecha': c.fecha, 'anterior': c.anterior, 'nuevo': c.nuevo,
                      'motivo': c.motivo, 'registrado_por': _nombre(c.registrado_por)} for c in qs[:200]])


@api_view(['GET'])
@permission_classes([TienePermiso.de('auditoria.ver')])
def auditoria_view(request):
    qs = AuditoriaCambio.objects.select_related('usuario')
    texto = request.query_params.get('q', '').strip()
    if texto:
        qs = qs.filter(Q(accion__icontains=texto) | Q(objeto__icontains=texto) | Q(usuario__first_name__icontains=texto))
    if request.query_params.get('desde'):
        from django.utils.dateparse import parse_date
        desde = parse_date(request.query_params['desde'])
        if desde is None:
            raise exceptions.ValidationError({'desde': 'Formato esperado: AAAA-MM-DD.'})
        qs = qs.filter(fecha__date__gte=desde)
    salarios, rrhh = tiene(request.user, 'personal.salarios'), tiene(request.user, 'talento.rrhh')
    return Response([_fila_auditoria(a, salarios, rrhh) for a in qs[:300]])


SALARIALES = ('salario_mensual', 'costo_hora', 'nomina', 'monto', 'salario_anterior', 'salario_nuevo')


def _reservar(valores, salarios):
    if not isinstance(valores, dict) or salarios:
        return valores
    return {k: ('reservado' if k in SALARIALES else v) for k, v in valores.items()}


def _fila_auditoria(a, salarios, rrhh):
    """Quien no maneja salarios no ve montos; quien no es Gestión del Talento no ve el contenido de expedientes ni documentos."""
    if not rrhh and 'expediente' in a.accion.lower():
        return {'id': a.id, 'fecha': a.fecha, 'usuario': _nombre(a.usuario), 'accion': a.accion, 'objeto': 'reservado',
                'antes': None, 'despues': None}
    return {'id': a.id, 'fecha': a.fecha, 'usuario': _nombre(a.usuario), 'accion': a.accion, 'objeto': a.objeto,
            'antes': _reservar(a.antes, salarios), 'despues': _reservar(a.despues, salarios)}


# ------------------------------------------------------------------ Políticas
import csv  # noqa: E402

from django.http import FileResponse, Http404, HttpResponse  # noqa: E402
from rest_framework.decorators import action  # noqa: E402
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser  # noqa: E402

from . import politicas as pol  # noqa: E402
from .models import AceptacionPolitica, DocumentoEmpleado, Politica, VersionPolitica  # noqa: E402


class EsRRHH(EsAdministrador):
    def has_permission(self, request, view):
        return pol.es_rrhh(request.user)


def _ip(request):
    return (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')) or None


class PoliticaSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='get_categoria_display', read_only=True)
    aceptada = serializers.SerializerMethodField()
    aceptada_en = serializers.SerializerMethodField()

    class Meta:
        model = Politica
        fields = ['id', 'clave', 'titulo', 'categoria', 'categoria_nombre', 'resumen', 'contenido', 'version', 'vigente_desde',
                  'para_todos', 'departamentos', 'puestos', 'requiere_aceptacion', 'activa', 'borrador', 'actualizada',
                  'aceptada', 'aceptada_en']
        read_only_fields = ['version', 'vigente_desde', 'actualizada']
        extra_kwargs = {'clave': {'required': False}}

    def _aceptacion(self, o):
        u = self.context['request'].user
        cache = self.context.setdefault('_acept', {})
        if u.pk not in cache:
            cache[u.pk] = {(a.politica_id, a.version): a.fecha for a in AceptacionPolitica.objects.filter(usuario=u)}
        return cache[u.pk].get((o.pk, o.version))

    def get_aceptada(self, o):
        return self._aceptacion(o) is not None

    def get_aceptada_en(self, o):
        return self._aceptacion(o)

    def validate(self, data):
        p = self.instance
        if p is not None and (not p.borrador or p.aceptaciones.exists()):
            for campo in ('contenido', 'titulo'):
                if campo in data and data[campo] != getattr(p, campo):
                    raise serializers.ValidationError({campo: 'Una política publicada se cambia con «Nueva versión», para que todos la acepten de nuevo.'})
            if data.get('borrador'):
                raise serializers.ValidationError({'borrador': 'Una política publicada no vuelve a borrador; desactívala si ya no aplica.'})
        return data


class PoliticaViewSet(viewsets.ModelViewSet):
    serializer_class = PoliticaSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'aceptar', 'constancia'):
            return super().get_permissions()
        return [EsRRHH()]

    def get_queryset(self):
        u = self.request.user
        qs = Politica.objects.prefetch_related('puestos', 'departamentos')
        if pol.es_rrhh(u):
            return qs
        visibles = [p.pk for p, _ in pol.de_usuario(u)]
        return qs.filter(pk__in=visibles)

    def perform_create(self, serializer):
        from django.utils.text import slugify
        base = (serializer.validated_data.get('clave') or slugify(serializer.validated_data['titulo']) or 'politica')[:36]
        clave, n = base, 2
        while Politica.objects.filter(clave=clave).exists():
            clave, n = f'{base}-{n}', n + 1
        p = serializer.save(creada_por=self.request.user, clave=clave)
        VersionPolitica.objects.create(politica=p, version=1, titulo=p.titulo, contenido=p.contenido, cambio='Versión inicial', por=self.request.user)
        if not p.borrador and p.activa:
            pol.avisar_publicacion(p, self.request.user)

    def perform_update(self, serializer):
        antes = serializer.instance.borrador
        p = serializer.save()
        if p.borrador and not p.aceptaciones.exists():  # mientras es borrador sin aceptar, la versión sigue al texto
            VersionPolitica.objects.filter(politica=p, version=p.version).update(titulo=p.titulo, contenido=p.contenido)
        elif antes and p.activa:
            p.vigente_desde = timezone.localdate()
            p.save(update_fields=['vigente_desde'])
            pol.avisar_publicacion(p, self.request.user)

    def perform_destroy(self, instance):
        if not instance.borrador or instance.aceptaciones.exists():
            raise exceptions.ValidationError('Ya se publicó: desactívala en vez de borrarla, para conservar quién la aceptó.')
        instance.delete()

    @action(detail=True, methods=['post'])
    def aceptar(self, request, pk=None):
        p = self.get_object()
        if p.borrador or not p.activa:
            return Response({'detail': 'Esta política no está publicada.'}, status=400)
        leida = request.data.get('version')
        if leida is not None and str(leida) != str(p.version):
            return Response({'detail': 'La política cambió mientras la leías. Vuelve a abrirla para leer la versión nueva.'}, status=409)
        a = pol.aceptar(p, request.user, _ip(request), request.META.get('HTTP_USER_AGENT', ''))
        return Response({'aceptada': True, 'version': a.version, 'fecha': a.fecha})

    @action(detail=True, methods=['post'], url_path='nueva-version')
    def nueva_version(self, request, pk=None):
        p = self.get_object()
        contenido = str(request.data.get('contenido') or '').strip()
        if not contenido:
            return Response({'contenido': 'Escribe el texto de la nueva versión.'}, status=400)
        pol.nueva_version(p, str(request.data.get('titulo') or '').strip()[:150], contenido, request.data.get('cambio'), request.user)
        return Response(self.get_serializer(p).data)

    @action(detail=True, methods=['get'])
    def versiones(self, request, pk=None):
        p = self.get_object()
        return Response([{'version': v.version, 'titulo': v.titulo, 'cambio': v.cambio, 'fecha': v.fecha, 'contenido': v.contenido,
                          'por': _nombre(v.por), 'aceptaron': p.aceptaciones.filter(version=v.version).count()} for v in p.versiones.all()])

    @action(detail=True, methods=['get'])
    def constancia(self, request, pk=None):
        """El texto exacto que aceptó una persona, con fecha, IP y versión (para imprimir o guardar en PDF)."""
        p = get_object_or_404(Politica, pk=pk)
        persona = _persona_param(request) or request.user
        if persona.pk != request.user.pk and not pol.es_rrhh(request.user):
            raise exceptions.PermissionDenied("Solo Gestión del Talento ve las constancias de otras personas.")
        a = AceptacionPolitica.objects.filter(politica=p, usuario=persona).order_by('-version').first()
        if a is None:
            raise Http404
        v = VersionPolitica.objects.filter(politica=p, version=a.version).first()
        return Response({'politica': p.titulo, 'version': a.version, 'contenido': v.contenido if v else p.contenido, 'persona': _nombre(persona),
                         'fecha': a.fecha, 'ip': a.ip, 'navegador': a.navegador})


@api_view(['GET'])
def politicas_pendientes_view(request):
    return Response([{'id': p.pk, 'titulo': p.titulo, 'version': p.version} for p in pol.pendientes(request.user)])


@api_view(['GET'])
@permission_classes([EsRRHH])
def cumplimiento_view(request):
    filas = pol.cumplimiento()
    if request.query_params.get('formato') == 'csv':
        r = HttpResponse(content_type='text/csv; charset=utf-8')
        r['Content-Disposition'] = 'attachment; filename="cumplimiento-politicas.csv"'
        r.write('﻿')
        w = csv.writer(r)
        w.writerow(['Política', 'Versión', 'Personas', 'Aceptaron', '%', 'Pendientes'])
        for f in filas:
            w.writerow([f['titulo'], f['version'], f['personas'], f['aceptaron'], f['porcentaje'] if f['porcentaje'] is not None else '',
                        '; '.join(x['nombre'] for x in f['faltan'])])
        return r
    return Response(filas)


# ------------------------------------------------------------------ Documentos del expediente
class DocumentoSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    subido_por_nombre = serializers.SerializerMethodField()
    vencido = serializers.SerializerMethodField()
    visible_al_colaborador = serializers.BooleanField(default=True)  # en un formulario, la casilla ausente no es «no»

    class Meta:
        model = DocumentoEmpleado
        fields = ['id', 'colaborador', 'tipo', 'tipo_nombre', 'titulo', 'archivo', 'emitido', 'vence', 'vencido', 'visible_al_colaborador',
                  'notas', 'subido_por_nombre', 'creado']
        extra_kwargs = {'archivo': {'write_only': True}}

    def get_subido_por_nombre(self, o):
        return _nombre(o.subido_por)

    def get_vencido(self, o):
        return bool(o.vence and o.vence < timezone.localdate())

    def validate_archivo(self, f):
        import os
        if f.size > 15 * 1024 * 1024:
            raise serializers.ValidationError('Máximo 15 MB.')
        if os.path.splitext(f.name)[1].lower() not in ('.pdf', '.jpg', '.jpeg', '.png', '.webp', '.docx', '.doc'):
            raise serializers.ValidationError('Sube un PDF, una imagen o un documento de Word.')
        return f


class DocumentoViewSet(viewsets.ModelViewSet):
    """Gestión del Talento sube y maneja los documentos; cada persona ve y descarga los suyos visibles. Los supervisores no."""
    serializer_class = DocumentoSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_permissions(self):
        return super().get_permissions() if self.action in ('list', 'retrieve', 'archivo') else [EsRRHH()]

    def get_queryset(self):
        u = self.request.user
        qs = DocumentoEmpleado.objects.select_related('colaborador', 'subido_por')
        propios = qs.filter(colaborador=u, visible_al_colaborador=True)
        if pol.es_rrhh(u):
            persona = _persona_param(self.request)
            if not es_administrador(u):
                # Gestión del Talento no ve ni toca lo oculto de su propio expediente.
                if persona and persona.pk == u.pk:
                    return propios
                qs = qs.exclude(colaborador=u) | propios
            return qs.filter(colaborador=persona) if persona else qs
        return propios

    def _no_propio(self, colaborador):
        if colaborador.pk == self.request.user.pk and not es_administrador(self.request.user):
            raise exceptions.PermissionDenied("Tu propio expediente lo maneja otra persona de Gestión del Talento o la administración.")

    def perform_create(self, serializer):
        self._no_propio(serializer.validated_data['colaborador'])
        serializer.save(subido_por=self.request.user)

    def perform_update(self, serializer):
        self._no_propio(serializer.instance.colaborador)
        viejo = serializer.instance.archivo.name if 'archivo' in serializer.validated_data else None
        d = serializer.save(colaborador=serializer.instance.colaborador)
        if viejo and viejo != d.archivo.name:
            d.archivo.storage.delete(viejo)

    def perform_destroy(self, instance):
        self._no_propio(instance.colaborador)
        nombre, storage = instance.archivo.name, instance.archivo.storage
        instance.delete()
        if nombre:
            storage.delete(nombre)  # copias de identificación y contratos no quedan en el disco

    @action(detail=True, methods=['get'])
    def archivo(self, request, pk=None):
        import mimetypes
        d = self.get_object()
        try:
            f = d.archivo.open('rb')
        except (FileNotFoundError, ValueError):
            raise Http404
        tipo = mimetypes.guess_type(d.archivo.name)[0] or 'application/octet-stream'
        from apps.core.archivos import entregar
        r = entregar(f, f'{d.titulo}{__import__("os").path.splitext(d.archivo.name)[1]}', tipo)
        r['Cache-Control'] = 'private, no-store'
        return r


@api_view(['GET'])
@permission_classes([EsRRHH])
def estado_documentos_view(request):
    return Response(pol.estado_documentos())


@api_view(['POST'])
def borrador_evaluacion_view(request, pk):
    """Borrador de fortalezas, aspectos a mejorar y comentario con los datos de la persona. Solo para quien evalúa, y se edita antes de enviar."""
    from apps.desempeno.inteligencia import borrador_evaluacion
    e = get_object_or_404(Evaluacion.objects.select_related('evaluado', 'evaluador'), pk=pk)
    if e.evaluador_id != request.user.pk:
        raise exceptions.PermissionDenied("El borrador es para quien hace esta evaluación.")
    if e.tipo == 'PAR':
        raise exceptions.ValidationError("En la evaluación de compañeros cuenta tu propia mirada: no hay borrador.")
    if e.estado != 'PENDIENTE':
        raise exceptions.ValidationError("Esta evaluación ya se envió.")
    from django.core.cache import cache
    clave = f'borrador-eval:{request.user.pk}:{timezone.now():%Y%m%d%H}'
    if cache.get_or_set(clave, 0, 3700) >= 20:
        raise exceptions.Throttled(detail="Pediste muchos borradores en esta hora. Intenta más tarde.")
    cache.incr(clave)
    b = borrador_evaluacion(e)
    b.pop('datos', None)
    return Response(b)
