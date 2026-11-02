"""Panel gerencial de la Dirección: la empresa completa en una pantalla, con alertas para decidir."""
from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, F, Sum
from django.utils import timezone

from .puntaje import calcular_ranking, rango_del_mes

ACUMULACION_POR_PERSONA = 2   # tareas vencidas sin entregar por persona a partir de las cuales el área está acumulando
MESES_BAJANDO = 3             # meses seguidos bajando para alertar
COSTO_SOBRE_MONTO = 0.6       # la mano de obra no debería pasar del 60 % del monto vendido de la OT


def _mes_anterior(periodo, n=1):
    for _ in range(n):
        periodo = (periodo.replace(day=1) - timedelta(days=1)).replace(day=1)
    return periodo


def _prom(valores):
    v = [x for x in valores if x is not None]
    return round(sum(v) / len(v), 1) if v else None


def _pct(a, b):
    return round(a / b * 100, 1) if b else None


def _ots_del_mes(inicio, fin):
    from apps.operaciones.models import OrdenTrabajo
    entregadas = OrdenTrabajo.objects.filter(fecha_entrega__range=(inicio, fin), estado__in=('ENTREGADA', 'CERRADA'))
    con_fecha = entregadas.exclude(fecha_compromiso__isnull=True)
    a_tiempo = sum(1 for o in con_fecha.only('fecha_entrega', 'fecha_compromiso') if o.fecha_entrega <= o.fecha_compromiso)
    return entregadas, a_tiempo, con_fecha.count()


def resumen_mes(periodo, hoy=None):
    """Indicadores de un mes (también se usan para la tendencia)."""
    from apps.desempeno.models import Tarea
    inicio, fin = rango_del_mes(periodo)
    ranking = calcular_ranking(inicio, hoy=hoy)
    entregadas, ot_a_tiempo, ot_con_fecha = _ots_del_mes(inicio, fin)
    validadas = Tarea.objects.filter(estado='COMPLETADA', fecha_completada__range=(inicio, fin))
    a_tiempo = validadas.filter(fecha_completada__lte=F('fecha_limite')).count()
    return {
        'mes': f'{inicio:%Y-%m}', 'ranking': ranking,
        'puntaje': _prom(f['puntaje_total'] for f in ranking),
        'ot_completadas': entregadas.count(), 'ot_a_tiempo': _pct(ot_a_tiempo, ot_con_fecha),
        'tareas_validadas': validadas.count(), 'tareas_a_tiempo': _pct(a_tiempo, validadas.count()),
    }


