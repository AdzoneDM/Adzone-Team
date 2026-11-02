from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import exceptions, permissions, serializers, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from . import servicios
from .models import Activo, MovimientoActivo


class GestionaActivos(permissions.BasePermission):
    message = "Los equipos los registran Tecnología, Almacén y la administración."

    def has_permission(self, request, view):
        return servicios.gestiona_activos(request.user)


def _nombre(u):
    return (u.get_full_name() or u.username) if u else None


class MovimientoSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    persona_nombre = serializers.SerializerMethodField()
    registrado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = MovimientoActivo
        fields = ['id', 'tipo', 'tipo_nombre', 'fecha', 'persona', 'persona_nombre', 'costo', 'nota', 'registrado_por_nombre', 'creado']

    def get_persona_nombre(self, o):
        return _nombre(o.persona)

    def get_registrado_por_nombre(self, o):
        return _nombre(o.registrado_por)


class ActivoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='get_categoria_display', read_only=True)
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    asignado_nombre = serializers.SerializerMethodField()
    proyecto_nombre = serializers.SerializerMethodField()
    dispositivo_nombre = serializers.CharField(source='dispositivo.nombre', read_only=True, default=None)
    dispositivo_contacto = serializers.DateTimeField(source='dispositivo.ultimo_contacto', read_only=True, default=None)
    valor_actual = serializers.SerializerMethodField()

    class Meta:
        model = Activo
        fields = ['id', 'codigo', 'nombre', 'categoria', 'categoria_nombre', 'marca', 'modelo', 'serie', 'estado', 'estado_nombre', 'ubicacion',
                  'asignado_a', 'asignado_nombre', 'proyecto', 'proyecto_nombre', 'dispositivo', 'dispositivo_nombre', 'dispositivo_contacto',
                  'fecha_compra', 'costo', 'proveedor', 'garantia_hasta', 'vida_util_meses', 'valor_residual', 'mantenimiento_cada_meses',
                  'proximo_mantenimiento', 'notas', 'valor_actual', 'creado']
        read_only_fields = ['codigo', 'estado', 'asignado_a']

    def get_asignado_nombre(self, o):
        return _nombre(o.asignado_a)

    def get_proyecto_nombre(self, o):
        return f'{o.proyecto.codigo} · {o.proyecto.nombre}' if o.proyecto_id else None

    def get_valor_actual(self, o):
        v = o.valor_actual()
        return float(v) if v is not None else None

    def to_representation(self, o):
        d = super().to_representation(o)
        if 'gestiona' not in self.context:
            self.context['gestiona'] = servicios.gestiona_activos(self.context['request'].user)
        if not self.context['gestiona']:
            for k in ('costo', 'valor_actual', 'valor_residual', 'proveedor'):
                d[k] = None
        return d

    def validate(self, data):
        if data.get('valor_residual') and data.get('costo') is not None and data['valor_residual'] > data['costo']:
            raise serializers.ValidationError({'valor_residual': 'No puede ser mayor que el costo.'})
        return data


class ActivoViewSet(viewsets.ModelViewSet):
    serializer_class = ActivoSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'reportar'):
            return [permissions.IsAuthenticated()]
        return [GestionaActivos()]

    def get_queryset(self):
        u = self.request.user
        qs = Activo.objects.select_related('asignado_a', 'proyecto', 'dispositivo')
        if not servicios.gestiona_activos(u):
            return qs.filter(asignado_a=u)
        p = self.request.query_params
        if p.get('estado'):
            qs = qs.filter(estado=p['estado'])
        else:
            qs = qs.exclude(estado='BAJA') if p.get('bajas') != '1' else qs
        if p.get('categoria'):
            qs = qs.filter(categoria=p['categoria'])
        if p.get('persona', '').isdigit():
            qs = qs.filter(asignado_a_id=p['persona'])
        if p.get('q'):
            t = p['q'].strip()
            qs = qs.filter(Q(nombre__icontains=t) | Q(codigo__icontains=t) | Q(serie__icontains=t) | Q(marca__icontains=t) | Q(asignado_a__first_name__icontains=t))
        return qs

    def perform_create(self, serializer):
        a = serializer.save()
        MovimientoActivo.objects.create(activo=a, tipo='ALTA', registrado_por=self.request.user, costo=a.costo, nota='Registro del equipo')

    def perform_destroy(self, instance):
        if instance.movimientos.exclude(tipo='ALTA').exists():
            raise exceptions.ValidationError('Tiene historial: dale de baja en vez de borrarlo.')
        instance.delete()

    @action(detail=True, methods=['get'])
    def historial(self, request, pk=None):
        return Response(MovimientoSerializer(self.get_object().movimientos.select_related('persona', 'registrado_por'), many=True).data)

    @action(detail=True, methods=['post'])
    def mover(self, request, pk=None):
        a = self.get_object()
        tipo = request.data.get('tipo')
        if tipo not in ('ASIGNACION', 'DEVOLUCION', 'TRASLADO', 'MANTENIMIENTO', 'REPARACION', 'DANO', 'BAJA'):
            return Response({'tipo': 'Movimiento no válido.'}, status=400)
        if a.estado == 'BAJA':
            return Response({'detail': 'El equipo está de baja.'}, status=400)
        persona = None
        if tipo == 'ASIGNACION':
            if not str(request.data.get('persona', '')).isdigit():
                return Response({'persona': 'Elige a quién se asigna.'}, status=400)
            persona = get_object_or_404(User, pk=request.data['persona'], is_active=True)
        if tipo == 'TRASLADO':
            a.ubicacion = str(request.data.get('ubicacion') or a.ubicacion)[:100]
        costo = request.data.get('costo') or None
        try:
            costo = None if costo in (None, '') else float(costo)
        except (TypeError, ValueError):
            return Response({'costo': 'Debe ser un número.'}, status=400)
        servicios.mover(a, tipo, request.user, persona=persona, costo=costo, nota=request.data.get('nota') or '')
        if tipo == 'ASIGNACION':
            from apps.desempeno.servicios import avisar
            avisar([persona], 'MONITOREO', f'Se te asignó {a.codigo} · {a.nombre}', 'Cuídalo y reporta cualquier daño desde «Mis equipos».',
                   enlace='/activos', excepto=request.user)
        return Response(self.get_serializer(a).data)

    @action(detail=True, methods=['post'])
    def reportar(self, request, pk=None):
        """Quien tiene el equipo reporta un daño o falla."""
        a = get_object_or_404(Activo, pk=pk)
        if a.asignado_a_id != request.user.pk and not servicios.gestiona_activos(request.user):
            raise exceptions.PermissionDenied("Solo quien lo tiene asignado reporta un daño.")
        nota = str(request.data.get('nota') or '').strip()
        if not nota:
            return Response({'nota': 'Describe qué pasó.'}, status=400)
        servicios.mover(a, 'DANO', request.user, persona=request.user, nota=nota)
        from apps.desempeno.servicios import avisar
        avisar(servicios.responsables(), 'MONITOREO', f'{_nombre(request.user)} reportó un daño en {a.codigo} · {a.nombre}', nota[:300],
               enlace=f'/activos?ver={a.pk}', excepto=request.user)
        return Response(self.get_serializer(a).data)


@api_view(['GET'])
def resumen_view(request):
    if not servicios.gestiona_activos(request.user):
        raise exceptions.PermissionDenied(GestionaActivos.message)
    return Response(servicios.resumen())
