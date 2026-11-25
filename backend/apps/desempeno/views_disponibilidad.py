"""Quién está libre (público para todos los departamentos) y el historial de tareas (quién la hizo, quién la asignó, quién la validó)."""
import csv

from django.contrib.auth.models import User
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Tarea
from .permisos import asignables, equipo_gestionable, es_administrador

ABIERTAS = ('PENDIENTE', 'EN_PROGRESO', 'BLOQUEADA')   # lo que la persona tiene por hacer (lo «en revisión» ya lo entregó)
POCA_CARGA_MAX = 2                                       # hasta 2 tareas abiertas = «poca carga»; más = ocupada
PAGINA = 40
MAX_CSV = 5000


def _nombre(u):
    return u.get_full_name() or u.username


def _puesto(u):
    return getattr(getattr(u, 'perfil', None), 'puesto_trabajo', None)


# ---------------------------------------------------------------------------------------------------------------------
# Quién está libre
# ---------------------------------------------------------------------------------------------------------------------
@api_view(['GET'])
def disponibilidad_view(request):
    """Todas las personas con su carga (cuántas tareas abiertas), para pedir ayuda a quien está libre. Es de consulta para cualquier persona de la
    plataforma y de todos los departamentos: solo muestra CUÁNTAS tareas tiene y la próxima entrega, nunca de qué son."""
    from apps.asistencia.models import Ausencia
    from apps.callcenter.permisos import GRUPO_AGENTE
    from .views_equipo import _depto_id, _entre_areas_permitido
    u = request.user
    hoy = timezone.localdate()
    gente = list(User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=False).exclude(groups__name=GRUPO_AGENTE)
                 .select_related('perfil__puesto_trabajo__departamento').order_by('first_name', 'last_name', 'username').distinct())
    carga = {p.pk: {'abiertas': 0, 'en_revision': 0, 'horas': 0.0, 'proxima': None} for p in gente}

    def sumar(uid, fecha):
        c = carga.get(uid)
        if c is not None:
            c['abiertas'] += 1
            if fecha and (c['proxima'] is None or fecha < c['proxima']):
                c['proxima'] = fecha

    for colab, estado, horas, fecha in Tarea.objects.filter(estado__in=ABIERTAS + ('EN_REVISION',)).values_list('colaborador_id', 'estado', 'horas_estimadas', 'fecha_limite'):
        if estado == 'EN_REVISION':
            if colab in carga:
                carga[colab]['en_revision'] += 1
            continue
        sumar(colab, fecha)
        if colab in carga:
            carga[colab]['horas'] += float(horas or 0)
    for uid, fecha in Tarea.companeros.through.objects.filter(tarea__estado__in=ABIERTAS, tarea__eliminada_en__isnull=True).values_list('user_id', 'tarea__fecha_limite'):
        sumar(uid, fecha)
    ausentes = set(Ausencia.objects.filter(estado='APROBADA', desde__lte=hoy, hasta__gte=hoy).values_list('usuario_id', flat=True))
    puedo_asignar = set(asignables(u).values_list('pk', flat=True))
    mi_depto = _depto_id(u)
    coordina = _entre_areas_permitido(u)

    personas, resumen = [], {'libres': 0, 'poca_carga': 0, 'ocupados': 0, 'no_disponibles': 0}
    for p in gente:
        c = carga[p.pk]
        if p.pk in ausentes:
            estado = 'AUSENTE'
            resumen['no_disponibles'] += 1
        elif c['abiertas'] == 0:
            estado = 'LIBRE'
            resumen['libres'] += 1
        elif c['abiertas'] <= POCA_CARGA_MAX:
            estado = 'POCA'
            resumen['poca_carga'] += 1
        else:
            estado = 'OCUPADO'
            resumen['ocupados'] += 1
        puesto = _puesto(p)
        personas.append({
            'id': p.pk, 'nombre': _nombre(p), 'usuario': p.username, 'puesto': puesto.nombre,
            'departamento': puesto.departamento.nombre if puesto.departamento_id else '', 'departamento_id': puesto.departamento_id,
            'estado': estado, 'tareas_abiertas': c['abiertas'], 'en_revision': c['en_revision'], 'horas_pendientes': round(c['horas'], 1),
            'proxima_entrega': c['proxima'], 'es_yo': p.pk == u.pk,
            'puedo_asignar': p.pk in puedo_asignar and p.pk != u.pk,
            # apoyo formal (Colaboración): dentro de tu departamento cualquiera; entre departamentos, quien supervisa (regla que ya existía)
            'puedo_pedir_apoyo': p.pk != u.pk and (coordina or (mi_depto is not None and puesto.departamento_id == mi_depto)),
        })
    return Response({'personas': personas, 'resumen': resumen, 'poca_carga_max': POCA_CARGA_MAX, 'hoy': hoy})


