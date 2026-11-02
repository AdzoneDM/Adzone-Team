"""
Ficha de productividad: todo lo que la plataforma mide de una persona en un mes, en un solo lugar.

Junta el puntaje (tareas, KPIs y jornada), el control de horario, la actividad en la computadora, el tiempo
registrado en tareas y señales de riesgo (sobrecarga, baja actividad, tendencia a la baja).
"""
from datetime import timedelta

from django.utils import timezone

from apps.asistencia import servicios as asistencia
from apps.monitoreo import servicios as monitoreo
from apps.tiempo.servicios import minutos_por_usuario
from .models import ConfiguracionDesempeno
from .puntaje import Mediciones, _puntaje_tareas, calcular_ranking, kpis_del_mes, rango_del_mes


def _mes_anterior(periodo, n):
    for _ in range(n):
        periodo = (periodo.replace(day=1) - timedelta(days=1)).replace(day=1)
    return periodo


def ficha(usuario, periodo):
    inicio, fin = rango_del_mes(periodo)
    config = ConfiguracionDesempeno.actual()
    fila = next((f for f in calcular_ranking(periodo, config=config) if f['colaborador_id'] == usuario.pk), None)
    med = Mediciones(usuario, inicio, fin)
    a = med.asistencia
    pc = monitoreo.resumen_periodo(usuario, inicio, fin)
    minutos_tareas = minutos_por_usuario(inicio, fin, [usuario]).get(usuario.pk, 0)
    t = med.tareas
    tareas = {
        'validadas': len(t),
        'a_tiempo_pct': med.medir('ENTREGAS_A_TIEMPO'), 'a_la_primera_pct': med.medir('PRIMERA'),
        'rondas_promedio': med.medir('RONDAS'), 'calidad_pct': med.medir('CALIDAD'),
    }
    utilizacion = round(minutos_tareas / a['minutos_trabajados'] * 100, 1) if a['minutos_trabajados'] else None
    alertas = []
    if a['minutos_extra'] >= 10 * 60:
        alertas.append({'tipo': 'sobrecarga', 'texto': f"{round(a['minutos_extra'] / 60, 1)} horas extra en el mes: riesgo de agotamiento."})
    if a['tardanzas'] >= 3:
        alertas.append({'tipo': 'puntualidad', 'texto': f"{a['tardanzas']} llegadas tarde ({a['minutos_tarde']} minutos)."})
    if a['ausencias']:
        alertas.append({'tipo': 'asistencia', 'texto': f"{a['ausencias']} ausencia(s) sin permiso."})
    if a['sin_salida']:
        alertas.append({'tipo': 'marcaje', 'texto': f"{a['sin_salida']} día(s) sin marcar salida."})
    if pc['actividad'] is not None and pc['actividad'] < 60:
        alertas.append({'tipo': 'actividad', 'texto': f"Solo {pc['actividad']} % del tiempo en jornada con actividad en la computadora."})
    if pc['improductividad'] is not None and pc['improductividad'] >= 20:
        alertas.append({'tipo': 'improductivo', 'texto': f"{pc['improductividad']} % del tiempo activo en apps o sitios improductivos."})
    if pc['cambios_por_hora'] is not None and pc['cambios_por_hora'] > 60:
        alertas.append({'tipo': 'foco', 'texto': f"{pc['cambios_por_hora']} cambios de ventana por hora: mucha interrupción."})
    if utilizacion is not None and a['minutos_trabajados'] >= 20 * 60 and utilizacion < 30:
        alertas.append({'tipo': 'registro', 'texto': f"Solo {utilizacion} % de la jornada registrado en tareas con el cronómetro."})

    tendencia = []
    for n in range(5, -1, -1):
        p = _mes_anterior(periodo, n)
        i, f = rango_del_mes(p)
        m = Mediciones(usuario, i, f)
        tendencia.append({'mes': f'{p:%Y-%m}', 'adherencia': m.asistencia['adherencia'], 'productividad': m.pc.get('productividad'),
                          'a_tiempo': m.medir('ENTREGAS_A_TIEMPO'), 'calidad': m.medir('CALIDAD')})
    puesto = getattr(getattr(usuario, 'perfil', None), 'puesto_trabajo', None)
    return {
        'persona': {'id': usuario.pk, 'nombre': usuario.get_full_name() or usuario.username,
                    'puesto': puesto.nombre if puesto else None, 'departamento': puesto.departamento.nombre if puesto else None},
        'mes': f'{periodo:%Y-%m}',
        'puntaje': {k: fila[k] for k in ('puntaje_total', 'puntaje_tareas', 'puntaje_kpis', 'puntaje_jornada', 'evaluacion',
                                         'motivos', 'bono_sugerido', 'posicion')} if fila else None,
        'pesos': {'tareas': config.peso_tareas, 'kpis': config.peso_kpis, 'jornada': config.peso_jornada},
        'kpis': fila['kpis'] if fila else kpis_del_mes(usuario, inicio, fin, mediciones=med),
        'tareas': tareas,
        'horario': {**a, 'adherencia': a['adherencia']},
        'computadora': {k: pc[k] for k in pc if k not in ()},
        'tiempo': {'minutos_en_tareas': minutos_tareas, 'utilizacion': utilizacion},
        'alertas': alertas,
        'tendencia': tendencia,
    }
