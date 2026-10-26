from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.desempeno.permisos import EsAdministrador
from apps.operaciones.formatos import AREAS
from apps.operaciones.models import OrdenTrabajo
from .models import ACCIONES, EVENTOS, Ejecucion, Regla
from .serializers import DESTINOS, EjecucionSerializer, ReglaSerializer


class ReglaViewSet(viewsets.ModelViewSet):
    serializer_class = ReglaSerializer
    permission_classes = [EsAdministrador]
    queryset = Regla.objects.all()

    def perform_create(self, serializer):
        serializer.save(creada_por=self.request.user)


@api_view(['GET'])
@permission_classes([EsAdministrador])
def catalogo_view(request):
    return Response({
        'eventos': [{'valor': k, 'nombre': v} for k, v in EVENTOS],
        'acciones': [{'valor': k, 'nombre': v} for k, v in ACCIONES],
        'destinos': [{'valor': 'responsable', 'nombre': 'Responsable'}, {'valor': 'solicitante', 'nombre': 'Quien la pidió'},
                     {'valor': 'jefes', 'nombre': 'Gerente del departamento'}, {'valor': 'finanzas', 'nombre': 'Finanzas'},
                     {'valor': 'administradores', 'nombre': 'Dirección'}],
        'areas': [{'valor': k, 'nombre': v['nombre']} for k, v in AREAS.items()],
        'estados': [{'valor': k, 'nombre': v} for k, v in OrdenTrabajo.ESTADOS],
        'variables': ['{numero}', '{titulo}', '{cliente}', '{estado_nombre}', '{responsable}', '{monto}', '{fecha_compromiso}',
                      '{saldo}', '{vencimiento}'],
        'destinos_validos': DESTINOS,
    })


@api_view(['GET'])
@permission_classes([EsAdministrador])
def ejecuciones_view(request):
    return Response(EjecucionSerializer(Ejecucion.objects.select_related('regla')[:100], many=True).data)