# ---------------------------------------------------------------------------------------------------------------------
# Historial de tareas
# ---------------------------------------------------------------------------------------------------------------------
def _visibles(user):
    """Las mismas tareas que ve cada persona en la plataforma: las suyas, las de su equipo, las que asignó y en las que colabora (Dirección: todas)."""
    qs = Tarea.objects.all()
    if not es_administrador(user):
        qs = qs.filter(Q(colaborador=user) | Q(companeros=user) | Q(colaborador__in=equipo_gestionable(user, 'equipo.ver')) | Q(asignada_por=user)).distinct()
    return qs


def _filtrar(request):
    p = request.query_params
    qs = _visibles(request.user).select_related(
        'colaborador__perfil__puesto_trabajo__departamento', 'asignada_por', 'validada_por', 'departamento_origen').prefetch_related('companeros')
    estado = p.get('estado', 'COMPLETADA')
    qs = qs.filter(estado__in=('COMPLETADA', 'CANCELADA')) if estado == 'todas' else qs.filter(estado='CANCELADA' if estado == 'CANCELADA' else 'COMPLETADA')
    qs = qs.annotate(cierre=Coalesce('fecha_validacion', 'fecha_modificacion'))
    if p.get('q'):
        t = p['q'].strip()[:100]
        qs = qs.filter(Q(titulo__icontains=t) | Q(cliente__icontains=t))
    if p.get('cliente'):
        qs = qs.filter(cliente__icontains=p['cliente'].strip()[:100])
    if p.get('persona'):
        qs = qs.filter(Q(colaborador_id=p['persona']) | Q(companeros__id=p['persona'])).distinct()
    if p.get('validador'):
        qs = qs.filter(validada_por_id=p['validador'])
    if p.get('asignador'):
        qs = qs.filter(asignada_por_id=p['asignador'])
    if p.get('departamento'):
        qs = qs.filter(colaborador__perfil__puesto_trabajo__departamento_id=p['departamento'])
    if p.get('desde'):
        qs = qs.filter(cierre__date__gte=p['desde'])
    if p.get('hasta'):
        qs = qs.filter(cierre__date__lte=p['hasta'])
    return qs.order_by('-cierre', '-id')


def _fila(t):
    puesto = _puesto(t.colaborador)
    return {
        'id': t.pk, 'titulo': t.titulo, 'cliente': t.cliente, 'estado': t.estado, 'prioridad': t.prioridad,
        'hizo': {'id': t.colaborador_id, 'nombre': _nombre(t.colaborador), 'puesto': puesto.nombre if puesto else '',
                 'departamento': puesto.departamento.nombre if puesto and puesto.departamento_id else ''},
        'companeros': [_nombre(c) for c in t.companeros.all()],
        'asigno': _nombre(t.asignada_por) if t.asignada_por_id else None,
        'valido': _nombre(t.validada_por) if t.validada_por_id else None,
        'autovalidada': bool(t.validada_por_id and t.validada_por_id == t.colaborador_id),
        'departamento_origen': t.departamento_origen.nombre if t.departamento_origen_id else None,
        'creada': t.fecha_creacion, 'limite': t.fecha_limite, 'entregada': t.fecha_entrega_real or t.fecha_completada,
        'validada': t.fecha_validacion, 'cierre': t.cierre, 'calidad': t.calificacion_calidad, 'a_tiempo': t.a_tiempo if t.estado == 'COMPLETADA' else None,
        'devoluciones': t.rondas_revision,
    }


def _celda(v):
    """Una celda de CSV segura: un texto que empieza con = + - @ se tomaría como fórmula al abrirlo en Excel."""
    s = '' if v is None else str(v)
    return "'" + s if s[:1] in ('=', '+', '-', '@', '\t', '\r') else s


