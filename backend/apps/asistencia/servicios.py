"""
Cálculo de la jornada de cada día a partir de los marcajes.

Reglas:
- Se trabaja desde ENTRADA (o REGRESO) hasta PAUSA o SALIDA.
- Tardanza: minutos entre la hora de entrada del turno y la primera ENTRADA, si pasan la tolerancia.
- Salida temprana: minutos entre la última SALIDA y la hora de salida del turno, si pasan la tolerancia.
- Almuerzo: si la persona trabajó más de 6 horas y marcó menos pausa que el almuerzo del horario, se descuenta
  la diferencia (el almuerzo no cuenta como trabajado aunque se olvide marcarlo).
- Día pasado sin SALIDA: se cierra a la hora de salida del turno y el día queda marcado «sin salida».
- Extra: lo trabajado por encima de lo programado, desde 15 minutos.
"""
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from .models import AsignacionHorario, Ausencia, Feriado, Horario, Marcaje

EXTRA_MINIMO = 15
DIA_LARGO = 6 * 60
TURNO_MAXIMO = timedelta(hours=16)  # una jornada abierta más de esto se da por olvidada


def rango(desde, hasta=None):
    """(inicio, fin) con hora local de un día o de un rango de días, para filtrar sin __date (usa el índice)."""
    hasta = hasta or desde
    return timezone.make_aware(datetime.combine(desde, time.min)), timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min))


def horario_de(usuario):
    asignacion = AsignacionHorario.objects.filter(usuario=usuario).select_related('horario').first()
    if asignacion:
        return asignacion.horario, asignacion.marca_obligatoria
    return Horario.objects.filter(por_defecto=True, activo=True).first(), True


def _hora(texto):
    h, m = texto.split(':')
    return time(int(h), int(m))


def _aware(dia, hora):
    return timezone.make_aware(datetime.combine(dia, hora))


def _minutos(delta):
    return max(0, int(delta.total_seconds() // 60))


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


def marcar(usuario, tipo, origen='WEB', ip=None, motivo='', nota='', momento=None):
    """Registra un marcaje si tiene sentido según el estado actual. Devuelve (marcaje, error)."""
    estado, _ = estado_actual(usuario, momento)
    motivo, nota = str(motivo or ''), str(nota or '')
    if tipo not in SIGUIENTES[estado]:
        textos = {'FUERA': 'No has marcado entrada hoy.', 'TRABAJANDO': 'Ya marcaste entrada.', 'EN_PAUSA': 'Estás en pausa: marca tu regreso.'}
        return None, textos[estado]
    return Marcaje.objects.create(usuario=usuario, tipo=tipo, origen=origen, ip=ip, motivo_pausa=motivo[:60],
                                  nota=nota[:255], momento=momento or timezone.now()), None


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
        'extra': 0, 'sin_salida': False, 'estado': 'LIBRE', 'llegada': None,
        'ausencia': ausencia.get_tipo_display() if ausencia else None,
        'marcajes': [{'id': m.id, 'tipo': m.tipo, 'momento': m.momento.isoformat(), 'origen': m.origen,
                      'motivo': m.motivo_pausa, 'corregido': bool(m.corregido_por_id)} for m in marcajes],
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

    trabajados = pausa = 0
    inicio = inicio_pausa = None
    for m in marcajes:
        if m.tipo in (Marcaje.ENTRADA, Marcaje.REGRESO):
            if inicio_pausa:
                pausa += _minutos(m.momento - inicio_pausa)
                inicio_pausa = None
            inicio = inicio or m.momento
        elif m.tipo in (Marcaje.PAUSA, Marcaje.SALIDA) and inicio:
            trabajados += _minutos(m.momento - inicio)
            inicio = None
            if m.tipo == Marcaje.PAUSA:
                inicio_pausa = m.momento
    if inicio:  # sigue abierta al terminar el día
        siguiente = Marcaje.objects.filter(usuario=usuario, momento__gt=inicio, momento__lte=inicio + TURNO_MAXIMO,
                                           tipo__in=(Marcaje.PAUSA, Marcaje.SALIDA)).order_by('momento').first()
        if siguiente and siguiente.momento <= ahora:
            trabajados += _minutos(siguiente.momento - inicio)  # turno que cruza la medianoche
            inicio = None
        elif ahora - inicio < TURNO_MAXIMO:
            trabajados += _minutos(ahora - inicio)  # en curso
        else:
            cierre = _aware(dia, _hora(turno[1])) if turno else inicio
            trabajados += _minutos(max(cierre, inicio) - inicio)
            fila['sin_salida'] = True
            inicio = None
    if inicio_pausa:
        if ahora - inicio_pausa < TURNO_MAXIMO and not any(m.momento > inicio_pausa for m in marcajes):
            pausa += _minutos(ahora - inicio_pausa)
        else:
            fila['sin_salida'] = True  # se fue a pausa y no volvió a marcar
    almuerzo = horario.almuerzo_minutos if horario else 0
    if trabajados > DIA_LARGO and pausa < almuerzo:
        trabajados -= almuerzo - pausa

    primera = next((m for m in marcajes if m.tipo == Marcaje.ENTRADA), None)
    ultima_salida = next((m for m in reversed(marcajes) if m.tipo == Marcaje.SALIDA), None)
    fila.update(trabajados=trabajados, pausa=pausa,
                entrada=primera.momento.isoformat() if primera else None,
                salida=ultima_salida.momento.isoformat() if ultima_salida else None)
    if laborable and primera:
        tarde = _minutos(primera.momento - _aware(dia, _hora(turno[0])))
        fila['tardanza'] = tarde if tarde > tolerancia else 0
        fila['llegada'] = 'TARDE' if fila['tardanza'] else 'A_TIEMPO'
        if ultima_salida and not inicio:
            temprano = _minutos(_aware(dia, _hora(turno[1])) - ultima_salida.momento)
            fila['salida_temprana'] = temprano if temprano > tolerancia else 0
    extra = trabajados - programados
    fila['extra'] = extra if extra >= EXTRA_MINIMO else 0
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
    trabajados = sum(d['trabajados'] for d in dias)
    return {
        'dias_laborables': len(laborables), 'dias_presentes': len(presentes), 'dias_a_tiempo': len(a_tiempo),
        'tardanzas': len(presentes_laborables) - len(a_tiempo), 'minutos_tarde': sum(d['tardanza'] for d in dias),
        'ausencias': len(ausentes), 'permisos': len(con_permiso),
        'salidas_tempranas': sum(1 for d in dias if d['salida_temprana']), 'minutos_salida_temprana': sum(d['salida_temprana'] for d in dias),
        'sin_salida': sum(1 for d in dias if d['sin_salida']),
        'minutos_programados': programados, 'minutos_trabajados': trabajados, 'minutos_extra': sum(d['extra'] for d in dias),
        'minutos_pausa': sum(d['pausa'] for d in dias),
        'puntualidad': round(len(a_tiempo) / len(presentes_laborables) * 100, 1) if presentes_laborables else None,
        'asistencia': round(len(presentes_laborables) / esperados * 100, 1) if esperados > 0 else None,
        'cumplimiento_horas': round(min(trabajados / programados, 1.5) * 100, 1) if programados else None,
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
