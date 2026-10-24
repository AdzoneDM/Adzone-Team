"""
Cálculo del puntaje mensual de desempeño (0-100) de cada colaborador.

Puntaje total = 60% tareas + 40% KPIs (pesos configurables en ConfiguracionDesempeno).
Si un colaborador solo tiene una de las dos fuentes en el mes, esa fuente vale el 100%.

Tareas (cuentan las que tienen fecha límite dentro del mes, salvo canceladas):
  - Puntualidad: 100 si se completó a tiempo, 50 si se completó tarde, 0 si no se completó.
  - Calidad: calificación del administrador (1-5) convertida a 0-100.
  - Nota de la tarea = promedio de puntualidad y calidad (solo puntualidad si aún no se calificó).
  - Solo cuenta como completada una tarea VALIDADA por su supervisor o el administrador.
  - No cuentan todavía: las tareas entregadas que esperan validación, ni las
    pendientes cuya fecha límite no ha pasado.
  - Peso por prioridad: Baja 1, Media 2, Alta 3.
  - Una tarea compartida cuenta igual para el responsable y para cada compañero.

KPIs: promedio del cumplimiento de cada KPI (0-100), ponderado por la
ponderación del KPI en el puesto.
  - KPIs de entrada manual: se usa el ResultadoKPI registrado del mes.
  - KPIs que no son de entrada manual: valor = tareas validadas vinculadas al KPI
    y entregadas en el mes, contra la meta numérica mensual.
  - Si además la plantilla es «menor es mejor» (p. ej. rondas de revisión), el valor es el
    promedio de rondas de entrega de esas tareas (1 = aprobada a la primera).
"""
import calendar

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from apps.kpis.models import KPIAsignado

from .models import ConfiguracionDesempeno, Tarea, ResultadoKPI

PESO_PRIORIDAD = {'BAJA': 1, 'MEDIA': 2, 'ALTA': 3}


def rango_del_mes(periodo):
    ultimo_dia = calendar.monthrange(periodo.year, periodo.month)[1]
    return periodo.replace(day=1), periodo.replace(day=ultimo_dia)


def nota_tarea(tarea, nota_tarde=50):
    if tarea.estado != 'COMPLETADA':
        return 0.0
    puntualidad = 100.0 if tarea.a_tiempo else float(nota_tarde)
    if tarea.calificacion_calidad is None:
        return puntualidad
    calidad = (tarea.calificacion_calidad - 1) / 4 * 100
    return (puntualidad + calidad) / 2


def cumplimiento(meta, real, menor_es_mejor=False):
    """Porcentaje de cumplimiento de una meta, entre 0 y 100."""
    meta, real = float(meta), float(real)
    if menor_es_mejor:
        porcentaje = 100.0 if real <= 0 else meta / real * 100
    else:
        porcentaje = 100.0 if meta <= 0 else real / meta * 100
    return max(0.0, min(100.0, porcentaje))


def _puntaje_tareas(tareas, hoy, nota_tarde=50):
    suma, pesos = 0.0, 0
    calidad, calificadas = 0, 0
    resumen = {'total': 0, 'completadas': 0, 'a_tiempo': 0, 'a_la_primera': 0, 'vencidas': 0,
               'en_plazo': 0, 'por_validar': 0, 'calidad_promedio': None}
    for tarea in tareas:
        if tarea.estado == 'EN_REVISION':
            resumen['por_validar'] += 1
            continue
        if tarea.estado != 'COMPLETADA' and tarea.fecha_limite >= hoy:
            resumen['en_plazo'] += 1
            continue
        resumen['total'] += 1
        if tarea.estado == 'COMPLETADA':
            resumen['completadas'] += 1
            if tarea.a_tiempo:
                resumen['a_tiempo'] += 1
            if tarea.rondas_revision == 0:
                resumen['a_la_primera'] += 1
            if tarea.calificacion_calidad:
                calidad += tarea.calificacion_calidad
                calificadas += 1
        else:
            resumen['vencidas'] += 1
        peso = PESO_PRIORIDAD.get(tarea.prioridad, 2)
        suma += nota_tarea(tarea, nota_tarde) * peso
        pesos += peso
    if calificadas:
        resumen['calidad_promedio'] = round(calidad / calificadas, 2)
    puntaje = round(suma / pesos, 2) if pesos else None
    return puntaje, resumen


def _puntaje_kpis(detalle):
    suma, pesos = 0.0, 0.0
    for kpi in detalle:
        peso = kpi['ponderacion'] or 1.0
        suma += kpi['cumplimiento'] * peso
        pesos += peso
    return round(suma / pesos, 2) if pesos else None


