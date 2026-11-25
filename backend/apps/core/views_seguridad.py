"""Sesiones abiertas (cada persona las ve y las cierra) y bitácora de accesos (quien tiene «Ver la auditoría»)."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.desempeno.permisos import TienePermiso

from . import accesos
from .models import EventoAcceso
from .permisos import revisar_cambio


def _fila(e, actual=None):
    return {'id': e.id, 'dispositivo': e.dispositivo or 'Dispositivo', 'navegador': e.navegador, 'ip': e.ip, 'desde': e.fecha,
            'actual': bool(actual and e.sesion == actual), 'riesgo': e.riesgo, 'motivo': e.motivo}


@api_view(['GET'])
def mis_sesiones_view(request):
    actual = request.session.session_key
    return Response([_fila(e, actual) for e in reversed(accesos.sesiones_abiertas(request.user))])


@api_view(['DELETE'])
def mi_sesion_view(request, pk):
    e = get_object_or_404(EventoAcceso, pk=pk, usuario=request.user, tipo='ENTRADA')
    if e.sesion == request.session.session_key:
        return Response({'detail': 'Esta es la sesión que estás usando: para cerrarla usa «Salir».'}, status=status.HTTP_400_BAD_REQUEST)
    accesos.cerrar_sesion(request, request.user, e)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
def cerrar_otras_view(request):
    actual = request.session.session_key
    n = 0
    for e in accesos.sesiones_abiertas(request.user):
        if e.sesion != actual:
            accesos.cerrar_sesion(request, request.user, e)
            n += 1
    return Response({'cerradas': n})


@api_view(['GET', 'POST'])
@permission_classes([TienePermiso.de('personal.usuarios')])
def sesiones_de_persona_view(request, pk):
    """Quien administra personas ve y cierra las sesiones de otra (no las de alguien con más permisos que él)."""
    persona = get_object_or_404(User, pk=pk)
    motivo = revisar_cambio(request.user, persona, [])
    if motivo and persona.pk != request.user.pk:
        raise PermissionDenied(motivo)
    if request.method == 'POST':
        n = 0
        for e in accesos.sesiones_abiertas(persona):
            accesos.cerrar_sesion(request, persona, e)
            n += 1
        from apps.talento.auditoria import auditar
        auditar(f'Cerró {n} sesión(es) abierta(s)', persona, usuario=request.user)
        return Response({'cerradas': n})
    return Response([_fila(e) for e in reversed(accesos.sesiones_abiertas(persona))])


@api_view(['GET'])
@permission_classes([TienePermiso.de('auditoria.ver')])
def bitacora_accesos_view(request):
    """Eventos de acceso con filtros (?usuario, ?tipo, ?ip, ?dias) y un resumen de las últimas 24 horas."""
    qs = EventoAcceso.objects.select_related('usuario')
    p = request.query_params
    if p.get('usuario'):
        qs = qs.filter(Q(usuario_id=p['usuario']) if str(p['usuario']).isdigit() else Q(usuario_texto__icontains=p['usuario'][:100]))
    if p.get('tipo'):
        qs = qs.filter(tipo__in=p['tipo'].split(','))
    if p.get('ip'):
        qs = qs.filter(ip=p['ip'][:45])
    dias = min(max(int(p.get('dias') or 30), 1), 365) if str(p.get('dias') or '30').isdigit() else 30
    qs = qs.filter(fecha__gte=timezone.now() - timedelta(days=dias))
    dia = EventoAcceso.objects.filter(fecha__gte=timezone.now() - timedelta(hours=24))
    resumen = dict(dia.values_list('tipo').annotate(n=Count('id')))
    ips = list(dia.filter(tipo='FALLO').exclude(ip=None).values('ip').annotate(n=Count('id')).order_by('-n')[:5])
    return Response({
        'resumen_24h': {'entradas': resumen.get('ENTRADA', 0), 'fallos': resumen.get('FALLO', 0) + resumen.get('FALLO_CODIGO', 0),
                        'bloqueos': resumen.get('BLOQUEO', 0), 'sospechosos': resumen.get('SOSPECHOSO', 0),
                        'denegados': resumen.get('DENEGADO', 0) + resumen.get('IP_BLOQUEADA', 0), 'ips_con_mas_fallos': ips},
        'eventos': [{'id': e.id, 'tipo': e.tipo, 'tipo_texto': e.get_tipo_display(), 'usuario': e.usuario_id,
                     'nombre': (e.usuario.get_full_name() or e.usuario.username) if e.usuario else e.usuario_texto,
                     'ip': e.ip, 'dispositivo': e.dispositivo, 'dispositivo_nuevo': e.dispositivo_nuevo, 'riesgo': e.riesgo,
                     'motivo': e.motivo, 'ruta': e.ruta, 'fecha': e.fecha} for e in qs[:300]],
    })
