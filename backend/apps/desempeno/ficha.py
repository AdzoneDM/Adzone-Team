"""
Ficha de productividad: todo lo que la plataforma mide de una persona en un mes, en un solo lugar.

Junta el puntaje (tareas, KPIs y jornada), el control de horario, la actividad en la computadora, el tiempo
registrado en tareas y señales de riesgo (sobrecarga, baja actividad, tendencia a la baja).
"""
from datetime import timedelta

from django.db.models import Count

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


def ficha(usuario, periodo, visor=None, meses=6):
    inicio, fin = rango_del_mes(periodo)
    config = ConfiguracionDesempeno.actual()
    fila = next(iter(calcular_ranking(periodo, config=config, solo=usuario.pk)), None)
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
    for n in range(min(max(meses, 3), 12) - 1, -1, -1):
        p = _mes_anterior(periodo, n)
        i, f = rango_del_mes(p)
        m = Mediciones(usuario, i, f)
        fila_mes = fila if n == 0 else next(iter(calcular_ranking(p, config=config, solo=usuario.pk)), None)
        tendencia.append({'mes': f'{p:%Y-%m}', 'puntaje': fila_mes['puntaje_total'] if fila_mes else None,
                          'adherencia': m.asistencia['adherencia'], 'productividad': m.pc.get('productividad'),
                          'a_tiempo': m.medir('ENTREGAS_A_TIEMPO'), 'calidad': m.medir('CALIDAD')})
    con_datos = [x['puntaje'] for x in tendencia if x['puntaje'] is not None]
    if len(con_datos) >= 3 and con_datos[-1] < con_datos[-2] < con_datos[-3]:
        alertas.append({'tipo': 'tendencia', 'texto': f"El puntaje baja tres meses seguidos ({con_datos[-3]:g} → {con_datos[-2]:g} → {con_datos[-1]:g})."})
    puesto = getattr(getattr(usuario, 'perfil', None), 'puesto_trabajo', None)
    return {
        'persona': {'id': usuario.pk, 'nombre': usuario.get_full_name() or usuario.username,
                    'puesto': puesto.nombre if puesto else None, 'departamento': puesto.departamento.nombre if puesto else None},
        'mes': f'{periodo:%Y-%m}',
        'puntaje': {k: fila[k] for k in ('puntaje_total', 'puntaje_tareas', 'puntaje_kpis', 'puntaje_jornada', 'puntaje_calidad', 'evaluacion',
                                         'motivos', 'bono_sugerido')} if fila else None,
        'pesos': {'tareas': config.peso_tareas, 'kpis': config.peso_kpis, 'calidad': config.peso_calidad, 'jornada': config.peso_jornada},
        'kpis': fila['kpis'] if fila else kpis_del_mes(usuario, inicio, fin, mediciones=med),
        'tareas': tareas,
        'horario': {**a, 'adherencia': a['adherencia']},
        'computadora': {k: pc[k] for k in pc if k not in ()},
        'tiempo': {'minutos_en_tareas': minutos_tareas, 'utilizacion': utilizacion},
        'alertas': alertas,
        'tendencia': tendencia,
        'talento': _talento(usuario, visor or usuario),
    }


def _talento(usuario, visor):
    """Evaluaciones 360°, planes de mejora y expediente, con lo que el visor puede ver."""
    from apps.talento import servicios as talento
    from apps.talento.models import CambioSalarial, CicloEvaluacion, EventoExpediente, PlanMejora
    from .permisos import es_administrador
    admin = es_administrador(visor)
    ciclo = CicloEvaluacion.objects.filter(evaluaciones__evaluado=usuario).distinct().first()
    eventos = EventoExpediente.objects.filter(colaborador=usuario).select_related('registrado_por')
    if visor.pk == usuario.pk and not admin:
        eventos = eventos.filter(visible_al_colaborador=True)
    resumen = {}
    for tipo, n in eventos.values_list('tipo').annotate(n=Count('id')):
        resumen[tipo] = n
    datos = {
        'evaluacion': talento.resultados(ciclo, usuario) if ciclo else None,
        'planes': [{'id': p.id, 'motivo': p.motivo, 'estado': p.get_estado_display(), 'revision': p.revision,
                    'objetivos': p.objetivos, 'cumplidos': sum(1 for o in p.objetivos if o.get('cumplido'))}
                   for p in PlanMejora.objects.filter(colaborador=usuario)[:5]],
        'expediente': [{'id': e.id, 'tipo': e.tipo, 'tipo_nombre': e.get_tipo_display(), 'fecha': e.fecha, 'titulo': e.titulo,
                        'descripcion': e.descripcion, 'justificacion': e.justificacion, 'visible': e.visible_al_colaborador,
                        'horas': float(e.horas) if e.horas is not None else None,
                        'monto': float(e.monto) if admin and e.monto is not None else None,
                        'registrado_por': (e.registrado_por.get_full_name() or e.registrado_por.username) if e.registrado_por else None}
                       for e in eventos[:30]],
        'resumen_expediente': resumen,
        'horas_capacitacion': float(sum(e.horas or 0 for e in eventos.filter(tipo='CAPACITACION'))),
    }
    if admin:
        datos['salarios'] = [{'fecha': c.fecha, 'anterior': float(c.anterior) if c.anterior is not None else None,
                              'nuevo': float(c.nuevo) if c.nuevo is not None else None, 'motivo': c.motivo}
                             for c in CambioSalarial.objects.filter(usuario=usuario)[:12]]
    return datos
