from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import exceptions, serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.desempeno.permisos import EsAdministrador, equipo_gestionable, es_administrador, puede_gestionar
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
    if persona.pk != request.user.pk and not puede_gestionar(request.user, persona):
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
        return [EsAdministrador()] if self.request.method not in ('GET', 'HEAD', 'OPTIONS') else super().get_permissions()

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
@permission_classes([EsAdministrador])
def por_revisar_view(request):
    qs = Evaluacion.objects.filter(estado='EN_REVISION').exclude(evaluado=request.user).select_related('evaluado__perfil__puesto_trabajo', 'evaluador', 'ciclo')
    return Response(EvaluacionSerializer(qs, many=True).data)


@api_view(['POST'])
@permission_classes([EsAdministrador])
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
    equipo = equipo_gestionable(request.user)
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
        return qs.filter(Q(colaborador=u) | Q(colaborador__in=equipo_gestionable(u)))

    def _gestiona(self, colaborador):
        if colaborador.pk == self.request.user.pk or not puede_gestionar(self.request.user, colaborador):
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
        if not es_administrador(self.context['request'].user):
            d['monto'] = None  # los montos de bonos solo los ve la administración
        return d


class ExpedienteViewSet(viewsets.ModelViewSet):
    serializer_class = EventoSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        u = self.request.user
        if self.action != 'list':
            # Detalle, edición y borrado: lo propio visible y lo del equipo que gestiono.
            base = EventoExpediente.objects.select_related('registrado_por')
            if es_administrador(u):
                return base
            return base.filter(Q(colaborador=u, visible_al_colaborador=True) | Q(colaborador__in=equipo_gestionable(u)))
        persona = _persona_param(self.request) or u
        _puede_ver(self.request, persona)
        qs = EventoExpediente.objects.filter(colaborador=persona).select_related('registrado_por')
        return qs.filter(visible_al_colaborador=True) if persona.pk == u.pk and not es_administrador(u) else qs

    def perform_create(self, serializer):
        c = serializer.validated_data['colaborador']
        if c.pk == self.request.user.pk or not puede_gestionar(self.request.user, c):
            raise exceptions.PermissionDenied("Lo registra el supervisor o la administración.")
        if serializer.validated_data.get('tipo') == 'BONO' and not es_administrador(self.request.user):
            raise exceptions.PermissionDenied("Los bonos los registra la administración.")
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
        if not puede_gestionar(self.request.user, e.colaborador):
            raise exceptions.PermissionDenied("No puedes editar este registro.")
        d = serializer.validated_data
        if not es_administrador(self.request.user) and (e.tipo == 'BONO' or d.get('tipo') == 'BONO' or 'monto' in d):
            raise exceptions.PermissionDenied("Los bonos y sus montos los maneja la administración.")
        serializer.save(colaborador=e.colaborador)

    def perform_destroy(self, instance):
        if not es_administrador(self.request.user):
            raise exceptions.PermissionDenied("Solo la administración borra registros del expediente.")
        instance.delete()


# ------------------------------------------------------------------ Salario y auditoría (administración)
@api_view(['GET'])
@permission_classes([EsAdministrador])
def salarios_view(request):
    persona = _persona_param(request)
    qs = CambioSalarial.objects.select_related('usuario', 'registrado_por')
    if persona:
        qs = qs.filter(usuario=persona)
    return Response([{'id': c.id, 'persona': _nombre(c.usuario), 'fecha': c.fecha, 'anterior': c.anterior, 'nuevo': c.nuevo,
                      'motivo': c.motivo, 'registrado_por': _nombre(c.registrado_por)} for c in qs[:200]])


@api_view(['GET'])
@permission_classes([EsAdministrador])
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
    return Response([{'id': a.id, 'fecha': a.fecha, 'usuario': _nombre(a.usuario), 'accion': a.accion, 'objeto': a.objeto,
                      'antes': a.antes, 'despues': a.despues} for a in qs[:300]])
