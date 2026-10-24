from django.db.models import ProtectedError
from rest_framework import serializers, status, viewsets
from rest_framework.response import Response

from apps.desempeno.permisos import LecturaOAdministrador, es_administrador, puesto_de, puestos_debajo
from .models import KPIAsignado, PlantillaKPI
from .serializers import KPIAsignadoSerializer, PlantillaKPISerializer


class PlantillaKPIViewSet(viewsets.ModelViewSet):
    queryset = PlantillaKPI.objects.prefetch_related('asignaciones').order_by('nombre')
    serializer_class = PlantillaKPISerializer
    permission_classes = [LecturaOAdministrador]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({"detail": "Esta plantilla está asignada a uno o más puestos. Quita esas asignaciones primero."},
                            status=status.HTTP_400_BAD_REQUEST)


class KPIAsignadoViewSet(viewsets.ModelViewSet):
    """
    KPIs de cada puesto. El administrador ve y cambia todos; un supervisor ve los de su puesto
    y los de los puestos que dependen de él; un colaborador, los de su puesto.
    """
    serializer_class = KPIAsignadoSerializer
    permission_classes = [LecturaOAdministrador]
    filterset_fields = ['puesto_trabajo', 'es_entrada_manual', 'activo']

    def get_queryset(self):
        user = self.request.user
        queryset = KPIAsignado.objects.select_related('puesto_trabajo__departamento', 'puesto_trabajo__supervisor', 'plantilla_kpi')
        orden = ('puesto_trabajo__departamento__nombre', 'puesto_trabajo__nombre', 'plantilla_kpi__nombre')
        if es_administrador(user):
            return queryset.order_by(*orden)
        puesto = puesto_de(user)
        if puesto is None:
            return KPIAsignado.objects.none()
        return queryset.filter(puesto_trabajo__in=[puesto.id, *puestos_debajo(puesto)]).order_by(*orden)

    def perform_create(self, serializer):
        puesto = serializer.validated_data.get('puesto_trabajo')
        plantilla = serializer.validated_data.get('plantilla_kpi')
        if KPIAsignado.objects.filter(puesto_trabajo=puesto, plantilla_kpi=plantilla).exists():
            raise serializers.ValidationError({"detail": "Esta plantilla de KPI ya está asignada a este puesto."})
        serializer.save()