def kpis_del_mes(usuario, inicio, fin, resultados_manuales=()):
    """Detalle de cada KPI del puesto del colaborador con su cumplimiento en el mes."""
    puesto = getattr(getattr(usuario, 'perfil', None), 'puesto_trabajo', None)
    if puesto is None:
        return []
    manuales = {r.kpi_asignado_id: r for r in resultados_manuales}
    detalle = []
    asignados = KPIAsignado.objects.filter(puesto_trabajo=puesto, activo=True).select_related('plantilla_kpi')
    for kpi in asignados:
        plantilla = kpi.plantilla_kpi
        fila = {
            'kpi_asignado_id': kpi.id,
            'nombre': plantilla.nombre,
            'unidad_medida': plantilla.unidad_medida,
            'ponderacion': float(kpi.ponderacion),
            'automatico': not kpi.es_entrada_manual,
        }
        if kpi.es_entrada_manual:
            resultado = manuales.get(kpi.id)
            if resultado is None:
                continue
            fila.update(meta=float(resultado.valor_meta), valor=float(resultado.valor_real),
                        cumplimiento=resultado.cumplimiento)
        else:
            if not kpi.meta_numerica:
                continue
            validadas = Tarea.objects.filter(
                Q(colaborador=usuario) | Q(companeros=usuario), kpi_asignado=kpi, estado='COMPLETADA',
                fecha_completada__range=(inicio, fin),
            ).distinct()
            if plantilla.menor_es_mejor:
                # Rondas de entrega promedio (1 = aprobada a la primera, 2 = una devolución…)
                rondas = [t.rondas_revision + 1 for t in validadas]
                if not rondas:
                    continue
                valor = round(sum(rondas) / len(rondas), 2)
            else:
                valor = validadas.count()
            fila.update(meta=float(kpi.meta_numerica), valor=valor,
                        cumplimiento=cumplimiento(kpi.meta_numerica, valor, plantilla.menor_es_mejor))
        fila['cumplimiento'] = round(fila['cumplimiento'], 2)
        detalle.append(fila)
    return detalle


def calcular_ranking(periodo, hoy=None, config=None):
    """Devuelve la lista de colaboradores evaluados en el mes, ordenada de mayor a menor puntaje."""
    hoy = hoy or timezone.localdate()
    config = config or ConfiguracionDesempeno.actual()
    peso_tareas = config.peso_tareas / 100
    inicio, fin = rango_del_mes(periodo)

    tareas_por_usuario = {}
    tareas = Tarea.objects.filter(fecha_limite__range=(inicio, fin)).exclude(estado='CANCELADA').prefetch_related('companeros')
    for tarea in tareas:
        # Una tarea compartida cuenta para el responsable y para cada compañero.
        for participante in tarea.participantes_ids():
            tareas_por_usuario.setdefault(participante, []).append(tarea)

    resultados_por_usuario = {}
    resultados = ResultadoKPI.objects.filter(periodo=inicio).select_related('kpi_asignado__plantilla_kpi')
    for resultado in resultados:
        resultados_por_usuario.setdefault(resultado.colaborador_id, []).append(resultado)

    ids = set(tareas_por_usuario) | set(resultados_por_usuario)
    usuarios = User.objects.filter(id__in=ids, is_active=True).select_related('perfil__puesto_trabajo__departamento')

    ranking = []
    for usuario in usuarios:
        puntaje_tareas, resumen_tareas = _puntaje_tareas(tareas_por_usuario.get(usuario.id, []), hoy, config.nota_tarde)
        detalle_kpis = kpis_del_mes(usuario, inicio, fin, resultados_por_usuario.get(usuario.id, []))
        puntaje_kpis = _puntaje_kpis(detalle_kpis)

        if puntaje_tareas is not None and puntaje_kpis is not None:
            total = puntaje_tareas * peso_tareas + puntaje_kpis * (1 - peso_tareas)
        elif puntaje_tareas is not None:
            total = puntaje_tareas
        elif puntaje_kpis is not None:
            total = puntaje_kpis
        else:
            continue  # Solo tiene tareas aún en plazo: no se evalúa todavía

        puesto = getattr(getattr(usuario, 'perfil', None), 'puesto_trabajo', None)
        ranking.append({
            'colaborador_id': usuario.id,
            'username': usuario.username,
            'nombre': usuario.get_full_name() or usuario.username,
            'puesto': puesto.nombre if puesto else None,
            'departamento_id': puesto.departamento_id if puesto else None,
            'departamento': puesto.departamento.nombre if puesto else None,
            'puntaje_tareas': puntaje_tareas,
            'puntaje_kpis': puntaje_kpis,
            'puntaje_total': round(total, 2),
            'tareas': resumen_tareas,
            'kpis_registrados': len(detalle_kpis),
            'kpis': detalle_kpis,
            # Con pocas tareas validadas el puntaje no es representativo: ni candidato ni bono.
            'elegible': resumen_tareas['completadas'] >= config.minimo_tareas_empleado_mes,
            'bono_sugerido': (config.bono_para(round(total, 2))
                              if resumen_tareas['completadas'] >= config.minimo_tareas_empleado_mes else 0),
        })

    ranking.sort(key=lambda fila: (-fila['puntaje_total'], fila['nombre']))
    for posicion, fila in enumerate(ranking, start=1):
        fila['posicion'] = posicion
    return ranking
