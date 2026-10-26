from django.db.models import F, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.operaciones.models import OrdenArea, OrdenTrabajo
from apps.operaciones.permisos import areas_que_supervisa, es_almacen, es_coordinacion, es_finanzas, filtro_ordenes
from apps.operaciones.servicios_ot import ErrorFlujo
from . import servicios
from .models import Material, MovimientoInventario, ValeMaterial
from .serializers import MaterialSerializer, MovimientoSerializer, ValeSerializer


def _error(e):
    return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MaterialViewSet(viewsets.ModelViewSet):
    """Catálogo de materiales. Todos lo consultan (para pedir); lo mantiene Almacén."""
    serializer_class = MaterialSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Material.objects.all()
        p = self.request.query_params
        if p.get('activos') == '1':
            qs = qs.filter(activo=True)
        if p.get('bajo_minimo') == '1':
            qs = qs.filter(existencia__lte=F('punto_reposicion'))
        if p.get('q'):
            qs = qs.filter(Q(nombre__icontains=p['q']) | Q(codigo__icontains=p['q']))
        return qs

    def _exigir(self):
        if not es_almacen(self.request.user):
            raise PermissionDenied("El catálogo de materiales lo mantiene Almacén.")

    def perform_create(self, serializer):
        self._exigir()
        serializer.save()

    def perform_update(self, serializer):
        self._exigir()
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        self._exigir()
        m = self.get_object()
        if m.movimientos.exists():
            return _error("Tiene movimientos: márcalo como inactivo.")
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def entrada(self, request, pk=None):
        try:
            m = servicios.entrada(self.get_object(), request.user, request.data.get('cantidad'), request.data.get('costo_unitario'),
                                  request.data.get('nota', ''))
        except ErrorFlujo as e:
            return _error(e)
        return Response(self.get_serializer(m).data)

    @action(detail=True, methods=['post'])
    def ajustar(self, request, pk=None):
        try:
            m = servicios.ajustar(self.get_object(), request.user, request.data.get('existencia'), request.data.get('nota', ''))
        except ErrorFlujo as e:
            return _error(e)
        return Response(self.get_serializer(m).data)

    @action(detail=True)
    def movimientos(self, request, pk=None):
        if not (es_almacen(request.user) or es_finanzas(request.user) or es_coordinacion(request.user)):
            raise PermissionDenied("El kardex lo ven Almacén, Coordinación y Administración.")
        return Response(MovimientoSerializer(self.get_object().movimientos.select_related('usuario', 'vale')[:200], many=True).data)


class ValeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ValeSerializer

    def get_queryset(self):
        user = self.request.user
        qs = ValeMaterial.objects.select_related('orden__cliente', 'oa', 'solicitado_por', 'autorizado_por', 'despachado_por',
                                                 'recibido_por').prefetch_related('lineas__material')
        if not (es_almacen(user) or es_coordinacion(user) or es_finanzas(user)):
            visibles = OrdenTrabajo.objects.filter(filtro_ordenes(user)) if filtro_ordenes(user) is not None else OrdenTrabajo.objects.all()
            qs = qs.filter(Q(solicitado_por=user) | Q(oa__responsable=user) | Q(oa__area__in=areas_que_supervisa(user)),
                           orden__in=visibles).distinct()
        p = self.request.query_params
        if p.get('estado'):
            qs = qs.filter(estado__in=p['estado'].split(','))
        if p.get('orden'):
            qs = qs.filter(orden_id=p['orden'])
        if p.get('oa'):
            qs = qs.filter(oa_id=p['oa'])
        return qs

    def create(self, request):
        oa = OrdenArea.objects.filter(pk=request.data.get('oa')).select_related('orden').first()
        if oa is None:
            return _error("Elige la Orden de Área.")
        try:
            vale = servicios.solicitar(oa, request.user, request.data.get('lineas'), request.data.get('notas', ''))
        except ErrorFlujo as e:
            return _error(e)
        return Response(self.get_serializer(vale).data, status=status.HTTP_201_CREATED)

    def _paso(self, funcion, *args):
        vale = self.get_object()
        try:
            funcion(vale, self.request.user, *args)
        except ErrorFlujo as e:
            return _error(e)
        return Response(self.get_serializer(self.get_queryset().get(pk=vale.pk)).data)

    @action(detail=True, methods=['post'])
    def autorizar(self, request, pk=None):
        return self._paso(servicios.autorizar)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        return self._paso(servicios.rechazar, request.data.get('motivo'))

    @action(detail=True, methods=['post'])
    def despachar(self, request, pk=None):
        return self._paso(servicios.despachar, request.data.get('lineas'))

    @action(detail=True, methods=['post'])
    def recibir(self, request, pk=None):
        return self._paso(servicios.recibir)

    @action(detail=True, methods=['post'])
    def cerrar(self, request, pk=None):
        return self._paso(servicios.cerrar, request.data.get('lineas'))

    @action(detail=False)
    def resumen(self, request):
        qs = self.get_queryset()
        return Response({
            'por_autorizar': qs.filter(estado='SOLICITADO').count(),
            'por_despachar': qs.filter(estado='AUTORIZADO').count(),
            'por_cerrar': qs.filter(estado='DESPACHADO').count(),
            'bajo_minimo': Material.objects.filter(activo=True, existencia__lte=F('punto_reposicion')).count(),
        })


class MovimientoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MovimientoSerializer

    def get_queryset(self):
        u = self.request.user
        if not (es_almacen(u) or es_finanzas(u) or es_coordinacion(u)):
            return MovimientoInventario.objects.none()
        return MovimientoInventario.objects.select_related('material', 'usuario', 'vale')
