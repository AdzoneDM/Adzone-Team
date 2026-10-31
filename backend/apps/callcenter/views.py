from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.desempeno.puntaje import calcular_ranking

from .models import Campana
from .permisos import agentes, es_agente, gestiona_call_center
from .serializers import CampanaSerializer


class CampanaViewSet(viewsets.ModelViewSet):
    """Quien gestiona el call center ve y edita todas; el agente solo ve las suyas."""
    serializer_class = CampanaSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Campana.objects.select_related('cliente').prefetch_related('agentes')
        if not gestiona_call_center(user):
            qs = qs.filter(agentes=user)
        if self.request.query_params.get('activas') == '1':
            hoy = timezone.localdate()
            qs = qs.filter(activa=True).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy))
        return qs

    def _exigir_gestion(self):
        if not gestiona_call_center(self.request.user):
            raise PermissionDenied("Solo la gerencia del call center crea o cambia campañas.")

    def perform_create(self, serializer):
        self._exigir_gestion()
        serializer.save(creada_por=self.request.user)

    def perform_update(self, serializer):
        self._exigir_gestion()
        serializer.save()

    def perform_destroy(self, instance):
        self._exigir_gestion()
        instance.delete()


@api_view(['GET'])
def resumen_view(request):
    """Datos de la pantalla de Call Center: la lista de agentes con sus campañas y su puntaje del mes."""
    user = request.user
    if not (gestiona_call_center(user) or es_agente(user)):
        raise PermissionDenied("Esta pantalla es del call center.")
    hoy = timezone.localdate()
    ranking = {f['colaborador_id']: f for f in calcular_ranking(hoy.replace(day=1), grupo='agentes')}
    lista = agentes() if gestiona_call_center(user) else agentes().filter(pk=user.pk)
    filas = []
    for a in lista.select_related('perfil__puesto_trabajo').prefetch_related('campanas_call_center'):
        f = ranking.get(a.id)
        puesto = getattr(getattr(a, 'perfil', None), 'puesto_trabajo', None)
        filas.append({
            'id': a.id, 'nombre': a.get_full_name() or a.username, 'puesto': puesto.nombre if puesto else None,
            'campanas': [{'id': c.id, 'nombre': c.nombre} for c in a.campanas_call_center.all() if c.activa],
            'puntaje': f['puntaje_total'] if f else None,
            'evaluacion': f['evaluacion'] if f else None,
            'kpis': f['kpis'] if f else [],
        })
    filas.sort(key=lambda x: x['nombre'])
    return Response({'gestiona': gestiona_call_center(user), 'agentes': filas})
