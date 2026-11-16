"""
Disponibilidad, actividades adicionales y colaboración entre compañeros (12.4).

- Quien termina sus tareas avisa («Pedir más trabajo») y queda en espera de asignación hasta recibir una tarea.
- Mientras tanto registra actividades adicionales (documentación, estudio, capacitación, mejoras…): su supervisor
  las valida y cuentan como indicador (KPI «Actividades adicionales validadas»).
- Colaboración: alguien pide apoyo a un compañero (o se registra un apoyo ya dado); el supervisor de quien ayudó
  lo valida y cuenta en el KPI «Apoyos a compañeros validados». El trabajo en equipo no depende solo de las tareas.
"""
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from . import servicios
from .models import ActividadAdicional, Colaboracion, Tarea
from .permisos import equipo_gestionable, es_administrador, puede_revisar, puesto_de


def _nombre(u):
    return (u.get_full_name() or u.username) if u else None


def _depto(u):
    p = puesto_de(u) if u else None
    return p.departamento.nombre if p and p.departamento_id else None


def _depto_id(u):
    p = puesto_de(u) if u else None
    return p.departamento_id if p else None


def _entre_areas_permitido(u):
    """Las áreas están aisladas: entre departamentos solo coordina quien supervisa (o un administrador)."""
    from .permisos import puede_validar
    return es_administrador(u) or puede_validar(u)


# ---------------------------------------------------------------------------
# Actividades adicionales
# ---------------------------------------------------------------------------
class ActividadSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    departamento = serializers.SerializerMethodField()
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    validada_por_nombre = serializers.SerializerMethodField()
    puedo_validar = serializers.SerializerMethodField()

    class Meta:
        model = ActividadAdicional
        fields = ['id', 'usuario', 'usuario_nombre', 'departamento', 'fecha', 'tipo', 'tipo_nombre', 'descripcion',
                  'resultado', 'minutos', 'proyecto', 'estado', 'validada_por', 'validada_por_nombre',
                  'fecha_validacion', 'comentario_supervisor', 'puedo_validar', 'fecha_creacion']
        read_only_fields = ['usuario', 'estado', 'validada_por', 'fecha_validacion', 'comentario_supervisor']

    def get_usuario_nombre(self, o):
        return _nombre(o.usuario)

    def get_departamento(self, o):
        return _depto(o.usuario)

    def get_validada_por_nombre(self, o):
        return _nombre(o.validada_por)

    def get_puedo_validar(self, o):
        u = self.context['request'].user
        return o.usuario_id != u.pk and puede_revisar(u, o.usuario)

    def validate_minutos(self, v):
        if v > 12 * 60:
            raise serializers.ValidationError("Como mucho 12 horas por registro.")
        return v

    def validate_fecha(self, v):
        hoy = timezone.localdate()
        if v > hoy or (hoy - v).days > 31:
            raise serializers.ValidationError("La fecha debe ser de los últimos 31 días.")
        return v

    def validate_descripcion(self, v):
        if len((v or '').strip()) < 10:
            raise serializers.ValidationError("Cuenta qué hiciste (al menos 10 letras).")
        return v.strip()