@api_view(['GET'])
def historial_tareas_view(request):
    """Historial de tareas terminadas: quién la hizo, quién la asignó y quién la validó, con fechas y calidad.
    Filtros: ?estado=COMPLETADA|CANCELADA|todas &q &cliente &persona &validador &asignador &departamento &desde &hasta &pagina; ?formato=csv descarga todo."""
    qs = _filtrar(request)
    if request.query_params.get('formato') == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="historial-de-tareas.csv"'
        resp.write('﻿')
        w = csv.writer(resp)
        w.writerow(['Tarea', 'Cliente', 'Estado', 'Quién la hizo', 'Con', 'Departamento', 'Asignada por', 'Validada por', 'Autovalidada', 'Creada',
                    'Fecha límite', 'Entregada', 'Validada', 'Calidad (1-5)', 'A tiempo', 'Devoluciones'])
        for t in qs[:MAX_CSV]:
            f = _fila(t)
            w.writerow([_celda(x) for x in (f['titulo'], f['cliente'], 'Validada' if f['estado'] == 'COMPLETADA' else 'Cancelada', f['hizo']['nombre'],
                                             ', '.join(f['companeros']), f['hizo']['departamento'], f['asigno'], f['valido'], 'Sí' if f['autovalidada'] else 'No',
                                             timezone.localtime(f['creada']).strftime('%d/%m/%Y'), f['limite'], f['entregada'] and str(f['entregada'])[:16],
                                             f['validada'] and timezone.localtime(f['validada']).strftime('%d/%m/%Y %H:%M'), f['calidad'],
                                             {True: 'Sí', False: 'No', None: ''}[f['a_tiempo']], f['devoluciones'])])
        return resp
    total = qs.count()
    try:
        pagina = max(1, int(request.query_params.get('pagina', 1)))
    except ValueError:
        pagina = 1
    paginas = max(1, -(-total // PAGINA))
    pagina = min(pagina, paginas)
    filas = [_fila(t) for t in qs[(pagina - 1) * PAGINA:pagina * PAGINA]]
    return Response({'count': total, 'pagina': pagina, 'paginas': paginas, 'resultados': filas})


# ---------------------------------------------------------------------------------------------------------------------
# Panel de estados: cuántas tareas hay en cada estado, con filtros. Cada persona ve solo las estadísticas de lo que ya puede ver.
# ---------------------------------------------------------------------------------------------------------------------
GRUPOS_ESTADO = {
    'pendientes': Q(estado='PENDIENTE', rondas_revision=0),
    'en_proceso': Q(estado='EN_PROGRESO', rondas_revision=0),
    'devueltas': Q(estado__in=('PENDIENTE', 'EN_PROGRESO'), rondas_revision__gt=0),   # el supervisor las devolvió para corregir
    'por_validar': Q(estado='EN_REVISION'),
    'aprobadas': Q(estado='COMPLETADA'),
    'bloqueadas': Q(estado='BLOQUEADA'),
    'canceladas': Q(estado='CANCELADA'),
}


@api_view(['GET'])
def resumen_tareas_view(request):
    """?departamento &persona &asignador &estado=<grupo> &prioridad &desde &hasta (sobre la fecha límite). Devuelve conteos por estado,
    por prioridad y por departamento de lo que la persona puede ver."""
    from django.db.models import Count, F
    p = request.query_params
    hoy = timezone.localdate()
    qs = _visibles(request.user)
    if p.get('departamento'):
        qs = qs.filter(colaborador__perfil__puesto_trabajo__departamento_id=p['departamento'])
    if p.get('persona'):
        qs = qs.filter(Q(colaborador_id=p['persona']) | Q(companeros__id=p['persona'])).distinct()
    if p.get('asignador'):
        qs = qs.filter(asignada_por_id=p['asignador'])
    if p.get('prioridad'):
        qs = qs.filter(prioridad=p['prioridad'])
    if p.get('desde'):
        qs = qs.filter(fecha_limite__gte=p['desde'])
    if p.get('hasta'):
        qs = qs.filter(fecha_limite__lte=p['hasta'])
    if p.get('estado') == 'vencidas':
        qs = qs.filter(estado__in=ABIERTAS, fecha_limite__lt=hoy)
    elif p.get('estado') in GRUPOS_ESTADO:
        qs = qs.filter(GRUPOS_ESTADO[p['estado']])
    ids = list(qs.values_list('pk', flat=True))
    base = Tarea.objects.filter(pk__in=ids)
    conteos = {k: base.filter(q).count() for k, q in GRUPOS_ESTADO.items()}
    conteos['total'] = len(ids)
    conteos['vencidas'] = base.filter(estado__in=ABIERTAS, fecha_limite__lt=hoy).count()           # se cuentan además de su estado
    conteos['a_tiempo'] = base.filter(estado='COMPLETADA', fecha_completada__lte=F('fecha_limite')).count()
    conteos['fuera_de_plazo'] = base.filter(estado='COMPLETADA', fecha_completada__gt=F('fecha_limite')).count()
    por_prioridad = dict(base.values_list('prioridad').annotate(n=Count('pk')))
    deptos = {}
    for dep, estado, limite in base.values_list('colaborador__perfil__puesto_trabajo__departamento__nombre', 'estado', 'fecha_limite'):
        d = deptos.setdefault(dep or 'Sin departamento', {'departamento': dep or 'Sin departamento', 'total': 0, 'abiertas': 0, 'vencidas': 0, 'por_validar': 0, 'aprobadas': 0})
        d['total'] += 1
        if estado in ABIERTAS:
            d['abiertas'] += 1
            if limite < hoy:
                d['vencidas'] += 1
        elif estado == 'EN_REVISION':
            d['por_validar'] += 1
        elif estado == 'COMPLETADA':
            d['aprobadas'] += 1
    return Response({'conteos': conteos, 'por_prioridad': por_prioridad, 'por_departamento': sorted(deptos.values(), key=lambda x: -x['total']), 'hoy': hoy})
