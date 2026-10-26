from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.desempeno import servicios as tareas_srv
from apps.desempeno.models import Tarea
from apps.desempeno.permisos import equipo_gestionable, es_administrador, puede_validar, puesto_de
from apps.operaciones.models import OrdenTrabajo, Proyecto
from apps.operaciones.permisos import es_finanzas, filtro_ordenes, filtro_proyectos
from . import servicios
from .models import RegistroTiempo
from .serializers import RegistroSerializer


def _fecha(texto, defecto=None):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return defecto or timezone.localdate()


def _validar_destino(user, tarea=None, orden=None, proyecto=None):
    if tarea and user.pk not in tarea.participantes_ids():
        raise PermissionDenied("Solo anotas tiempo en tareas que trabajas.")
    if orden:
        f = filtro_ordenes(user)
        if f is not None and not OrdenTrabajo.objects.filter(f, pk=orden.pk).exists():
            raise PermissionDenied("No tienes acceso a esa orden.")
    if proyecto:
        f = filtro_proyectos(user)
        if f is not None and not Proyecto.objects.filter(f, pk=proyecto.pk).exists():
            raise PermissionDenied("No tienes acceso a ese proyecto.")


class RegistroViewSet(viewsets.ModelViewSet):
    """Mis registros de tiempo. Nadie ve ni toca los de otros por aquí."""
    serializer_class = RegistroSerializer

    def get_queryset(self):
        qs = RegistroTiempo.objects.filter(usuario=self.request.user).select_related(
            'tarea', 'orden__cliente', 'proyecto__cliente')
        p = self.request.query_params
        if p.get('desde') and p.get('hasta'):
            qs = qs.filter(inicio__range=(servicios._dt(_fecha(p['desde'])), servicios._dt(_fecha(p['hasta']), True)))
        return qs

    def perform_create(self, serializer):
        v = serializer.validated_data
        _validar_destino(self.request.user, v.get('tarea'), v.get('orden'), v.get('proyecto'))
        r = serializer.save(usuario=self.request.user)
        r.completar_desde_tarea()
        r.save()

    def perform_update(self, serializer):
        v = serializer.validated_data
        _validar_destino(self.request.user, v.get('tarea'), v.get('orden'), v.get('proyecto'))
        serializer.save()


@api_view(['GET'])
def activo_view(request):
    r = servicios.activo(request.user)
    return Response({'activo': RegistroSerializer(r).data if r else None})


