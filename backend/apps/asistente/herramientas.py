"""Herramientas de consulta del asistente. Son la ÚNICA vía por la que la IA ve datos:

- Solo lectura.
- Cada una aplica los permisos de quien pregunta (los mismos de la plataforma): un colaborador ve lo suyo; un supervisor,
  su equipo; Dirección, todo. Finanzas, comercial y órdenes, solo con su permiso. Lo que no puede ver no existe para la IA.
- Devuelven datos agregados y listas cortas (no volcados completos), en JSON.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone

MAX_DIAS = 366
MAX_LISTA = 30


# ------------------------------------------------------------------ alcance de quien pregunta
class Alcance:
    def __init__(self, user):
        from apps.comercial.permisos import es_comercial, filtro_solicitudes
        from apps.core.permisos import tiene
        from apps.desempeno.permisos import equipo_gestionable, es_administrador
        from apps.operaciones.permisos import es_finanzas, filtro_ordenes
        self.user = user
        self.direccion = es_administrador(user)
        # Personas cuyo trabajo ve (tareas, puntaje) y cuya asistencia ve. Siempre incluye a la persona misma.
        self.ids_trabajo = set(equipo_gestionable(user, 'equipo.ver').values_list('id', flat=True)) | {user.pk}
        self.ids_asistencia = set(equipo_gestionable(user, 'asistencia.ver').values_list('id', flat=True)) | {user.pk}
        self.finanzas = es_finanzas(user)
        self.comercial = es_comercial(user)
        self.filtro_solicitudes = filtro_solicitudes(user)
        self.filtro_ordenes = filtro_ordenes(user)
        self.ve_compensacion = self.direccion or tiene(user, 'personal.salarios')

    def personas(self, ids, departamento=None, persona_id=None):
        qs = User.objects.filter(id__in=ids, is_active=True).select_related('perfil__puesto_trabajo__departamento')
        if persona_id:
            qs = qs.filter(id=persona_id)
        if departamento:
            qs = qs.filter(perfil__puesto_trabajo__departamento__nombre__iexact=departamento.strip())
        return list(qs)

    def describir(self):
        partes = ['tus propios datos']
        if len(self.ids_trabajo) > 1:
            partes.append(f'el trabajo de {len(self.ids_trabajo) - 1} persona(s) de tu equipo' if not self.direccion else 'toda la empresa (Dirección)')
        if self.finanzas:
            partes.append('finanzas')
        if self.comercial:
            partes.append('oportunidades comerciales')
        return ', '.join(partes)


def _nombre(u):
    return u.get_full_name() or u.username if u else None


def _depto(u):
    p = getattr(getattr(u, 'perfil', None), 'puesto_trabajo', None)
    return p.departamento.nombre if p and p.departamento_id else None


def _fechas(desde, hasta, defecto_dias=30):
    hoy = timezone.localdate()
    try:
        h = date.fromisoformat(hasta) if hasta else hoy
        d = date.fromisoformat(desde) if desde else h - timedelta(days=defecto_dias)
    except ValueError:
        raise ValueError('Las fechas van en formato AAAA-MM-DD.')
    if d > h:
        d, h = h, d
    if (h - d).days > MAX_DIAS:
        d = h - timedelta(days=MAX_DIAS)
    return d, h


def _num(v):
    if isinstance(v, Decimal):
        return float(round(v, 2))
    return v


# ------------------------------------------------------------------ herramientas
def personas(alcance, departamento=None):
    gente = alcance.personas(alcance.ids_trabajo, departamento)
    return {'total': len(gente), 'personas': [
        {'id': u.id, 'nombre': _nombre(u), 'puesto': getattr(getattr(u.perfil, 'puesto_trabajo', None), 'nombre', None), 'departamento': _depto(u)}
        for u in sorted(gente, key=lambda x: _nombre(x))[:200]]}


def tareas_resumen(alcance, desde=None, hasta=None, persona_id=None, departamento=None, agrupar_por='persona'):
    from apps.desempeno.models import Tarea
    d, h = _fechas(desde, hasta)
    gente = {u.id: u for u in alcance.personas(alcance.ids_trabajo, departamento, persona_id)}
    hoy = timezone.localdate()
    qs = Tarea.objects.filter(colaborador_id__in=gente, fecha_limite__range=(d, h)).exclude(estado='CANCELADA')
    filas = defaultdict(Counter)
    calidad = defaultdict(list)
    for t in qs.only('estado', 'fecha_limite', 'fecha_completada', 'colaborador_id', 'calificacion_calidad'):
        u = gente[t.colaborador_id]
        clave = {'persona': _nombre(u), 'departamento': _depto(u) or 'Sin departamento', 'estado': t.get_estado_display()}.get(agrupar_por, _nombre(u))
        c = filas[clave]
        c['total'] += 1
        c[t.estado.lower()] += 1
        if t.estado == 'COMPLETADA':
            c['validadas_a_tiempo' if t.fecha_completada and t.fecha_completada <= t.fecha_limite else 'validadas_tarde'] += 1
            if t.calificacion_calidad:
                calidad[clave].append(t.calificacion_calidad)
        elif t.fecha_limite < hoy:
            c['vencidas_sin_validar'] += 1
    salida = []
    for clave, c in filas.items():
        fila = {'grupo': clave, **dict(c)}
        if calidad[clave]:
            fila['calidad_promedio_1a5'] = round(sum(calidad[clave]) / len(calidad[clave]), 2)
        salida.append(fila)
    salida.sort(key=lambda f: -f['total'])
    return {'desde': d.isoformat(), 'hasta': h.isoformat(), 'agrupado_por': agrupar_por, 'personas_incluidas': len(gente),
            'nota': 'Por fecha límite dentro del rango. «completada» = validada.', 'filas': salida[:100]}


def tareas_lista(alcance, filtro='vencidas', persona_id=None, departamento=None, limite=MAX_LISTA):
    from apps.desempeno.models import Tarea
    gente = {u.id: u for u in alcance.personas(alcance.ids_trabajo, departamento, persona_id)}
    hoy = timezone.localdate()
    qs = Tarea.objects.filter(colaborador_id__in=gente).exclude(estado__in=('CANCELADA',))
    if filtro == 'vencidas':
        qs = qs.exclude(estado='COMPLETADA').filter(fecha_limite__lt=hoy)
    elif filtro == 'bloqueadas':
        qs = qs.filter(estado='BLOQUEADA')
    elif filtro == 'en_revision':
        qs = qs.filter(estado='EN_REVISION')
    elif filtro == 'proximas':
        qs = qs.exclude(estado='COMPLETADA').filter(fecha_limite__range=(hoy, hoy + timedelta(days=7)))
    else:
        raise ValueError('filtro debe ser vencidas, bloqueadas, en_revision o proximas.')
    total = qs.count()
    lista = [{'id': t.id, 'titulo': t.titulo[:120], 'persona': _nombre(gente[t.colaborador_id]), 'estado': t.get_estado_display(),
              'prioridad': t.prioridad, 'fecha_limite': t.fecha_limite.isoformat(),
              'dias_de_atraso': max(0, (hoy - t.fecha_limite).days)} for t in qs.order_by('fecha_limite')[:min(int(limite or MAX_LISTA), MAX_LISTA)]]
    return {'filtro': filtro, 'total': total, 'mostradas': len(lista), 'tareas': lista}


def desempeno_mes(alcance, mes=None, persona_id=None, departamento=None):
    from apps.desempeno.puntaje import calcular_ranking
    hoy = timezone.localdate()
    try:
        periodo = date.fromisoformat(f'{mes}-01') if mes else hoy.replace(day=1)
    except ValueError:
        raise ValueError('El mes va en formato AAAA-MM.')
    visibles = {u.id for u in alcance.personas(alcance.ids_trabajo, departamento, persona_id)}
    filas = []
    for f in calcular_ranking(periodo):
        if f['colaborador_id'] not in visibles:
            continue
        fila = {'nombre': f['nombre'], 'departamento': f['departamento'], 'puesto': f['puesto'], 'puntaje_total': f['puntaje_total'],
                'puntaje_tareas': f['puntaje_tareas'], 'puntaje_kpis': f['puntaje_kpis'], 'puntaje_jornada': f['puntaje_jornada'],
                'puntaje_calidad': f['puntaje_calidad'], 'tareas': f['tareas'],
                'kpis': [{'kpi': k.get('nombre'), 'cumplimiento_pct': k.get('cumplimiento'), 'meta': k.get('meta'), 'real': k.get('real')}
                         for k in f['kpis']][:10]}
        if alcance.ve_compensacion:
            fila['bono_sugerido'] = _num(f.get('bono_sugerido'))
        filas.append(fila)
    return {'mes': periodo.strftime('%Y-%m'), 'evaluados': len(filas),
            'nota': 'Puntajes de 0 a 100 (como en la plataforma). Sin tareas ni KPIs medidos en el mes, la persona no aparece.', 'filas': filas}


def asistencia(alcance, desde=None, hasta=None, persona_id=None, departamento=None):
    from apps.asistencia import servicios as asis
    d, h = _fechas(desde, hasta, defecto_dias=30)
    filas = []
    for u in alcance.personas(alcance.ids_asistencia, departamento, persona_id)[:120]:
        r = asis.resumen(u, d, h)
        filas.append({'nombre': _nombre(u), 'departamento': _depto(u), 'dias_laborables': r['dias_laborables'], 'dias_presentes': r['dias_presentes'],
                      'tardanzas': r['tardanzas'], 'tardanzas_justificadas': r.get('tardanzas_justificadas', 0), 'minutos_tarde': r['minutos_tarde'],
                      'ausencias': r['ausencias'], 'permisos': r['permisos'], 'dias_sin_marcar_salida': r['sin_salida'],
                      'horas_trabajadas': round(r['segundos_trabajados'] / 3600, 1), 'horas_programadas': round(r['minutos_programados'] / 60, 1),
                      'horas_extra': round(r['segundos_extra'] / 3600, 1), 'pausas_excedidas': r['pausas_excedidas'],
                      'puntualidad_pct': r['puntualidad'], 'asistencia_pct': r['asistencia']})
    return {'desde': d.isoformat(), 'hasta': h.isoformat(), 'personas': len(filas), 'filas': filas}


def ordenes(alcance, desde=None, hasta=None):
    from apps.operaciones.models import OrdenTrabajo
    d, h = _fechas(desde, hasta, defecto_dias=90)
    qs = OrdenTrabajo.objects.filter(fecha_creacion__date__range=(d, h)).select_related('cliente', 'departamento')
    if alcance.filtro_ordenes is not None:
        qs = qs.filter(alcance.filtro_ordenes)
    lista = list(qs)
    por_estado = Counter(o.get_estado_display() for o in lista)
    vencidas = [o for o in lista if o.vencida]
    entregadas = [o for o in lista if o.estado in ('ENTREGADA', 'CERRADA')]
    a_tiempo = [o for o in entregadas if o.a_tiempo]
    return {'desde': d.isoformat(), 'hasta': h.isoformat(), 'total': len(lista), 'por_estado': dict(por_estado),
            'abiertas': sum(o.estado in OrdenTrabajo.ABIERTAS for o in lista),
            'entregadas': len(entregadas), 'entregadas_a_tiempo_pct': round(len(a_tiempo) / len(entregadas) * 100, 1) if entregadas else None,
            'por_departamento': dict(Counter((o.departamento.nombre if o.departamento else 'Sin departamento') for o in lista)),
            'vencidas': [{'codigo': o.codigo, 'titulo': o.titulo[:100], 'cliente': o.cliente.nombre if o.cliente else None,
                          'compromiso': o.fecha_compromiso.isoformat() if o.fecha_compromiso else None, 'estado': o.get_estado_display()}
                         for o in sorted(vencidas, key=lambda x: x.fecha_compromiso)[:MAX_LISTA]]}


def comercial(alcance, desde=None, hasta=None):
    from apps.comercial.models import Oportunidad, SolicitudServicio
    d, h = _fechas(desde, hasta, defecto_dias=90)
    hoy = timezone.localdate()
    salida = {'desde': d.isoformat(), 'hasta': h.isoformat()}
    if alcance.comercial:
        ops = list(Oportunidad.objects.filter(fecha_creacion__date__range=(d, h)).select_related('cliente', 'responsable'))
        cerradas = [o for o in ops if o.estado in Oportunidad.CERRADOS]
        salida['oportunidades'] = {
            'total': len(ops), 'por_estado': dict(Counter(o.get_estado_display() for o in ops)),
            'tasa_de_cierre_pct': round(sum(o.estado == 'APROBADA' for o in cerradas) / len(cerradas) * 100, 1) if cerradas else None,
            'por_responsable': dict(Counter(_nombre(o.responsable) or 'Sin responsable' for o in ops)),
            'seguimiento_vencido': [{'codigo': o.codigo, 'cliente': o.nombre_cliente, 'titulo': o.titulo[:100], 'responsable': _nombre(o.responsable),
                                     'seguimiento': o.proximo_seguimiento.isoformat(), 'estado': o.get_estado_display()}
                                    for o in Oportunidad.objects.exclude(estado__in=Oportunidad.CERRADOS)
                                    .filter(proximo_seguimiento__lt=hoy).select_related('cliente', 'responsable')[:MAX_LISTA]],
        }
    sol = SolicitudServicio.objects.filter(fecha_creacion__date__range=(d, h)).select_related('departamento')
    if alcance.filtro_solicitudes is not None:
        sol = sol.filter(alcance.filtro_solicitudes)
    sol = list(sol)
    salida['solicitudes_de_servicio'] = {'total': len(sol), 'por_estado': dict(Counter(s.get_estado_display() for s in sol)),
                                         'por_departamento': dict(Counter(s.departamento.nombre for s in sol)),
                                         'por_servicio': dict(Counter(s.servicio_nombre for s in sol))}
    return salida


def finanzas(alcance, desde=None, hasta=None):
    if not alcance.finanzas:
        raise PermissionError('Sin permiso de Finanzas.')
    from apps.finanzas.models import Factura, Gasto
    d, h = _fechas(desde, hasta, defecto_dias=90)
    facturas = list(Factura.objects.filter(fecha__range=(d, h)).exclude(estado__in=('ANULADA', 'BORRADOR')).select_related('cliente'))
    pendientes = list(Factura.objects.filter(estado='EMITIDA').select_related('cliente'))
    gastos = list(Gasto.objects.filter(fecha__range=(d, h)))
    saldo_cliente = defaultdict(Decimal)
    for f in pendientes:
        saldo_cliente[f.cliente.nombre if f.cliente else 'Sin cliente'] += f.saldo
    return {'desde': d.isoformat(), 'hasta': h.isoformat(), 'moneda': 'Montos en la moneda de cada documento (mayormente RD$).',
            'facturado': _num(sum((f.total for f in facturas), Decimal(0))), 'cobrado_de_lo_facturado': _num(sum((f.pagado for f in facturas), Decimal(0))),
            'facturas': len(facturas),
            'saldo_por_cobrar_total': _num(sum((f.saldo for f in pendientes), Decimal(0))),
            'facturas_vencidas': sum(1 for f in pendientes if f.vencida),
            'saldo_vencido': _num(sum((f.saldo for f in pendientes if f.vencida), Decimal(0))),
            'mayores_saldos_por_cliente': [{'cliente': c, 'saldo': _num(s)} for c, s in sorted(saldo_cliente.items(), key=lambda x: -x[1])[:10]],
            'gastos': _num(sum((g.monto for g in gastos), Decimal(0))),
            'gastos_por_categoria': {k: _num(v) for k, v in _sumar(gastos, lambda g: g.get_categoria_display(), lambda g: g.monto).items()}}


def _sumar(items, clave, valor):
    r = defaultdict(Decimal)
    for i in items:
        r[clave(i)] += valor(i)
    return r


# ------------------------------------------------------------------ definiciones para la API
_FECHAS = {'desde': {'type': 'string', 'description': 'Fecha inicial AAAA-MM-DD (opcional).'},
           'hasta': {'type': 'string', 'description': 'Fecha final AAAA-MM-DD (opcional; por defecto hoy).'}}
_FILTRO_GENTE = {'persona_id': {'type': 'integer', 'description': 'Id de una persona (de la herramienta personas).'},
                 'departamento': {'type': 'string', 'description': 'Nombre exacto del departamento, p. ej. Marketing.'}}


def _def(nombre, descripcion, props, requeridos=()):
    return {'name': nombre, 'description': descripcion,
            'input_schema': {'type': 'object', 'properties': props, 'required': list(requeridos), 'additionalProperties': False}}


CATALOGO = {
    'personas': (personas, lambda a: True, _def('personas', 'Lista de personas cuyo trabajo puede ver quien pregunta (id, nombre, puesto, departamento). Úsala para obtener ids o saber quién está en un área.',
                                              {'departamento': _FILTRO_GENTE['departamento']})),
    'tareas_resumen': (tareas_resumen, lambda a: True, _def('tareas_resumen', 'Conteo de tareas por persona, departamento o estado en un rango (por fecha límite): total, validadas a tiempo/tarde, vencidas sin validar, bloqueadas, en revisión y calidad promedio.',
                                                          {**_FECHAS, **_FILTRO_GENTE, 'agrupar_por': {'type': 'string', 'enum': ['persona', 'departamento', 'estado']}})),
    'tareas_lista': (tareas_lista, lambda a: True, _def('tareas_lista', 'Lista concreta de tareas: vencidas, bloqueadas, en_revision (por validar) o proximas (vencen en 7 días). Máximo 30.',
                                                      {'filtro': {'type': 'string', 'enum': ['vencidas', 'bloqueadas', 'en_revision', 'proximas']}, **_FILTRO_GENTE,
                                                       'limite': {'type': 'integer'}}, ['filtro'])),
    'desempeno_mes': (desempeno_mes, lambda a: True, _def('desempeno_mes', 'Puntaje del mes por persona (total, tareas, KPIs, jornada, calidad) y cumplimiento de cada KPI.',
                                                        {'mes': {'type': 'string', 'description': 'AAAA-MM (por defecto el mes actual).'}, **_FILTRO_GENTE})),
    'asistencia': (asistencia, lambda a: True, _def('asistencia', 'Asistencia por persona en un rango: tardanzas (y cuántas justificadas), ausencias, permisos, horas trabajadas vs programadas, extra, puntualidad.',
                                                  {**_FECHAS, **_FILTRO_GENTE})),
    'ordenes': (ordenes, lambda a: True, _def('ordenes', 'Órdenes de trabajo creadas en un rango: por estado y departamento, % entregadas a tiempo y lista de vencidas.', _FECHAS)),
    'comercial': (comercial, lambda a: True,   # las oportunidades solo salen con permiso comercial; las solicitudes, filtradas
                  _def('comercial', 'Oportunidades comerciales (si quien pregunta es de Marketing/Dirección) y solicitudes de servicio por estado, departamento y servicio.', _FECHAS)),
    'finanzas': (finanzas, lambda a: a.finanzas, _def('finanzas', 'Facturado, cobrado, saldo por cobrar (y vencido), mayores saldos por cliente y gastos por categoría.', _FECHAS)),
}


def disponibles(alcance):
    """Definiciones para la API (orden fijo, para que el caché funcione) de las herramientas que esta persona puede usar."""
    return [defin for nombre, (_, permitido, defin) in CATALOGO.items() if permitido(alcance)]


def ejecutar(alcance, nombre, entrada):
    if nombre not in CATALOGO or not CATALOGO[nombre][1](alcance):
        raise PermissionError('Esa consulta no está disponible para ti.')
    funcion = CATALOGO[nombre][0]
    return funcion(alcance, **{k: v for k, v in (entrada or {}).items() if v not in (None, '')})
