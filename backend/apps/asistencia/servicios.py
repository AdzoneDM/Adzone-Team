"""
Cálculo de la jornada de cada día a partir de los marcajes.

Reglas:
- Se trabaja desde ENTRADA (o REGRESO) hasta PAUSA o SALIDA.
- Tardanza: minutos entre la hora de entrada del turno y la primera ENTRADA, si pasan la tolerancia.
- Salida temprana: minutos entre la última SALIDA y la hora de salida del turno, si pasan la tolerancia.
- Almuerzo: si la persona trabajó más de 6 horas y marcó menos pausa que el almuerzo del horario, se descuenta
  la diferencia (el almuerzo no cuenta como trabajado aunque se olvide marcarlo).
- Pausas: el almuerzo se marca aparte (es_almuerzo) y se cuenta por separado de las demás pausas. Una pausa que pasa de
  `pausa_max_minutos` del horario, o un almuerzo que pasa de `almuerzo_minutos`, cuenta como exceso (y avisa: revisar_pausas).
- Horario de cada persona: el suyo propio, si no el del departamento de su puesto, si no el general.
- Día pasado sin SALIDA: se cierra a la hora de salida del turno y el día queda marcado «sin salida».
- Extra: lo trabajado por encima de lo programado, desde 15 minutos.
"""
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from .models import AlmuerzoPersonal, AsignacionHorario, Ausencia, Feriado, Horario, Marcaje

EXTRA_MINIMO = 15
DIA_LARGO = 6 * 60
TURNO_MAXIMO = timedelta(hours=16)  # una jornada abierta más de esto se da por olvidada


def rango(desde, hasta=None):
    """(inicio, fin) con hora local de un día o de un rango de días, para filtrar sin __date (usa el índice)."""
    hasta = hasta or desde
    return timezone.make_aware(datetime.combine(desde, time.min)), timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min))


def _departamento_id(usuario):
    try:
        puesto = usuario.perfil.puesto_trabajo
    except Exception:  # noqa: BLE001 (sin perfil o sin puesto)
        return None
    return puesto.departamento_id if puesto else None


def horarios_por_departamento():
    """{id de departamento: horario activo}. Si un departamento tiene varios, el primero por nombre."""
    mapa = {}
    for h in Horario.objects.filter(activo=True, departamentos__isnull=False).prefetch_related('departamentos').order_by('nombre').distinct():
        for d in h.departamentos.all():
            mapa.setdefault(d.pk, h)
    return mapa


def horario_de(usuario):
    asignacion = AsignacionHorario.objects.filter(usuario=usuario).select_related('horario').first()
    if asignacion:
        return asignacion.horario, asignacion.marca_obligatoria
    depto = _departamento_id(usuario)
    if depto:
        propio = Horario.objects.filter(activo=True, departamentos=depto).order_by('nombre').first()
        if propio:
            return propio, True
    return Horario.objects.filter(por_defecto=True, activo=True).first(), True


def almuerzo_inicio_de(usuario, horario=None):
    """Hora de almuerzo de la persona: la que ella eligió o, si no, la del horario («HH:MM» o None)."""
    propia = AlmuerzoPersonal.objects.filter(usuario=usuario).values_list('hora', flat=True).first()
    if propia:
        return propia
    return (horario.almuerzo_inicio or None) if horario else None


def _hora(texto):
    h, m = texto.split(':')
    return time(int(h), int(m))


def _aware(dia, hora):
    return timezone.make_aware(datetime.combine(dia, hora))


def _segundos(delta):
    """Segundos exactos (con fracción) de un intervalo. Todo el cálculo de la jornada se hace en segundos: se redondea una
    sola vez, al final y sobre el total, nunca tramo por tramo (si no, se pierden hasta 59 s en cada entrada y salida)."""
    return max(0.0, delta.total_seconds())


def _enteros(segundos):
    return int(segundos)  # al segundo, hacia abajo, solo sobre totales


