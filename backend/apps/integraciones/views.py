from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.operaciones.models import Cliente
from apps.operaciones.permisos import es_finanzas
from .cashflow import servicios
from .cashflow.cliente import CashflowError
from .models import SincronizacionCashflow


def _finanzas(request):
    if not es_finanzas(request.user):
        raise PermissionDenied("La integración con Cashflow la usa Administración.")


@api_view(['GET'])
def estado_view(request):
    _finanzas(request)
    datos = servicios.estado()
    datos['bitacora'] = [{'id': s.id, 'operacion': s.operacion, 'objeto': s.objeto, 'exito': s.exito, 'modo': s.modo,
                          'detalle': s.detalle, 'usuario': (s.usuario.get_full_name() or s.usuario.username) if s.usuario else 'Tarea diaria',
                          'fecha': s.fecha} for s in SincronizacionCashflow.objects.select_related('usuario')[:60]]
    return Response(datos)


@api_view(['POST'])
def probar_view(request):
    _finanzas(request)
    try:
        return Response({'ok': True, 'empresa': servicios.probar(request.user)})
    except CashflowError as e:
        return Response({'ok': False, 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def sincronizar_view(request):
    _finanzas(request)
    return Response(servicios.sincronizar_pendientes(request.user))


@api_view(['POST'])
def cliente_view(request, pk):
    _finanzas(request)
    cliente = Cliente.objects.filter(pk=pk).first()
    if cliente is None:
        return Response({"detail": "No encontré ese cliente."}, status=status.HTTP_404_NOT_FOUND)
    try:
        return Response({'cashflow_id': servicios.sincronizar_cliente(cliente, request.user)})
    except CashflowError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