class ActividadAdicionalViewSet(viewsets.ModelViewSet):
    """?ambito=mias (por defecto) | equipo | por_validar. Cada persona registra las suyas; su supervisor las valida."""
    serializer_class = ActividadSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        u = self.request.user
        qs = ActividadAdicional.objects.select_related('usuario', 'validada_por')
        ambito = self.request.query_params.get('ambito', 'mias')
        if self.action not in ('list', None):
            # Una sola actividad: la propia o la de alguien de su equipo (para validarla).
            if es_administrador(u):
                return qs
            return qs.filter(Q(usuario=u) | Q(usuario__in=equipo_gestionable(u, 'tareas.validar')))
        if ambito in ('equipo', 'por_validar'):
            if not es_administrador(u):
                qs = qs.filter(usuario__in=equipo_gestionable(u, 'tareas.validar'))
            qs = qs.exclude(usuario=u)
            if ambito == 'por_validar':
                qs = qs.filter(estado='REGISTRADA')
        elif ambito == 'persona' and self.request.query_params.get('usuario'):
            otro = User.objects.filter(pk=self.request.query_params['usuario']).first()
            if not otro or not (otro.pk == u.pk or es_administrador(u) or puede_revisar(u, otro)):
                return qs.none()
            qs = qs.filter(usuario=otro)
        else:
            qs = qs.filter(usuario=u)
        p = self.request.query_params
        if p.get('desde'):
            qs = qs.filter(fecha__gte=p['desde'])
        if p.get('hasta'):
            qs = qs.filter(fecha__lte=p['hasta'])
        return qs

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    def perform_update(self, serializer):
        a = serializer.instance
        if a.usuario_id != self.request.user.pk or a.estado != 'REGISTRADA':
            raise PermissionDenied("Solo se corrige una actividad propia que aún no se validó.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.usuario_id != self.request.user.pk or instance.estado != 'REGISTRADA':
            raise PermissionDenied("Solo se borra una actividad propia que aún no se validó.")
        instance.delete()

    def _revisar(self, request, aprobar):
        a = self.get_object()
        if a.usuario_id == request.user.pk or not puede_revisar(request.user, a.usuario):
            raise PermissionDenied("Solo su supervisor o un administrador la valida.")
        if a.estado != 'REGISTRADA':
            return Response({"detail": "Esta actividad ya se revisó."}, status=status.HTTP_400_BAD_REQUEST)
        comentario = (request.data.get('comentario') or '').strip()[:500]
        if not aprobar and len(comentario) < 5:
            return Response({"detail": "Explica por qué no se valida."}, status=status.HTTP_400_BAD_REQUEST)
        a.estado = 'VALIDADA' if aprobar else 'NO_VALIDADA'
        a.validada_por, a.fecha_validacion, a.comentario_supervisor = request.user, timezone.now(), comentario
        a.save()
        servicios.avisar([a.usuario], 'ACTIVIDAD',
                         f"{'Validada' if aprobar else 'No validada'}: {a.get_tipo_display()}",
                         comentario or f"{servicios.nombre(request.user)} validó tu actividad del {a.fecha:%d/%m}.",
                         enlace='/mis-tareas?ver=actividades', excepto=request.user)
        return Response(self.get_serializer(a).data)

    @action(detail=True, methods=['post'])
    def validar(self, request, pk=None):
        return self._revisar(request, True)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        return self._revisar(request, False)


# ---------------------------------------------------------------------------
# Colaboración entre compañeros
# ---------------------------------------------------------------------------
class ColaboracionSerializer(serializers.ModelSerializer):
    solicitante_nombre = serializers.SerializerMethodField()
    ayudante_nombre = serializers.SerializerMethodField()
    solicitante_departamento = serializers.SerializerMethodField()
    ayudante_departamento = serializers.SerializerMethodField()
    tarea_titulo = serializers.SerializerMethodField()
    validada_por_nombre = serializers.SerializerMethodField()
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    yo = serializers.SerializerMethodField()

    class Meta:
        model = Colaboracion
        fields = ['id', 'solicitante', 'solicitante_nombre', 'solicitante_departamento', 'ayudante', 'ayudante_nombre',
                  'ayudante_departamento', 'tarea', 'tarea_titulo', 'proyecto', 'descripcion', 'resultado', 'minutos',
                  'estado', 'estado_nombre', 'motivo', 'validada_por', 'validada_por_nombre', 'fecha_validacion',
                  'fecha_realizada', 'fecha_creacion', 'yo']
        read_only_fields = ['estado', 'motivo', 'validada_por', 'fecha_validacion', 'fecha_realizada']

    def get_solicitante_nombre(self, o):
        return _nombre(o.solicitante)

    def get_ayudante_nombre(self, o):
        return _nombre(o.ayudante)

    def get_solicitante_departamento(self, o):
        return _depto(o.solicitante)

    def get_ayudante_departamento(self, o):
        return _depto(o.ayudante)

    def get_tarea_titulo(self, o):
        return o.tarea.titulo if o.tarea_id else None

    def get_validada_por_nombre(self, o):
        return _nombre(o.validada_por)

    def get_yo(self, o):
        """Qué puede hacer quien mira: el front muestra solo esos botones."""
        u = self.context['request'].user
        r = []
        if o.ayudante_id == u.pk and o.estado == 'SOLICITADA':
            r += ['aceptar', 'rechazar']
        if o.ayudante_id == u.pk and o.estado == 'ACEPTADA':
            r.append('realizar')
        if o.estado == 'REALIZADA' and u.pk not in (o.ayudante_id, o.solicitante_id) and puede_revisar(u, o.ayudante):
            r += ['validar', 'no_validar']
        if o.solicitante_id == u.pk and o.estado == 'SOLICITADA':
            r.append('cancelar')
        return r

    def validate_descripcion(self, v):
        if len((v or '').strip()) < 10:
            raise serializers.ValidationError("Cuenta en qué se necesita el apoyo (al menos 10 letras).")
        return v.strip()


class ColaboracionViewSet(viewsets.ModelViewSet):
    """
    POST {ayudante, descripcion, tarea?, proyecto?}: pido apoyo a un compañero.
    POST {solicitante, descripcion, resultado, minutos, ya_realizada: true}: registro un apoyo que di.
    ?ambito=mias (pedidas o dadas) | equipo | por_validar.
    """
    serializer_class = ColaboracionSerializer
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        u = self.request.user
        qs = Colaboracion.objects.select_related('solicitante', 'ayudante', 'tarea', 'validada_por')
        ambito = self.request.query_params.get('ambito', 'mias')
        if self.action not in ('list', None):
            if es_administrador(u):
                return qs
            equipo = equipo_gestionable(u, 'tareas.validar')
            return qs.filter(Q(ayudante=u) | Q(solicitante=u) | Q(ayudante__in=equipo) | Q(solicitante__in=equipo)).distinct()
        if ambito in ('equipo', 'por_validar'):
            if not es_administrador(u):
                equipo = equipo_gestionable(u, 'tareas.validar')
                qs = qs.filter(Q(ayudante__in=equipo) | Q(solicitante__in=equipo))
            if ambito == 'por_validar':
                qs = qs.filter(estado='REALIZADA').exclude(ayudante=u).exclude(solicitante=u)
        else:
            qs = qs.filter(Q(ayudante=u) | Q(solicitante=u))
        return qs.distinct()

    def create(self, request, *args, **kwargs):
        u = request.user
        ya = str(request.data.get('ya_realizada', '')).lower() in ('1', 'true', 'si', 'sí')
        data = request.data.copy()
        if ya:
            data['ayudante'] = u.pk
        else:
            data['solicitante'] = u.pk
        ser = self.get_serializer(data=data)
        ser.is_valid(raise_exception=True)
        sol, ayu = ser.validated_data['solicitante'], ser.validated_data['ayudante']
        if sol.pk == ayu.pk:
            return Response({"detail": "Elige a otra persona."}, status=status.HTTP_400_BAD_REQUEST)
        if not ayu.is_active or not sol.is_active:
            return Response({"detail": "Esa persona no está activa."}, status=status.HTTP_400_BAD_REQUEST)
        if _depto_id(sol) != _depto_id(ayu) and not _entre_areas_permitido(u):
            return Response({"detail": "Para apoyo de otro departamento, pídeselo a tu supervisor: él lo coordina."},
                            status=status.HTTP_400_BAD_REQUEST)
        tarea = ser.validated_data.get('tarea')
        if tarea and u.pk not in tarea.participantes_ids() and not puede_revisar(u, tarea.colaborador):
            raise PermissionDenied("Solo se relaciona una tarea en la que participas.")
        if ya:
            if len((request.data.get('resultado') or '').strip()) < 5:
                return Response({"detail": "Cuenta el resultado del apoyo."}, status=status.HTTP_400_BAD_REQUEST)
            c = ser.save(registrada_por=u, estado='REALIZADA', fecha_realizada=timezone.now())
            servicios.avisar([c.solicitante], 'COLABORACION', f"{servicios.nombre(u)} registró que te apoyó",
                             c.descripcion[:200], tarea=c.tarea, enlace='/colaboracion', excepto=u)
            self._a_validar(c, u)
        else:
            c = ser.save(registrada_por=u, estado='SOLICITADA')
            servicios.avisar([c.ayudante], 'COLABORACION', f"{servicios.nombre(u)} te pide apoyo",
                             c.descripcion[:200], tarea=c.tarea, enlace='/colaboracion', excepto=u)
        return Response(self.get_serializer(c).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        if instance.solicitante_id != self.request.user.pk or instance.estado != 'SOLICITADA':
            raise PermissionDenied("Solo quien la pidió la retira, y antes de que se responda.")
        instance.delete()

    @staticmethod
    def _a_validar(c, quien):
        from .permisos import revisores_de
        servicios.avisar(revisores_de(c.ayudante), 'COLABORACION',
                         f"Por validar: {servicios.nombre(c.ayudante)} apoyó a {servicios.nombre(c.solicitante)}",
                         (c.resultado or c.descripcion)[:200], tarea=c.tarea, enlace='/colaboracion?ver=por_validar',
                         excepto=quien)

    def _paso(self, request, accion):
        c = self.get_object()
        if accion not in ColaboracionSerializer(c, context={'request': request}).data['yo']:
            raise PermissionDenied("Esta acción no te corresponde en este momento.")
        u = request.user
        texto = (request.data.get('texto') or '').strip()[:1000]
        if accion == 'aceptar':
            c.estado = 'ACEPTADA'
            servicios.avisar([c.solicitante], 'COLABORACION', f"{servicios.nombre(u)} aceptó apoyarte",
                             c.descripcion[:200], tarea=c.tarea, enlace='/colaboracion', excepto=u)
        elif accion == 'rechazar':
            c.estado, c.motivo = 'RECHAZADA', texto
            servicios.avisar([c.solicitante], 'COLABORACION', f"{servicios.nombre(u)} no puede apoyarte ahora",
                             texto, tarea=c.tarea, enlace='/colaboracion', excepto=u)
        elif accion == 'realizar':
            if len(texto) < 5:
                return Response({"detail": "Cuenta el resultado del apoyo."}, status=status.HTTP_400_BAD_REQUEST)
            c.estado, c.resultado, c.fecha_realizada = 'REALIZADA', texto, timezone.now()
            try:
                c.minutos = min(int(request.data.get('minutos') or 0), 12 * 60)
            except (TypeError, ValueError):
                c.minutos = 0
            servicios.avisar([c.solicitante], 'COLABORACION', f"{servicios.nombre(u)} terminó el apoyo",
                             texto[:200], tarea=c.tarea, enlace='/colaboracion', excepto=u)
            self._a_validar(c, u)
        elif accion in ('validar', 'no_validar'):
            if accion == 'no_validar' and len(texto) < 5:
                return Response({"detail": "Explica por qué no se valida."}, status=status.HTTP_400_BAD_REQUEST)
            c.estado = 'VALIDADA' if accion == 'validar' else 'NO_VALIDADA'
            c.validada_por, c.fecha_validacion, c.motivo = u, timezone.now(), texto
            servicios.avisar([c.ayudante], 'COLABORACION',
                             f"{'Validado' if accion == 'validar' else 'No validado'}: tu apoyo a {servicios.nombre(c.solicitante)}",
                             texto, tarea=c.tarea, enlace='/colaboracion', excepto=u)
        c.save()
        return Response(self.get_serializer(c).data)

    @action(detail=True, methods=['post'])
    def accion(self, request, pk=None):
        return self._paso(request, request.data.get('accion', ''))


@api_view(['GET'])
def mi_disponibilidad_view(request):
    """Para «Mis tareas»: si estoy en espera de asignación y desde cuándo, y qué tengo por hacer o bloqueado."""
    u = request.user
    espera = servicios.espera_abierta(u)
    mias = Tarea.objects.filter(Q(colaborador=u) | Q(companeros=u)).distinct()
    return Response({
        'en_espera': bool(espera), 'desde': espera.desde if espera else None,
        'por_hacer': mias.filter(estado__in=['PENDIENTE', 'EN_PROGRESO']).count(),
        'bloqueadas': mias.filter(estado='BLOQUEADA').count(),
        'en_revision': mias.filter(estado='EN_REVISION').count(),
        'tipos_actividad': [{'valor': k, 'texto': t} for k, t in ActividadAdicional.TIPOS],
    })


@api_view(['GET'])
def personas_view(request):
    """Personas activas para pedir o registrar apoyo (nombre y departamento). Empleados: solo su departamento."""
    u = request.user
    gente = (User.objects.filter(is_active=True).exclude(pk=u.pk)
             .select_related('perfil__puesto_trabajo__departamento').order_by('first_name', 'username'))
    todos = _entre_areas_permitido(u)
    mio = _depto_id(u)
    return Response([{'id': x.pk, 'nombre': _nombre(x), 'departamento': _depto(x)} for x in gente
                     if todos or (mio is not None and _depto_id(x) == mio)])