def _min(segundos):
    return int(segundos // 60)


def estado_actual(usuario, ahora=None):
    """FUERA, TRABAJANDO o EN_PAUSA según el último marcaje de hoy."""
    ahora = ahora or timezone.now()
    # El último marcaje de las últimas 16 h (no «de hoy»): un turno que pasa de medianoche sigue abierto.
    ultimo = Marcaje.objects.filter(usuario=usuario, momento__gt=ahora - TURNO_MAXIMO, momento__lte=ahora).order_by('-momento').first()
    if ultimo is None or ultimo.tipo == Marcaje.SALIDA:
        return 'FUERA', ultimo
    if ultimo.tipo == Marcaje.PAUSA:
        return 'EN_PAUSA', ultimo
    return 'TRABAJANDO', ultimo


def en_jornada(usuario, ahora=None):
    return estado_actual(usuario, ahora)[0] == 'TRABAJANDO'


SIGUIENTES = {'FUERA': [Marcaje.ENTRADA], 'TRABAJANDO': [Marcaje.PAUSA, Marcaje.SALIDA], 'EN_PAUSA': [Marcaje.REGRESO, Marcaje.SALIDA]}


def marcar(usuario, tipo, origen='WEB', ip=None, motivo='', nota='', momento=None, lugar=None, almuerzo=False):
    """Registra un marcaje si tiene sentido según el estado actual. Devuelve (marcaje, error).
    `almuerzo`: la pausa que empieza es el almuerzo (se cuenta aparte de las demás pausas)."""
    estado, _ = estado_actual(usuario, momento)
    motivo, nota = str(motivo or ''), str(nota or '')
    if tipo not in SIGUIENTES[estado]:
        textos = {'FUERA': 'No has marcado entrada hoy.', 'TRABAJANDO': 'Ya marcaste entrada.', 'EN_PAUSA': 'Estás en pausa: marca tu regreso.'}
        return None, textos[estado]
    almuerzo = bool(almuerzo) and tipo == Marcaje.PAUSA
    if almuerzo and not motivo:
        motivo = 'Almuerzo'
    return Marcaje.objects.create(usuario=usuario, tipo=tipo, origen=origen, ip=ip, motivo_pausa=motivo[:60], es_almuerzo=almuerzo,
                                  nota=nota[:255], momento=momento or timezone.now(), **(lugar or {})), None


def inicio_control(usuario):
    """Primer día en que la persona marcó: antes de eso no se le cuentan ausencias (no usaba el control de horario)."""
    primero = Marcaje.objects.filter(usuario=usuario).order_by('momento').values_list('momento', flat=True).first()
    return timezone.localtime(primero).date() if primero else None


def jornada(usuario, dia, ahora=None, horario=None, obligatoria=None, marcajes=None, ausencias=None, feriados=None, desde_control=False):
    """Resumen de un día. Los parámetros opcionales evitan consultas cuando se calcula un mes entero.
    `desde_control`: fecha desde la que la persona usa el control de horario (None = nunca ha marcado)."""
    ahora = ahora or timezone.now()
    hoy = timezone.localtime(ahora).date()
    if horario is None and obligatoria is None:
        horario, obligatoria = horario_de(usuario)
    if marcajes is None:
        marcajes = list(Marcaje.objects.filter(usuario=usuario, momento__range=rango(dia)).order_by('momento'))
    if feriados is None:
        feriados = set(Feriado.objects.filter(fecha=dia).values_list('fecha', flat=True))
    if ausencias is None:
        ausencias = list(Ausencia.objects.filter(usuario=usuario, estado='APROBADA', desde__lte=dia, hasta__gte=dia))
    ausencia = next((a for a in ausencias if a.cubre(dia)), None)
    turno = horario.turno(dia.weekday()) if horario else None
    laborable = bool(turno) and dia not in feriados
    programados = horario.minutos_programados(dia.weekday()) if laborable else 0
    tolerancia = horario.tolerancia_minutos if horario else 10

    fila = {
        'fecha': dia.isoformat(), 'laborable': laborable, 'feriado': dia in feriados,
        'turno': list(turno) if laborable else None, 'programados': programados,
        'entrada': None, 'salida': None, 'trabajados': 0, 'pausa': 0, 'tardanza': 0, 'salida_temprana': 0,
        'extra': 0, 'segundos_en_curso': 0,
        # Lo mismo en segundos exactos: de ahí sale el pago, los minutos son solo para mostrar
        'programados_seg': programados * 60, 'trabajados_seg': 0, 'pausa_seg': 0, 'almuerzo_seg': 0, 'pausas_seg': 0, 'pausas': [], 'excesos': 0, 'exceso_seg': 0,
        'almuerzo_programado': (horario.almuerzo_inicio or None) if horario else None, 'pausa_max_minutos': horario.pausa_max_minutos if horario else 60, 'tardanza_seg': 0, 'salida_temprana_seg': 0, 'extra_seg': 0, 'sin_salida': False, 'estado': 'LIBRE', 'llegada': None, 'pausa_max_minutos': horario.pausa_max_minutos if horario else 60, 'tardanza_seg': 0, 'salida_temprana_seg': 0, 'extra_seg': 0, 'sin_salida': False, 'estado': 'LIBRE', 'llegada': None,
        'ausencia': ausencia.get_tipo_display() if ausencia else None,
        'marcajes': [{'id': m.id, 'tipo': m.tipo, 'momento': m.momento.isoformat(), 'origen': m.origen,
                      'motivo': m.motivo_pausa, 'almuerzo': m.es_almuerzo, 'corregido': bool(m.corregido_por_id)} for m in marcajes],
    }
    if desde_control is False:
        desde_control = inicio_control(usuario)
    if not marcajes:
        if ausencia:
            fila['estado'] = 'PERMISO'
        elif laborable and (desde_control is None or dia < desde_control):
            fila['estado'] = 'SIN_CONTROL'  # aún no usa el control de horario: ni tarde ni ausente
        elif laborable and obligatoria:
            fin_turno = _aware(dia, _hora(turno[1]))
            if dia < hoy or (dia == hoy and ahora > fin_turno):
                fila['estado'] = 'AUSENTE'
            elif dia == hoy:
                fila['estado'] = 'TARDE_SIN_MARCAR' if ahora > _aware(dia, _hora(turno[0])) + timedelta(minutes=tolerancia) else 'PENDIENTE'
            else:
                fila['estado'] = 'PROGRAMADO'
        return fila

    trabajados = pausa = fuera = 0.0  # segundos; «fuera»: entre una salida y la siguiente entrada del día (p. ej. cerró la plataforma al almorzar)
    inicio = inicio_pausa = salio = None
    es_almuerzo = False
    tramos = []  # (inicio, fin o None si sigue abierta, es almuerzo)
    for m in marcajes:
        if m.tipo in (Marcaje.ENTRADA, Marcaje.REGRESO):
            if m.tipo == Marcaje.ENTRADA and salio and not inicio:
                fuera += _segundos(m.momento - salio)
            salio = None
            if inicio_pausa:
                pausa += _segundos(m.momento - inicio_pausa)
                tramos.append((inicio_pausa, m.momento, es_almuerzo))
                inicio_pausa = None
            inicio = inicio or m.momento
        elif m.tipo in (Marcaje.PAUSA, Marcaje.SALIDA) and inicio:
            trabajados += _segundos(m.momento - inicio)
            inicio = None
            if m.tipo == Marcaje.SALIDA:
                salio = m.momento
            if m.tipo == Marcaje.PAUSA:
                inicio_pausa, es_almuerzo = m.momento, m.es_almuerzo
    if inicio:  # sigue abierta al terminar el día
        siguiente = Marcaje.objects.filter(usuario=usuario, momento__gt=inicio, momento__lte=inicio + TURNO_MAXIMO,
                                           tipo__in=(Marcaje.PAUSA, Marcaje.SALIDA)).order_by('momento').first()
        if siguiente and siguiente.momento <= ahora:
            trabajados += _segundos(siguiente.momento - inicio)  # turno que cruza la medianoche
            inicio = None
        elif ahora - inicio < TURNO_MAXIMO:
            trabajados += _segundos(ahora - inicio)  # en curso
            fila['segundos_en_curso'] = int(_segundos(ahora - inicio)) % 60  # (compatibilidad) segundos del minuto en curso
        else:
            cierre = _aware(dia, _hora(turno[1])) if turno else inicio
            trabajados += _segundos(max(cierre, inicio) - inicio)
            fila['sin_salida'] = True
            inicio = None
    if inicio_pausa:
        if ahora - inicio_pausa < TURNO_MAXIMO and not any(m.momento > inicio_pausa for m in marcajes):
            pausa += _segundos(ahora - inicio_pausa)
            tramos.append((inicio_pausa, None, es_almuerzo))
        else:
            fila['sin_salida'] = True  # se fue a pausa y no volvió a marcar
    almuerzo = horario.almuerzo_minutos if horario else 0
    limite_pausa = (horario.pausa_max_minutos if horario else 60) * 60
    limite_almuerzo = almuerzo * 60
    for t_ini, t_fin, t_alm in tramos:
        dur = _segundos((t_fin or ahora) - t_ini)
        limite = limite_almuerzo if t_alm else limite_pausa
        excedida = bool(limite) and dur > limite
        fila['pausas'].append({'inicio': t_ini.isoformat(), 'fin': t_fin.isoformat() if t_fin else None, 'almuerzo': t_alm,
                               'segundos': _enteros(dur), 'excedida': excedida, 'exceso_seg': _enteros(dur - limite) if excedida else 0})
        fila['almuerzo_seg' if t_alm else 'pausas_seg'] += _enteros(dur)
        if excedida:
            fila['excesos'] += 1
            fila['exceso_seg'] += _enteros(dur - limite)
    # Almuerzo no marcado: se descuenta lo que falte; el tiempo fuera entre dos tramos del día ya cuenta como descanso
    if trabajados > DIA_LARGO * 60 and pausa + fuera < almuerzo * 60:
        trabajados -= almuerzo * 60 - pausa - fuera

    primera = next((m for m in marcajes if m.tipo == Marcaje.ENTRADA), None)
    ultima_salida = next((m for m in reversed(marcajes) if m.tipo == Marcaje.SALIDA), None)
    primer_almuerzo = next((m for m in marcajes if m.tipo == Marcaje.PAUSA and m.es_almuerzo), None)
    fila['almuerzo_inicio'] = timezone.localtime(primer_almuerzo.momento).strftime('%H:%M') if primer_almuerzo else None
    fila.update(trabajados=_min(trabajados), pausa=_min(pausa), trabajados_seg=_enteros(trabajados), pausa_seg=_enteros(pausa),
                entrada=primera.momento.isoformat() if primera else None,
                salida=ultima_salida.momento.isoformat() if ultima_salida else None)
    if laborable and primera:
        tarde = _segundos(primera.momento - _aware(dia, _hora(turno[0])))
        if tarde > tolerancia * 60:  # pasada la tolerancia, cuenta desde la hora de entrada, al segundo
            fila['tardanza'], fila['tardanza_seg'] = _min(tarde), _enteros(tarde)
        fila['llegada'] = 'TARDE' if fila['tardanza_seg'] else 'A_TIEMPO'
        if ultima_salida and not inicio:
            temprano = _segundos(_aware(dia, _hora(turno[1])) - ultima_salida.momento)
            if temprano > tolerancia * 60:
                fila['salida_temprana'], fila['salida_temprana_seg'] = _min(temprano), _enteros(temprano)
    extra = trabajados - programados * 60
    if extra >= EXTRA_MINIMO * 60:
        fila['extra'], fila['extra_seg'] = _min(extra), _enteros(extra)
    if inicio:
        fila['estado'] = 'TRABAJANDO'
    elif inicio_pausa and not fila['sin_salida']:
        fila['estado'] = 'EN_PAUSA'
    else:
        fila['estado'] = 'PRESENTE' if laborable else 'FUERA_DE_HORARIO'
    return fila


def dias_entre(desde, hasta):
    d = desde
    while d <= hasta:
        yield d
        d += timedelta(days=1)


def jornadas(usuario, desde, hasta, ahora=None):
    """Lista de jornadas del rango con todo precargado (tres consultas por persona)."""
    horario, obligatoria = horario_de(usuario)
    todos = list(Marcaje.objects.filter(usuario=usuario, momento__range=rango(desde, hasta)).order_by('momento'))
    por_dia = {}
    for m in todos:
        por_dia.setdefault(timezone.localtime(m.momento).date(), []).append(m)
    ausencias = list(Ausencia.objects.filter(usuario=usuario, estado='APROBADA', desde__lte=hasta, hasta__gte=desde))
    feriados = set(Feriado.objects.filter(fecha__range=(desde, hasta)).values_list('fecha', flat=True))
    hoy = timezone.localdate()
    control = inicio_control(usuario)
    return [jornada(usuario, d, ahora, horario, obligatoria, por_dia.get(d, []), ausencias, feriados, control)
            for d in dias_entre(desde, min(hasta, hoy))]


def jornadas_del_dia(usuarios, dia, ahora=None):
    """La jornada de `dia` de muchas personas a la vez: {id: jornada}. Seis consultas en total (no seis por persona)."""
    from collections import defaultdict
    from django.db.models import Min
    ids = [u.pk for u in usuarios]
    asignados = {a.usuario_id: a for a in AsignacionHorario.objects.filter(usuario_id__in=ids).select_related('horario')}
    por_defecto = Horario.objects.filter(por_defecto=True, activo=True).first()
    por_depto = horarios_por_departamento()
    marcajes = defaultdict(list)
    for m in Marcaje.objects.filter(usuario_id__in=ids, momento__range=rango(dia)).order_by('momento'):
        marcajes[m.usuario_id].append(m)
    ausencias = defaultdict(list)
    for a in Ausencia.objects.filter(usuario_id__in=ids, estado='APROBADA', desde__lte=dia, hasta__gte=dia):
        ausencias[a.usuario_id].append(a)
    feriados = set(Feriado.objects.filter(fecha=dia).values_list('fecha', flat=True))
    primeros = dict(Marcaje.objects.filter(usuario_id__in=ids).values('usuario_id').annotate(m=Min('momento')).values_list('usuario_id', 'm'))
    salida = {}
    for u in usuarios:
        asignacion = asignados.get(u.pk)
        horario, obligatoria = (asignacion.horario, asignacion.marca_obligatoria) if asignacion else (por_depto.get(_departamento_id(u)) or por_defecto, True)
        control = timezone.localtime(primeros[u.pk]).date() if u.pk in primeros else None
        salida[u.pk] = jornada(u, dia, ahora, horario, obligatoria, marcajes.get(u.pk, []), ausencias.get(u.pk, []), feriados, control)
    return salida


def resumen(usuario, desde, hasta, ahora=None):
    """Indicadores de asistencia del período (para la ficha, el reporte y los KPIs automáticos)."""
    dias = jornadas(usuario, desde, hasta, ahora)
    laborables = [d for d in dias if d['laborable'] and d['estado'] not in ('PROGRAMADO', 'PENDIENTE', 'TARDE_SIN_MARCAR', 'SIN_CONTROL')]
    con_permiso = [d for d in laborables if d['estado'] == 'PERMISO']
    presentes = [d for d in dias if d['entrada']]
    presentes_laborables = [d for d in laborables if d['entrada']]
    a_tiempo = [d for d in presentes_laborables if d['llegada'] == 'A_TIEMPO']
    ausentes = [d for d in laborables if d['estado'] == 'AUSENTE']
    esperados = len(laborables) - len(con_permiso)
    programados = sum(d['programados'] for d in laborables if d['estado'] != 'PERMISO')
    trabajados_seg = sum(d['trabajados_seg'] for d in dias)  # se suma en segundos y se convierte una sola vez
    tarde_seg, salida_seg = sum(d['tardanza_seg'] for d in dias), sum(d['salida_temprana_seg'] for d in dias)
    extra_seg, pausa_seg = sum(d['extra_seg'] for d in dias), sum(d['pausa_seg'] for d in dias)
    almuerzo_seg, pausas_seg = sum(d['almuerzo_seg'] for d in dias), sum(d['pausas_seg'] for d in dias)
    return {
        'dias_laborables': len(laborables), 'dias_presentes': len(presentes), 'dias_a_tiempo': len(a_tiempo),
        'tardanzas': len(presentes_laborables) - len(a_tiempo), 'minutos_tarde': tarde_seg // 60, 'segundos_tarde': tarde_seg,
        'ausencias': len(ausentes), 'permisos': len(con_permiso),
        'salidas_tempranas': sum(1 for d in dias if d['salida_temprana']), 'minutos_salida_temprana': salida_seg // 60, 'segundos_salida_temprana': salida_seg,
        'sin_salida': sum(1 for d in dias if d['sin_salida']),
        'minutos_programados': programados, 'minutos_trabajados': trabajados_seg // 60, 'segundos_trabajados': trabajados_seg,
        'minutos_extra': extra_seg // 60, 'segundos_extra': extra_seg,
        'minutos_pausa': pausa_seg // 60, 'segundos_pausa': pausa_seg,
        'segundos_almuerzo': almuerzo_seg, 'segundos_pausas': pausas_seg,
        'pausas_excedidas': sum(d['excesos'] for d in dias), 'segundos_exceso_pausa': sum(d['exceso_seg'] for d in dias),
        'puntualidad': round(len(a_tiempo) / len(presentes_laborables) * 100, 1) if presentes_laborables else None,
        'asistencia': round(len(presentes_laborables) / esperados * 100, 1) if esperados > 0 else None,
        'cumplimiento_horas': round(min(trabajados_seg / (programados * 60), 1.5) * 100, 1) if programados else None,
    }


def adherencia(res):
    """Un número 0-100 que resume el horario: promedio de puntualidad, asistencia y horas cumplidas (tope 100)."""
    partes = [v for v in (res['puntualidad'], res['asistencia'], min(res['cumplimiento_horas'], 100) if res['cumplimiento_horas'] is not None else None)
              if v is not None]
    return round(sum(partes) / len(partes), 1) if partes else None


def usuarios_con_horario():
    return User.objects.filter(is_active=True).select_related('perfil__puesto_trabajo__departamento')


def mes(periodo):
    """(primer día, último día) del mes de `periodo` (una fecha cualquiera del mes)."""
    inicio = periodo.replace(day=1)
    fin = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return inicio, fin


def revisar_pausas(ahora=None):
    """Avisa de las pausas (y almuerzos) abiertas que pasaron de su límite, una sola vez por pausa. Devuelve cuántas avisó.
    Se llama a cada minuto desde las pantallas abiertas (al pedir las notificaciones): no hace falta un programa aparte."""
    from apps.desempeno.permisos import revisores_de
    from apps.desempeno.servicios import avisar, nombre
    ahora = ahora or timezone.now()
    avisadas = 0
    abiertas = Marcaje.objects.filter(tipo=Marcaje.PAUSA, alerta_enviada=False, momento__gt=ahora - TURNO_MAXIMO, momento__lte=ahora
                                      ).select_related('usuario')
    for m in abiertas:
        if Marcaje.objects.filter(usuario=m.usuario, momento__gt=m.momento).exists():
            continue  # ya volvió (o salió): el contador se detuvo
        horario, _ = horario_de(m.usuario)
        limite = (horario.almuerzo_minutos if m.es_almuerzo else (horario.pausa_max_minutos if horario else 60)) if horario else 60
        if not limite or ahora - m.momento < timedelta(minutes=limite):
            continue
        if not Marcaje.objects.filter(pk=m.pk, alerta_enviada=False).update(alerta_enviada=True):
            continue  # otro proceso ya la avisó
        seg = int((ahora - m.momento).total_seconds())
        tiempo = f'{seg // 3600}:{seg % 3600 // 60:02d}:{seg % 60:02d}'
        cosa = 'el almuerzo' if m.es_almuerzo else 'una pausa'
        titulo = f'{nombre(m.usuario)} lleva {tiempo} en {"almuerzo" if m.es_almuerzo else "pausa"}'
        detalle = f'Empezó {cosa} a las {timezone.localtime(m.momento):%H:%M} y no ha registrado el regreso (límite: {limite} min).'
        avisar(revisores_de(m.usuario, 'asistencia.ver'), 'ASISTENCIA', titulo, detalle, enlace='/asistencia')
        if m.es_almuerzo:
            # Alerta emergente con sonido (insiste hasta que la persona la atiende): el regreso era a la hora que salió + su almuerzo
            debia = timezone.localtime(m.momento + timedelta(minutes=limite))
            avisar([m.usuario], 'ALMUERZO_EXCESO', 'Se acabó tu tiempo de almuerzo',
                   f'Saliste a las {timezone.localtime(m.momento):%H:%M} y tu almuerzo es de {limite} min: debías regresar a las {debia:%H:%M}. '
                   f'Llevas {tiempo}. Marca tu regreso ahora.')
        else:
            avisar([m.usuario], 'ASISTENCIA', f'Llevas {tiempo} en pausa', 'Marca tu regreso en cuanto vuelvas.', enlace='/')
        avisadas += 1
    return avisadas


AVISO_ANTES_ALMUERZO = timedelta(minutes=5)   # «te quedan 5 minutos»
VENTANA_HORA_ALMUERZO = timedelta(hours=2)    # pasado este tiempo desde la hora del almuerzo ya no se avisa que «es la hora»


def revisar_almuerzos(ahora=None):
    """Avisos de almuerzo para quien está en jornada (cada uno una sola vez):
    1) «Es tu hora de almuerzo»: llegó la hora del horario (`almuerzo_inicio`) y todavía no salió a comer hoy.
    2) «Te quedan 5 minutos»: ya está en almuerzo y falta poco para que se cumpla su tiempo, contado desde que salió.
    (Pasarse del tiempo lo avisa `revisar_pausas`.) Devuelve cuántos avisos creó."""
    from apps.desempeno.servicios import avisar
    ahora = ahora or timezone.now()
    local = timezone.localtime(ahora)
    hoy = local.date()
    candidatos = Marcaje.objects.filter(momento__gt=ahora - TURNO_MAXIMO, momento__lte=ahora).values_list('usuario_id', flat=True).distinct()
    enviados = 0
    for u in User.objects.filter(is_active=True, pk__in=list(candidatos)):
        estado, ultimo = estado_actual(u, ahora)
        horario, _ = horario_de(u)
        if not horario or estado == 'FUERA':
            continue
        if estado == 'EN_PAUSA' and ultimo.es_almuerzo:
            restante = timedelta(minutes=horario.almuerzo_minutos) - (ahora - ultimo.momento)
            if horario.almuerzo_minutos > 5 and timedelta(0) < restante <= AVISO_ANTES_ALMUERZO and _una_vez(u, f'almuerzo-fin-{ultimo.pk}', 'ALMUERZO_FIN'):
                vuelve = timezone.localtime(ultimo.momento + timedelta(minutes=horario.almuerzo_minutos))
                avisar([u], 'ALMUERZO_FIN', f'Te quedan {max(1, int(restante.total_seconds() // 60 + 0.99))} minutos de almuerzo',
                       f'Saliste a las {timezone.localtime(ultimo.momento):%H:%M}: debes estar de vuelta a las {vuelve:%H:%M}. Marca tu regreso al llegar.')
                enviados += 1
        elif estado == 'TRABAJANDO' and almuerzo_inicio_de(u, horario):
            hora_almuerzo = almuerzo_inicio_de(u, horario)
            try:
                inicio = _aware(hoy, _hora(hora_almuerzo))
            except (ValueError, TypeError):
                continue
            if not (inicio <= ahora < inicio + VENTANA_HORA_ALMUERZO):
                continue
            desde, hasta = rango(hoy)
            if Marcaje.objects.filter(usuario=u, es_almuerzo=True, momento__gte=min(desde, ahora - TURNO_MAXIMO), momento__lte=ahora).exists():
                continue  # ya salió a almorzar hoy
            if _una_vez(u, f'almuerzo-hora-{hoy:%Y%m%d}-{hora_almuerzo.replace(":", "")}', 'ALMUERZO_HORA'):
                avisar([u], 'ALMUERZO_HORA', 'Es tu hora de almuerzo',
                       f'Tu almuerzo es a las {hora_almuerzo} y dura {horario.almuerzo_minutos} min. Marca «Almuerzo» al salir: '
                       f'te avisamos cuando falten 5 minutos y cuando se cumpla tu tiempo.')
                enviados += 1
    return enviados


def _una_vez(usuario, clave, tipo, detalle=''):
    from apps.core.models import AlertaEnviada
    _, nueva = AlertaEnviada.objects.get_or_create(usuario=usuario, clave=clave[:80], defaults={'tipo': tipo, 'detalle': detalle[:255]})
    return nueva


def revisar_asistencia(ahora=None):
    """Avisa a los supervisores de las tardanzas y de quien no ha marcado entrada, y de las pausas largas.
    Pensado para correr cada 10 minutos en horario laboral (`python manage.py revisar_jornadas`)."""
    from apps.desempeno.permisos import revisores_de
    from apps.desempeno.servicios import avisar
    ahora = ahora or timezone.now()
    hoy = timezone.localtime(ahora).date()
    enviados = revisar_pausas(ahora) + revisar_almuerzos(ahora)
    # Solo a quien ya usa el control de horario o tiene horario asignado
    usan = set(Marcaje.objects.values_list('usuario_id', flat=True).distinct()) | set(
        AsignacionHorario.objects.filter(marca_obligatoria=True).values_list('usuario_id', flat=True))
    for u in User.objects.filter(is_active=True, pk__in=usan):
        j = jornada(u, hoy, ahora)
        nombre = u.get_full_name() or u.username
        if j['llegada'] == 'TARDE' and j['tardanza'] >= 15 and _una_vez(u, f'tarde-{hoy:%Y%m%d}', 'TARDE', f"{j['tardanza']} min"):
            avisar(revisores_de(u, 'asistencia.ver'), 'ASISTENCIA', f"{nombre} llegó {j['tardanza']} minutos tarde", enlace='/asistencia')
            enviados += 1
        if j['estado'] == 'TARDE_SIN_MARCAR' and _una_vez(u, f'sinmarcar-{hoy:%Y%m%d}', 'SIN_MARCAR'):
            avisar([u], 'ASISTENCIA', 'No has marcado tu entrada', 'Márcala en Adzone Team en cuanto llegues.', enlace='/')
            avisar(revisores_de(u, 'asistencia.ver'), 'ASISTENCIA', f'{nombre} no ha marcado entrada', f"Entraba a las {j['turno'][0]}.", enlace='/asistencia')
            enviados += 1
    return enviados


# ------------------------------------------------------------------ Jornada automática
# Al abrir la plataforma la jornada empieza sola; al cerrarla (sin señal de ningún dispositivo durante CIERRE_SIN_SENAL) termina sola,
# a la hora de la última señal, y se detiene el cronómetro de la tarea. Si vuelve a abrirla ese día, empieza otro tramo.
CIERRE_SIN_SENAL = timedelta(minutes=5)
VENTANA_ANTES, VENTANA_DESPUES = timedelta(hours=2), timedelta(hours=3)   # entrada automática: de 2 h antes del turno a 3 h después
NOTA_CIERRE_AUTO = 'Cierre automático: la plataforma se cerró'


def registrar_senal(usuario, ahora=None):
    from .models import PresenciaPlataforma
    PresenciaPlataforma.objects.update_or_create(usuario=usuario, defaults={'ultima_senal': ahora or timezone.now()})


def entrada_automatica(usuario, ahora=None, hoy=None, obligatoria=None):
    """¿Debe empezar sola la jornada al abrir la plataforma? Solo a quien marca obligatoriamente, en día laborable, sin permiso aprobado,
    cerca de su turno, y si hoy no ha marcado o su última salida fue automática (vuelve a abrirla: otro tramo)."""
    ahora = ahora or timezone.now()
    estado, ultimo = estado_actual(usuario, ahora)
    if estado != 'FUERA':
        return False
    if obligatoria is None:
        obligatoria = horario_de(usuario)[1]
    hoy = hoy or jornada(usuario, timezone.localtime(ahora).date(), ahora)
    if not (obligatoria and hoy.get('laborable') and hoy.get('turno')) or hoy.get('ausencia'):
        return False
    dia = timezone.localtime(ahora).date()
    if not (_aware(dia, _hora(hoy['turno'][0])) - VENTANA_ANTES <= ahora <= _aware(dia, _hora(hoy['turno'][1])) + VENTANA_DESPUES):
        return False
    if ultimo is None or timezone.localtime(ultimo.momento).date() != dia:
        return True
    return ultimo.tipo == Marcaje.SALIDA and ultimo.origen == 'AUTO'


def cerrar_jornadas_sin_senal(ahora=None):
    """Cierra las jornadas de quienes cerraron la plataforma: la salida queda a la hora de la última señal.
    Solo si la plataforma estuvo abierta durante ese tramo (quien marcó por QR y no la usa no se ve afectado)."""
    from apps.tiempo import servicios as cronometro
    from .models import PresenciaPlataforma
    ahora = ahora or timezone.now()
    cerradas = 0
    for p in PresenciaPlataforma.objects.filter(ultima_senal__lt=ahora - CIERRE_SIN_SENAL, ultima_senal__gt=ahora - TURNO_MAXIMO).select_related('usuario'):
        estado, ultimo = estado_actual(p.usuario, ahora)
        if estado == 'FUERA':
            continue
        apertura = Marcaje.objects.filter(usuario=p.usuario, tipo=Marcaje.ENTRADA, momento__lte=ahora).order_by('-momento').values_list('momento', flat=True).first()
        if apertura is None or p.ultima_senal < apertura:
            continue   # no tuvo la plataforma abierta en este tramo
        momento = max(p.ultima_senal, ultimo.momento)
        marcaje, error = marcar(p.usuario, Marcaje.SALIDA, 'AUTO', nota=NOTA_CIERRE_AUTO, momento=momento)
        if error:
            continue
        registro = cronometro.activo(p.usuario)
        if registro:
            cronometro.detener(registro, fin=max(momento, registro.inicio))
        cerradas += 1
    return cerradas