def panel(periodo, hoy=None):
    from apps.desempeno.models import Tarea
    from apps.operaciones.models import OrdenArea, OrdenTrabajo
    from apps.talento.models import COMPETENCIAS, CicloEvaluacion, Evaluacion, PlanMejora
    from apps.tiempo.models import RegistroTiempo
    hoy = hoy or timezone.localdate()
    inicio, fin = rango_del_mes(periodo)
    actual = resumen_mes(inicio, hoy)
    ranking = actual['ranking']

    personal = User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=False)
    por_depto = defaultdict(lambda: {'personas': 0, 'puntajes': [], 'asistencia': [], 'calidad': [], 'kpis': [], 'pc': [],
                                     'validadas': 0, 'vencidas': 0, 'horas': 0, 'bajo_minimo': 0})
    for nombre, n in personal.values_list('perfil__puesto_trabajo__departamento__nombre').annotate(n=Count('id')):
        por_depto[nombre or 'Sin departamento']['personas'] = n
    for f in ranking:
        d = por_depto[f['departamento'] or 'Sin departamento']
        d['puntajes'].append(f['puntaje_total'])
        d['asistencia'].append(f.get('puntaje_asistencia'))
        d['calidad'].append(f.get('puntaje_calidad'))
        d['kpis'].append(f.get('puntaje_kpis'))
        d['pc'].append((f.get('jornada_detalle') or {}).get('productividad'))
        d['bajo_minimo'] += f['evaluacion'] == 'BAJO_MINIMO'
    for nombre, n in (Tarea.objects.filter(estado='COMPLETADA', fecha_completada__range=(inicio, fin))
                      .values_list('colaborador__perfil__puesto_trabajo__departamento__nombre').annotate(n=Count('id'))):
        por_depto[nombre or 'Sin departamento']['validadas'] = n
    for nombre, n in (Tarea.objects.filter(estado__in=('PENDIENTE', 'EN_PROGRESO'), fecha_limite__lt=hoy, colaborador__is_active=True)
                      .values_list('colaborador__perfil__puesto_trabajo__departamento__nombre').annotate(n=Count('id'))):
        por_depto[nombre or 'Sin departamento']['vencidas'] = n
    for nombre, m in (RegistroTiempo.objects.filter(inicio__date__range=(inicio, fin))
                      .values_list('usuario__perfil__puesto_trabajo__departamento__nombre').annotate(m=Sum('minutos'))):
        por_depto[nombre or 'Sin departamento']['horas'] = round((m or 0) / 60, 1)

    # Tendencia de 6 meses (el actual incluido) y por departamento para detectar caídas
    meses = [actual] + [resumen_mes(_mes_anterior(inicio, i), hoy) for i in range(1, 6)]
    meses.reverse()
    tendencia_depto = defaultdict(list)
    for m in meses:
        grupos = defaultdict(list)
        for f in m['ranking']:
            grupos[f['departamento'] or 'Sin departamento'].append(f['puntaje_total'])
        for nombre in set(por_depto) | set(grupos):
            tendencia_depto[nombre].append(_prom(grupos.get(nombre, [])))

    alertas = []
    # 1) OT abiertas por encima de las horas presupuestadas, y mano de obra sobre el monto vendido
    abiertas = OrdenTrabajo.objects.filter(estado__in=OrdenTrabajo.ABIERTAS).select_related('cliente')
    estimadas = dict(OrdenArea.objects.filter(orden__in=abiertas).values_list('orden_id').annotate(h=Sum('horas_estimadas')))
    reales = dict(RegistroTiempo.objects.filter(orden__in=abiertas).values_list('orden_id').annotate(m=Sum('minutos')))
    costos = defaultdict(float)
    for r in RegistroTiempo.objects.filter(orden__in=abiertas).select_related('usuario__perfil').only('orden_id', 'minutos', 'usuario__perfil__costo_hora'):
        ch = getattr(getattr(r.usuario, 'perfil', None), 'costo_hora', None)
        if ch:
            costos[r.orden_id] += float(ch) * r.minutos / 60
    for ot in abiertas:
        est, real = estimadas.get(ot.pk), (reales.get(ot.pk) or 0) / 60
        if est and real > float(est):
            alertas.append({'tipo': 'HORAS', 'nivel': 'alta' if real > float(est) * 1.25 else 'media',
                            'titulo': f'{ot.numero or ot.solicitud} pasó sus horas presupuestadas',
                            'detalle': f'{real:.1f} h trabajadas de {float(est):.1f} h estimadas ({ot.titulo}).', 'enlace': f'/ordenes/{ot.pk}'})
        if ot.monto and costos.get(ot.pk, 0) > float(ot.monto) * COSTO_SOBRE_MONTO:
            alertas.append({'tipo': 'COSTO', 'nivel': 'alta' if costos[ot.pk] > float(ot.monto) else 'media',
                            'titulo': f'{ot.numero or ot.solicitud}: la mano de obra va en {costos[ot.pk] / float(ot.monto) * 100:.0f} % del monto',
                            'detalle': f'RD$ {costos[ot.pk]:,.0f} en horas para una OT de RD$ {float(ot.monto):,.0f}.', 'enlace': f'/ordenes/{ot.pk}'})
    # 2) Áreas acumulando trabajo vencido
    for nombre, d in por_depto.items():
        if d['personas'] and d['vencidas'] >= max(3, d['personas'] * ACUMULACION_POR_PERSONA):
            alertas.append({'tipo': 'ACUMULACION', 'nivel': 'alta' if d['vencidas'] >= d['personas'] * ACUMULACION_POR_PERSONA * 2 else 'media',
                            'titulo': f'{nombre} acumula {d["vencidas"]} tareas vencidas', 'detalle': f'{d["personas"]} personas en el área.',
                            'enlace': '/equipo'})
    # 3) Indicadores bajando varios meses seguidos
    for nombre, serie in tendencia_depto.items():
        ultimos = [v for v in serie[-(MESES_BAJANDO + 1):]]
        if len(ultimos) == MESES_BAJANDO + 1 and all(v is not None for v in ultimos) and all(b < a for a, b in zip(ultimos, ultimos[1:])):
            alertas.append({'tipo': 'TENDENCIA', 'nivel': 'media', 'titulo': f'{nombre}: el puntaje baja {MESES_BAJANDO} meses seguidos',
                            'detalle': ' → '.join(f'{v:g}' for v in ultimos), 'enlace': '/desempeno'})
    # 4) Necesidades de capacitación: competencias flojas del último ciclo y KPIs bajo umbral
    capacitacion = []
    ciclo = CicloEvaluacion.objects.first()
    if ciclo:
        notas = defaultdict(list)
        for e in Evaluacion.objects.filter(ciclo=ciclo, tipo__in=('SUPERVISOR', 'PAR'), estado__in=('ENVIADA', 'CERRADA')).select_related(
                'evaluado__perfil__puesto_trabajo__departamento'):
            p = getattr(e.evaluado.perfil, 'puesto_trabajo', None)
            depto = p.departamento.nombre if p and p.departamento_id else 'Sin departamento'
            for clave, v in (e.puntajes or {}).items():
                notas[(depto, clave)].append(v)
        nombres = dict(COMPETENCIAS)
        for (depto, clave), vals in notas.items():
            prom = sum(vals) / len(vals)
            if clave in nombres and prom < 3 and len(vals) >= 2:
                capacitacion.append({'departamento': depto, 'tema': nombres[clave], 'promedio': round(prom, 2), 'origen': f'Evaluación «{ciclo.nombre}»'})
    kpis_bajos = defaultdict(lambda: defaultdict(int))
    for f in ranking:
        for k in f.get('kpis', []) or []:
            if k.get('bajo_umbral'):
                kpis_bajos[f['departamento'] or 'Sin departamento'][k['nombre']] += 1
    for depto, kp in kpis_bajos.items():
        for nombre, n in kp.items():
            if n >= 2:
                capacitacion.append({'departamento': depto, 'tema': nombre, 'personas': n, 'origen': 'KPI bajo el umbral'})
    if capacitacion:
        alertas.append({'tipo': 'CAPACITACION', 'nivel': 'baja', 'titulo': f'{len(capacitacion)} necesidad(es) de capacitación detectadas',
                        'detalle': '; '.join(f"{c['departamento']}: {c['tema']}" for c in capacitacion[:4]), 'enlace': '/panel#capacitacion'})
    # 5) Cumplimiento: políticas sin aceptar, documentos por vencer e incidencias de alto riesgo
    from apps.talento import politicas as pol
    cumpl = pol.cumplimiento()
    sin_aceptar = sum(len(c['faltan']) for c in cumpl)
    if sin_aceptar:
        alertas.append({'tipo': 'POLITICAS', 'nivel': 'media' if sin_aceptar > 10 else 'baja',
                        'titulo': f'{sin_aceptar} aceptación(es) de políticas pendientes',
                        'detalle': '; '.join(f"{c['titulo']}: {len(c['faltan'])}" for c in cumpl if c['faltan'])[:300], 'enlace': '/politicas?ver=cumplimiento'})
    docs = pol.estado_documentos(hoy)
    if docs['vencen']:
        vencidos = sum(1 for d in docs['vencen'] if d['vencido'])
        alertas.append({'tipo': 'DOCUMENTOS', 'nivel': 'alta' if vencidos else 'media',
                        'titulo': f"{len(docs['vencen'])} documento(s) por vencer" + (f' ({vencidos} vencido(s))' if vencidos else ''),
                        'detalle': '; '.join(f"{d['persona']}: {d['titulo']} ({d['vence']:%d/%m})" for d in docs['vencen'][:4]), 'enlace': '/politicas?ver=documentos'})
    from apps.monitoreo.comportamiento import riesgo as riesgo_pc
    riesgos = [v for v in riesgo_pc(list(personal.values_list('pk', flat=True)), inicio, fin).values() if v['nivel'] in ('ALTO', 'CRITICO')]
    if riesgos:
        alertas.append({'tipo': 'RIESGO', 'nivel': 'alta', 'titulo': f'{len(riesgos)} persona(s) con riesgo alto en la computadora',
                        'detalle': 'Reglas de comportamiento: apuestas, acceso remoto, descargas, IA no aprobada…', 'enlace': '/monitoreo?ver=resumen'})
    orden_nivel = {'alta': 0, 'media': 1, 'baja': 2}
    alertas.sort(key=lambda a: orden_nivel[a['nivel']])

    departamentos = sorted(({
        'nombre': n, 'personas': d['personas'], 'evaluados': len(d['puntajes']), 'puntaje': _prom(d['puntajes']),
        'asistencia': _prom(d['asistencia']), 'calidad': _prom(d['calidad']), 'kpis': _prom(d['kpis']),
        'productividad_pc': _prom(d['pc']), 'tareas_validadas': d['validadas'], 'tareas_vencidas': d['vencidas'],
        'horas': d['horas'], 'bajo_minimo': d['bajo_minimo'], 'tendencia': tendencia_depto.get(n, []),
    } for n, d in por_depto.items() if d['personas'] or d['puntajes']), key=lambda x: x['nombre'])

    destacados = [{'id': f['colaborador_id'], 'nombre': f['nombre'], 'puesto': f['puesto'], 'puntaje': f['puntaje_total']} for f in ranking[:5]]
    atencion = [{'id': f['colaborador_id'], 'nombre': f['nombre'], 'puesto': f['puesto'], 'puntaje': f['puntaje_total'],
                 'motivos': f.get('motivos', [])} for f in ranking if f['evaluacion'] == 'BAJO_MINIMO'][:10]
    return {
        'mes': f'{inicio:%Y-%m}',
        'personal_activo': personal.count(),
        'evaluados': len(ranking),
        'puntaje_promedio': actual['puntaje'],
        'asistencia_promedio': _prom(f.get('puntaje_asistencia') for f in ranking),
        'calidad_promedio': _prom(f.get('puntaje_calidad') for f in ranking),
        'ot_completadas': actual['ot_completadas'], 'ot_a_tiempo': actual['ot_a_tiempo'],
        'ot_abiertas': abiertas.count(),
        'tareas_validadas': actual['tareas_validadas'], 'tareas_a_tiempo': actual['tareas_a_tiempo'],
        'planes_abiertos': PlanMejora.objects.filter(estado='ABIERTO').count(),
        'evaluaciones_por_revisar': Evaluacion.objects.filter(estado='EN_REVISION').count(),
        'politicas_pendientes': sin_aceptar, 'expedientes_incompletos': len(docs['faltantes']),
        'tendencia': [{k: m[k] for k in ('mes', 'puntaje', 'ot_completadas', 'ot_a_tiempo', 'tareas_validadas', 'tareas_a_tiempo')} for m in meses],
        'departamentos': departamentos, 'alertas': alertas, 'capacitacion': capacitacion,
        'destacados': destacados, 'atencion': atencion,
    }