@api_view(['POST'])
def iniciar_view(request):
    user = request.user
    tarea = Tarea.objects.filter(pk=request.data.get('tarea')).first() if request.data.get('tarea') else None
    orden = OrdenTrabajo.objects.filter(pk=request.data.get('orden')).first() if request.data.get('orden') else None
    proyecto = Proyecto.objects.filter(pk=request.data.get('proyecto')).first() if request.data.get('proyecto') else None
    _validar_destino(user, tarea, orden, proyecto)
    descripcion = (request.data.get('descripcion') or '').strip()
    if not (tarea or orden or proyecto or descripcion):
        return Response({"detail": "Elige una tarea, una orden o un proyecto, o escribe en qué trabajas."},
                        status=status.HTTP_400_BAD_REQUEST)
    registro, previo = servicios.iniciar(user, tarea, orden, proyecto, descripcion)
    if tarea and tarea.estado == 'PENDIENTE':  # empezar el cronómetro es empezar la tarea
        tarea.estado = 'EN_PROGRESO'
        tarea.save(update_fields=['estado', 'fecha_modificacion'])
        tareas_srv.registrar(tarea, user, 'INICIADA')
        tareas_srv.tras_cambio(tarea, user)
    return Response({'activo': RegistroSerializer(registro).data,
                     'detenido': RegistroSerializer(previo).data if previo else None}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def detener_view(request):
    r = servicios.activo(request.user)
    if r is None:
        return Response({"detail": "No tienes un cronómetro corriendo."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(RegistroSerializer(servicios.detener(r)).data)


def _capacidad_min(u):
    horas = getattr(getattr(u, 'perfil', None), 'horas_semana', None) or Decimal('44')
    return int(Decimal(horas) * 60)


@api_view(['GET'])
def semana_view(request):
    desde, hasta = servicios.rango_semana(_fecha(request.query_params.get('fecha')))
    registros = list(RegistroTiempo.objects.filter(
        usuario=request.user, inicio__range=(servicios._dt(desde), servicios._dt(hasta, True)))
        .select_related('tarea', 'orden__cliente', 'proyecto__cliente'))
    dias = []
    for i in range(7):
        d = desde + timedelta(days=i)
        dias.append({'fecha': d, 'minutos': sum(r.minutos_hasta_ahora() for r in registros
                                                 if timezone.localtime(r.inicio).date() == d)})
    return Response({'desde': desde, 'hasta': hasta, 'dias': dias, 'total': sum(x['minutos'] for x in dias),
                     'capacidad': _capacidad_min(request.user),
                     'registros': RegistroSerializer(registros, many=True).data})


@api_view(['GET'])
def equipo_view(request):
    """Carga semanal de cada persona: horas anotadas, lo que tiene pendiente y su capacidad."""
    user = request.user
    if not puede_validar(user):
        raise PermissionDenied("Solo para quien supervisa un equipo.")
    desde, hasta = servicios.rango_semana(_fecha(request.query_params.get('fecha')))
    gente = list(equipo_gestionable(user).select_related('perfil__puesto_trabajo__departamento').order_by('first_name'))
    minutos = servicios.minutos_por_usuario(desde, hasta, gente)
    abiertas = Tarea.objects.filter(Q(colaborador__in=gente) | Q(companeros__in=gente),
                                    estado__in=['PENDIENTE', 'EN_PROGRESO'], fecha_limite__lte=hasta).distinct().prefetch_related('companeros')
    pendiente, cuantas = {}, {}
    for t in abiertas:
        for pid in t.participantes_ids():
            cuantas[pid] = cuantas.get(pid, 0) + 1
            if t.horas_estimadas:
                pendiente[pid] = pendiente.get(pid, 0) + float(t.horas_estimadas) * 60 / len(t.participantes_ids())
    filas = []
    for u in gente:
        cap = _capacidad_min(u)
        reg = minutos.get(u.pk, 0)
        pend = int(pendiente.get(u.pk, 0))
        puesto = puesto_de(u)
        filas.append({'id': u.pk, 'nombre': u.get_full_name() or u.username, 'puesto': puesto.nombre if puesto else None,
                      'departamento': puesto.departamento.nombre if puesto else None,
                      'color': puesto.departamento.color if puesto else None,
                      'registrado': reg, 'pendiente': pend, 'capacidad': cap, 'tareas_abiertas': cuantas.get(u.pk, 0),
                      'carga_pct': round(100 * (reg + pend) / cap) if cap else None})
    filas.sort(key=lambda f: -(f['carga_pct'] or 0))
    return Response({'desde': desde, 'hasta': hasta, 'personas': filas})


@api_view(['GET'])
def reporte_view(request):
    """Horas por proyecto, cliente, persona, orden o departamento en un periodo."""
    user = request.user
    if not (es_finanzas(user) or puede_validar(user)):
        raise PermissionDenied("Solo para quien supervisa o Finanzas.")
    hoy = timezone.localdate()
    desde = _fecha(request.query_params.get('desde'), hoy.replace(day=1))
    hasta = _fecha(request.query_params.get('hasta'), hoy)
    agrupar = request.query_params.get('agrupar', 'proyecto')
    qs = RegistroTiempo.objects.filter(inicio__range=(servicios._dt(desde), servicios._dt(hasta, True)), fin__isnull=False)
    if not (es_administrador(user) or es_finanzas(user)):
        qs = qs.filter(usuario__in=list(equipo_gestionable(user)) + [user])
    qs = qs.select_related('usuario__perfil__puesto_trabajo__departamento', 'proyecto__cliente', 'orden__cliente', 'tarea')
    grupos = {}
    for r in qs:
        if agrupar == 'persona':
            clave, nombre = r.usuario_id, r.usuario.get_full_name() or r.usuario.username
        elif agrupar == 'cliente':
            c = (r.orden.cliente if r.orden_id else r.proyecto.cliente if r.proyecto_id else None)
            clave, nombre = (c.pk, c.nombre) if c else (0, 'Sin cliente')
        elif agrupar == 'orden':
            clave, nombre = (r.orden_id, f"{r.orden.numero} · {r.orden.titulo}") if r.orden_id else (0, 'Sin orden')
        elif agrupar == 'departamento':
            p = puesto_de(r.usuario)
            clave, nombre = (p.departamento_id, p.departamento.nombre) if p else (0, 'Sin departamento')
        else:
            clave, nombre = (r.proyecto_id, f"{r.proyecto.codigo} · {r.proyecto.nombre}") if r.proyecto_id else (0, 'Sin proyecto')
        g = grupos.setdefault(clave, {'clave': clave, 'nombre': nombre, 'minutos': 0, 'facturable': 0, 'personas': set()})
        g['minutos'] += r.minutos
        g['facturable'] += r.minutos if r.facturable else 0
        g['personas'].add(r.usuario_id)
    filas = sorted(({**g, 'personas': len(g['personas'])} for g in grupos.values()), key=lambda g: -g['minutos'])
    return Response({'desde': desde, 'hasta': hasta, 'agrupar': agrupar, 'filas': filas,
                     'total': sum(f['minutos'] for f in filas)})
