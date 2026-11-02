"""
Cálculo del puntaje mensual de desempeño (0-100) de cada colaborador.

Puntaje total = 48% tareas + 32% KPIs + 20% jornada (pesos configurables en ConfiguracionDesempeno).
Si a un colaborador le falta alguna de las tres en el mes, las que tiene se reparten el 100 %.

Jornada (control de horario y monitoreo): promedio de la adherencia al horario (puntualidad, asistencia y
horas cumplidas) y, si su computadora reporta, la productividad contra la meta (75 % por defecto).

Tareas (cuentan las que tienen fecha límite dentro del mes, salvo canceladas):
  - Puntualidad: 100 si se completó a tiempo, 50 si se completó tarde, 0 si no se completó.
  - Calidad: calificación del administrador (1-5) convertida a 0-100.
  - Nota de la tarea = promedio de puntualidad y calidad (solo puntualidad si aún no se calificó).
  - Solo cuenta como completada una tarea VALIDADA por su supervisor o el administrador.
  - No cuentan todavía: las tareas entregadas que esperan validación, ni las
    pendientes cuya fecha límite no ha pasado.
  - Peso por prioridad: Baja 1, Media 2, Alta 3.
  - Una tarea compartida cuenta igual para el responsable y para cada compañero.

Evaluación contra el mínimo (ConfiguracionDesempeno.puntaje_minimo):
  - CUMPLE: puntaje total igual o mayor que el mínimo.
  - BAJO_MINIMO: puntaje total menor que el mínimo, con datos suficientes.
  - POCOS_DATOS: menos de `minimo_tareas_evaluacion` tareas que ya cuentan y ningún KPI medido.
    Un puntaje con una o dos tareas no es base para decidir sobre una persona.
  - Quien tiene puesto y no tiene nada evaluado en el mes no entra al ranking: sale en `sin_evaluar`.

Grupos: los agentes de call center (acceso «Agente Call Center») se evalúan aparte del resto.
  grupo='empleados' deja fuera a los agentes, grupo='agentes' deja solo a los agentes y None, a todos.

KPIs: promedio del cumplimiento de cada KPI (0-100), ponderado por la
ponderación del KPI en el puesto.
  - KPIs de entrada manual: se usa el ResultadoKPI registrado del mes.
  - KPIs que no son de entrada manual: valor = tareas validadas vinculadas al KPI
    y entregadas en el mes, contra la meta numérica mensual.
  - Si además la plantilla es «menor es mejor» (p. ej. rondas de revisión), el valor es el
    promedio de rondas de entrega de esas tareas (1 = aprobada a la primera).
  - Si la plantilla tiene «fuente» (puntualidad, asistencia, entregas a tiempo, productividad en PC…), el valor
    lo calcula la plataforma con esa fuente (ver `medir`). Sin datos en el mes, el KPI no cuenta.
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


def _tareas_validadas(usuario, inicio, fin):
    return Tarea.objects.filter(Q(colaborador=usuario) | Q(companeros=usuario), estado='COMPLETADA',
                                fecha_completada__range=(inicio, fin)).distinct()


class Mediciones:
    """Calcula una sola vez por persona y mes lo que piden los KPIs automáticos y la jornada."""

    def __init__(self, usuario, inicio, fin):
        self.usuario, self.inicio, self.fin = usuario, inicio, fin
        self._asistencia = self._pc = self._tareas = None

    @property
    def asistencia(self):
        if self._asistencia is None:
            from apps.asistencia.servicios import adherencia, resumen
            r = resumen(self.usuario, self.inicio, self.fin)
            r['adherencia'] = adherencia(r)
            self._asistencia = r
        return self._asistencia

    @property
    def pc(self):
        if self._pc is None:
            from apps.monitoreo.servicios import indicadores_pc
            self._pc = indicadores_pc([self.usuario.pk], self.inicio, self.fin).get(self.usuario.pk, {})
        return self._pc

    @property
    def tareas(self):
        if self._tareas is None:
            self._tareas = list(_tareas_validadas(self.usuario, self.inicio, self.fin))
        return self._tareas

    def medir(self, fuente):
        """Valor del mes para una fuente automática, o None si no hay datos."""
        t = self.tareas
        if fuente == 'ENTREGAS_A_TIEMPO':
            return round(sum(1 for x in t if x.a_tiempo) / len(t) * 100, 1) if t else None
        if fuente == 'PRIMERA':
            return round(sum(1 for x in t if not x.rondas_revision) / len(t) * 100, 1) if t else None
        if fuente == 'RONDAS':
            return round(sum(x.rondas_revision + 1 for x in t) / len(t), 2) if t else None
        if fuente == 'CALIDAD':
            notas = [x.calificacion_calidad for x in t if x.calificacion_calidad]
            return round(sum(notas) / len(notas) / 5 * 100, 1) if notas else None
        a = self.asistencia
        if fuente == 'PUNTUALIDAD':
            return a['puntualidad']
        if fuente == 'ASISTENCIA':
            return a['asistencia']
        if fuente == 'HORAS':
            return min(a['cumplimiento_horas'], 100) if a['cumplimiento_horas'] is not None else None
        if fuente == 'ADHERENCIA':
            return a['adherencia']
        if fuente == 'ACTIVIDAD_PC':
            return self.pc.get('actividad')
        if fuente == 'PRODUCTIVIDAD_PC':
            return self.pc.get('productividad')
        return None

    def jornada(self, meta_productividad=75):
        """Puntaje de jornada 0-100 y su detalle, o (None, detalle) si no hay datos de horario ni de PC."""
        a = self.asistencia
        partes = []
        if a['adherencia'] is not None and a['dias_laborables']:
            partes.append(a['adherencia'])
        prod = self.pc.get('productividad')
        if prod is not None and self.pc.get('minutos_activos', 0) >= 60:
            partes.append(min(prod / meta_productividad * 100, 100) if meta_productividad else prod)
        detalle = {k: a[k] for k in ('puntualidad', 'asistencia', 'cumplimiento_horas', 'adherencia', 'tardanzas',
                                     'minutos_tarde', 'ausencias', 'minutos_trabajados', 'minutos_extra', 'dias_laborables')}
        detalle.update({k: self.pc.get(k) for k in ('actividad', 'productividad', 'minutos_activos', 'minutos_registrados')})
        return (round(sum(partes) / len(partes), 2) if partes else None), detalle


def kpis_del_mes(usuario, inicio, fin, resultados_manuales=(), mediciones=None):
    """Detalle de cada KPI del puesto del colaborador con su cumplimiento en el mes."""
    puesto = getattr(getattr(usuario, 'perfil', None), 'puesto_trabajo', None)
    if puesto is None:
        return []
    manuales = {r.kpi_asignado_id: r for r in resultados_manuales}
    mediciones = mediciones or Mediciones(usuario, inicio, fin)
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
            'fuente': plantilla.fuente if not kpi.es_entrada_manual else '',
        }
        if kpi.es_entrada_manual:
            resultado = manuales.get(kpi.id)
            if resultado is None:
                continue
            fila.update(meta=float(resultado.valor_meta), valor=float(resultado.valor_real),
                        cumplimiento=resultado.cumplimiento)
        elif plantilla.fuente:
            valor = mediciones.medir(plantilla.fuente)
            if valor is None or kpi.meta_numerica is None:
                continue
            fila.update(meta=float(kpi.meta_numerica), valor=valor,
                        cumplimiento=cumplimiento(kpi.meta_numerica, valor, plantilla.menor_es_mejor))
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


def motivos_bajo_puntaje(fila, nota_tarde=50):
    """Lo que más le baja el puntaje a una persona, en frases cortas para explicar la evaluación."""
    t = fila['tareas']
    motivos = []
    if t['vencidas']:
        motivos.append(f"{t['vencidas']} tarea(s) vencida(s) sin entregar")
    tarde = t['completadas'] - t['a_tiempo']
    if tarde:
        motivos.append(f"{tarde} entregada(s) tarde")
    if t['calidad_promedio'] is not None and t['calidad_promedio'] < 3:
        motivos.append(f"calidad promedio {t['calidad_promedio']} de 5")
    j = fila.get('jornada_detalle') or {}
    if j.get('tardanzas'):
        motivos.append(f"{j['tardanzas']} llegada(s) tarde ({j['minutos_tarde']} min)")
    if j.get('ausencias'):
        motivos.append(f"{j['ausencias']} ausencia(s) sin permiso")
    if j.get('productividad') is not None and j['productividad'] < 60:
        motivos.append(f"productividad en computadora de {round(j['productividad'])} %")
    for kpi in fila['kpis']:
        if kpi['cumplimiento'] < 70:
            motivos.append(f"KPI «{kpi['nombre']}» al {round(kpi['cumplimiento'])} %")
    return motivos


def evaluar(fila, config):
    datos_suficientes = (fila['tareas']['total'] >= config.minimo_tareas_evaluacion or fila['kpis_registrados'] > 0
                         or (fila.get('jornada_detalle') or {}).get('dias_laborables', 0) >= 5)
    if not datos_suficientes:
        return 'POCOS_DATOS'
    return 'CUMPLE' if fila['puntaje_total'] >= config.puntaje_minimo else 'BAJO_MINIMO'


GRUPO_AGENTE = 'Agente Call Center'


def filtrar_grupo(usuarios, grupo):
    if grupo == 'agentes':
        return usuarios.filter(groups__name=GRUPO_AGENTE)
    if grupo == 'empleados':
        return usuarios.exclude(groups__name=GRUPO_AGENTE)
    return usuarios


def sin_evaluar(periodo, ranking, hoy=None, grupo=None):
    """Personas activas con puesto que no tienen nada evaluado en el mes (no salen en el ranking).

    Sin tareas que ya cuenten ni KPIs no hay base para juzgar su desempeño: hay que revisar
    primero si se les asignó trabajo y si su supervisor lo registra en la plataforma.
    """
    hoy = hoy or timezone.localdate()
    inicio, fin = rango_del_mes(periodo)
    evaluados = {f['colaborador_id'] for f in ranking}
    personas = (filtrar_grupo(User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=False), grupo)
                .exclude(id__in=evaluados)
                .select_related('perfil__puesto_trabajo__departamento', 'perfil__puesto_trabajo__supervisor'))
    supervisores = {}
    for u in User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=False).select_related('perfil'):
        supervisores.setdefault(u.perfil.puesto_trabajo_id, []).append(u.get_full_name() or u.username)
    filas = []
    for usuario in personas:
        puesto = usuario.perfil.puesto_trabajo
        tareas = Tarea.objects.filter(Q(colaborador=usuario) | Q(companeros=usuario),
                                      fecha_limite__range=(inicio, fin)).exclude(estado='CANCELADA').distinct()
        filas.append({
            'colaborador_id': usuario.id,
            'nombre': usuario.get_full_name() or usuario.username,
            'puesto': puesto.nombre,
            'departamento_id': puesto.departamento_id,
            'departamento': puesto.departamento.nombre if puesto.departamento_id else None,
            'supervisor': ', '.join(supervisores.get(puesto.supervisor_id, [])) if puesto.supervisor_id else '',
            'tareas_asignadas': tareas.count(),
            'por_validar': tareas.filter(estado='EN_REVISION').count(),
        })
    filas.sort(key=lambda f: (f['departamento'] or '', f['nombre']))
    return filas


def _meta_productividad():
    from apps.monitoreo.models import ConfiguracionMonitoreo
    return ConfiguracionMonitoreo.actual().meta_productividad_pct


def calcular_ranking(periodo, hoy=None, config=None, grupo=None):
    """Devuelve la lista de colaboradores evaluados en el mes, ordenada de mayor a menor puntaje."""
    hoy = hoy or timezone.localdate()
    config = config or ConfiguracionDesempeno.actual()
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

    from apps.asistencia.models import Marcaje
    con_jornada = set(Marcaje.objects.filter(momento__date__range=(inicio, fin)).values_list('usuario_id', flat=True)) if config.peso_jornada else set()
    ids = set(tareas_por_usuario) | set(resultados_por_usuario) | con_jornada
    usuarios = filtrar_grupo(User.objects.filter(id__in=ids, is_active=True), grupo).select_related('perfil__puesto_trabajo__departamento')

    ranking = []
    for usuario in usuarios:
        puntaje_tareas, resumen_tareas = _puntaje_tareas(tareas_por_usuario.get(usuario.id, []), hoy, config.nota_tarde)
        mediciones = Mediciones(usuario, inicio, fin)
        detalle_kpis = kpis_del_mes(usuario, inicio, fin, resultados_por_usuario.get(usuario.id, []), mediciones)
        puntaje_kpis = _puntaje_kpis(detalle_kpis)
        puntaje_jornada, detalle_jornada = (mediciones.jornada(_meta_productividad()) if usuario.id in con_jornada
                                            else (None, {}))

        partes = [(p, w) for p, w in ((puntaje_tareas, config.peso_tareas), (puntaje_kpis, config.peso_kpis),
                                      (puntaje_jornada, config.peso_jornada)) if p is not None and w > 0]
        if not partes:
            continue  # Solo tiene tareas aún en plazo: no se evalúa todavía
        total = sum(p * w for p, w in partes) / sum(w for _, w in partes)

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
            'puntaje_jornada': puntaje_jornada,
            'jornada_detalle': detalle_jornada,
            'puntaje_total': round(total, 2),
            'tareas': resumen_tareas,
            'kpis_registrados': len(detalle_kpis),
            'kpis': detalle_kpis,
            # Con pocas tareas validadas el puntaje no es representativo: ni candidato ni bono.
            'elegible': resumen_tareas['completadas'] >= config.minimo_tareas_empleado_mes,
            'bono_sugerido': (config.bono_para(round(total, 2))
                              if resumen_tareas['completadas'] >= config.minimo_tareas_empleado_mes else 0),
        })
        ranking[-1]['evaluacion'] = evaluar(ranking[-1], config)
        ranking[-1]['motivos'] = motivos_bajo_puntaje(ranking[-1]) if ranking[-1]['evaluacion'] == 'BAJO_MINIMO' else []

    ranking.sort(key=lambda fila: (-fila['puntaje_total'], fila['nombre']))
    for posicion, fila in enumerate(ranking, start=1):
        fila['posicion'] = posicion
    return ranking
