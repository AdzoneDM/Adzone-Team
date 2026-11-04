"""
Inteligencia en el día a día:
- Resumen semanal para la Dirección: quién va bien, qué OT están en riesgo y dónde se pierde dinero.
- Sugerencia de a quién asignar una tarea, según carga, cumplimiento, calidad y tareas parecidas que ya hizo.
- Borrador de la evaluación del supervisor a partir de los datos de la persona.

Los números siempre se calculan aquí. La IA (si hay ANTHROPIC_API_KEY) solo redacta a partir de ellos; sin clave,
el texto se arma con reglas. A la API no se envían salarios, documentos ni la actividad en la computadora.
"""
import json
import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from apps.core import ia
from .models import ResumenSemanal, Tarea

ABIERTAS = ('PENDIENTE', 'EN_PROGRESO', 'EN_REVISION')


def _nombre(u):
    return (u.get_full_name() or u.username) if u else ''


def _f(x):
    return float(x) if isinstance(x, Decimal) else x


# ------------------------------------------------------------------ Resumen semanal
def datos_semana(hoy=None):
    from apps.operaciones.models import OrdenTrabajo
    from .puntaje import calcular_ranking
    hoy = hoy or timezone.localdate()
    lunes = hoy - timedelta(days=hoy.weekday())
    desde = lunes - timedelta(days=7)
    hasta = lunes - timedelta(days=1)

    tareas = Tarea.objects.exclude(estado='CANCELADA')
    semana = tareas.filter(fecha_limite__range=(desde, hasta))
    validadas = semana.filter(estado='COMPLETADA')
    a_tiempo = sum(1 for t in validadas.only('fecha_completada', 'fecha_limite', 'estado') if t.a_tiempo)
    vencidas = (tareas.filter(estado__in=ABIERTAS, fecha_limite__lt=hoy).values('colaborador').annotate(n=Count('id')).order_by('-n')[:5])
    nombres = {u.pk: u for u in User.objects.filter(pk__in=[v['colaborador'] for v in vencidas])}

    riesgo = []
    for o in (OrdenTrabajo.objects.filter(estado__in=['LIBERADA', 'EN_PRODUCCION', 'EN_PAUSA'], fecha_compromiso__isnull=False,
                                         fecha_compromiso__lte=hoy + timedelta(days=3)).select_related('cliente').order_by('fecha_compromiso')[:8]):
        areas = list(o.areas.exclude(estado='CANCELADA'))
        riesgo.append({'numero': o.numero or o.solicitud, 'titulo': o.titulo, 'cliente': o.cliente.nombre, 'compromiso': o.fecha_compromiso.isoformat(),
                       'vencida': o.fecha_compromiso < hoy, 'partes': len(areas), 'listas': sum(1 for a in areas if a.estado == 'TERMINADA')})

    dinero = {}
    try:
        from apps.finanzas.rentabilidad import rentabilidad_ordenes
        r = rentabilidad_ordenes(hoy.replace(day=1) - timedelta(days=60), hoy)
        perdidas = [o for o in r['ordenes'] if o.get('alerta')][:5]
        dinero = {'margen': r['totales']['margen'], 'en_alerta': r['totales']['en_alerta'], 'retrabajo': _f(r['totales']['retrabajo']),
                  'peores': [{'numero': o['numero'], 'cliente': o['cliente'], 'margen': o['margen'], 'utilidad': _f(o['utilidad'])} for o in perdidas]}
    except Exception:  # noqa: BLE001 (sin finanzas cargadas, el resumen sigue)
        dinero = {}

    ranking = [f for f in calcular_ranking(hoy.replace(day=1)) if f.get('puntaje_total') is not None]
    return {
        'semana': {'desde': desde.isoformat(), 'hasta': hasta.isoformat()},
        'tareas': {'con_fecha': semana.count(), 'validadas': validadas.count(), 'a_tiempo': a_tiempo,
                   'abiertas_vencidas': tareas.filter(estado__in=ABIERTAS, fecha_limite__lt=hoy).count(),
                   'por_validar': tareas.filter(estado='EN_REVISION').count()},
        'mas_atrasados': [{'nombre': _nombre(nombres.get(v['colaborador'])), 'vencidas': v['n']} for v in vencidas],
        'ot_en_riesgo': riesgo,
        'dinero': dinero,
        'mejores': [{'nombre': f['nombre'], 'puntaje': f['puntaje_total'], 'departamento': f.get('departamento')} for f in ranking[:3]],
        'por_debajo': [{'nombre': f['nombre'], 'puntaje': f['puntaje_total'],
                        'motivos': [m for m in (f.get('motivos') or []) if 'computadora' not in str(m).lower()][:2]}
                       for f in ranking if f.get('evaluacion') == 'BAJO_MINIMO'][:5],
    }


def _dia(iso):
    from datetime import date as _d
    return _d.fromisoformat(iso).strftime('%d/%m')


def texto_sin_ia(d):
    t = d['tareas']
    lineas = [f"Semana del {_dia(d['semana']['desde'])} al {_dia(d['semana']['hasta'])}."]
    if t['con_fecha']:
        lineas.append(f"Tareas: {t['validadas']} de {t['con_fecha']} validadas ({t['a_tiempo']} a tiempo). "
                      f"Quedan {t['abiertas_vencidas']} vencidas sin entregar y {t['por_validar']} por validar.")
    if d['mejores']:
        lineas.append('Van bien: ' + ', '.join(f"{m['nombre']} ({m['puntaje']:g})" for m in d['mejores']) + '.')
    if d['por_debajo']:
        lineas.append('Necesitan atención: ' + '; '.join(f"{p['nombre']} ({p['puntaje']:g}{': ' + ', '.join(p['motivos']) if p['motivos'] else ''})"
                                                         for p in d['por_debajo']) + '.')
    if d['mas_atrasados']:
        lineas.append('Más tareas vencidas: ' + ', '.join(f"{a['nombre']} ({a['vencidas']})" for a in d['mas_atrasados']) + '.')
    if d['ot_en_riesgo']:
        lineas.append('OT en riesgo: ' + '; '.join(f"{o['numero']} {o['cliente']} ({'vencida' if o['vencida'] else 'vence el ' + _dia(o['compromiso'])}, "
                                                   f"{o['listas']}/{o['partes']} partes listas)" for o in d['ot_en_riesgo']) + '.')
    din = d.get('dinero') or {}
    if din.get('peores'):
        lineas.append(f"Dinero: margen de los últimos meses {din['margen']}%; {din['en_alerta']} OT con margen bajo o pérdida, "
                      + 'las peores ' + ', '.join(f"{o['numero']} ({o['margen']}%)" for o in din['peores'][:3]) + '.')
    return '\n'.join(lineas)


SISTEMA_RESUMEN = (
    "Eres el analista de operaciones de ADZONE, agencia de marketing en República Dominicana. Escribe en español dominicano "
    "profesional, directo y breve, para la Dirección. Usa SOLO los datos que te dan (no inventes cifras ni nombres). "
    "Estructura: 1) una frase con cómo fue la semana; 2) «Lo que va bien» (2-3 viñetas); 3) «Lo que hay que mirar» (OT en riesgo, "
    "personas que necesitan apoyo, dónde se pierde dinero; 3-5 viñetas con nombres y números); 4) «Para esta semana» (2-3 acciones "
    "concretas). Sin saludos ni despedidas. Máximo 220 palabras. Sé respetuoso con las personas: habla de apoyo, no de culpas.")


def generar_resumen(hoy=None, forzar=False):
    hoy = hoy or timezone.localdate()
    lunes = hoy - timedelta(days=hoy.weekday())
    existente = ResumenSemanal.objects.filter(semana=lunes).first()
    if existente and not forzar:
        return existente
    d = datos_semana(hoy)
    texto = ia.preguntar(SISTEMA_RESUMEN, 'Datos de la semana (JSON):\n' + json.dumps(d, ensure_ascii=False, default=str), max_tokens=900)
    r, _ = ResumenSemanal.objects.update_or_create(semana=lunes, defaults={'datos': d, 'texto': texto or texto_sin_ia(d), 'con_ia': bool(texto)})
    return r


def avisar_resumen(hoy=None):
    """Los lunes: genera el resumen y avisa a la Dirección."""
    hoy = hoy or timezone.localdate()
    if hoy.weekday() != 0:
        return 0
    from apps.core.permisos import con_permiso
    from .servicios import avisar
    r = generar_resumen(hoy)
    primera = r.texto.strip().splitlines()[0][:200] if r.texto.strip() else ''
    avisar(list(con_permiso('direccion')), 'TALENTO', 'Resumen de la semana', primera, enlace='/resumen-semanal')
    return 1


# ------------------------------------------------------------------ Sugerir a quién asignar
PALABRA = re.compile(r'[a-záéíóúñ0-9]{4,}', re.I)


def _palabras(texto):
    return {p.lower() for p in PALABRA.findall(texto or '')}


def sugerir_asignacion(asignador, titulo='', descripcion='', permiso='tareas.asignar', limite=5):
    """Ordena a las personas que `asignador` puede asignar: menos carga, mejor cumplimiento y calidad, y experiencia en algo parecido."""
    from .permisos import equipo_gestionable
    gente = list(equipo_gestionable(asignador, permiso).select_related('perfil__puesto_trabajo'))
    if not gente:
        return []
    hoy = timezone.localdate()
    hace = hoy - timedelta(days=90)
    ids = [u.pk for u in gente]
    abiertas = {r['colaborador']: r for r in Tarea.objects.filter(colaborador__in=ids, estado__in=ABIERTAS).values('colaborador')
                .annotate(n=Count('id'), horas=Sum('horas_estimadas'), vencidas=Count('id', filter=Q(fecha_limite__lt=hoy)))}
    hechas = list(Tarea.objects.filter(colaborador__in=ids, estado='COMPLETADA', fecha_completada__gte=hace)
                  .only('colaborador_id', 'titulo', 'fecha_completada', 'fecha_limite', 'calificacion_calidad', 'estado'))
    claves = _palabras(f'{titulo} {descripcion}')
    filas = []
    for u in gente:
        mias = [t for t in hechas if t.colaborador_id == u.pk]
        a_tiempo = (sum(1 for t in mias if t.a_tiempo) / len(mias) * 100) if mias else None
        calidad = [t.calificacion_calidad for t in mias if t.calificacion_calidad]
        calidad = sum(calidad) / len(calidad) if calidad else None
        parecidas = [t.titulo for t in mias if claves and len(claves & _palabras(t.titulo)) >= 1]
        ab = abiertas.get(u.pk, {})
        n, vencidas = ab.get('n', 0), ab.get('vencidas', 0)
        horas = float(ab.get('horas') or 0)
        semana = float(getattr(getattr(u, 'perfil', None), 'horas_semana', None) or 44)
        carga = min(100.0, (horas or n * 4) / semana * 100)  # sin horas estimadas, cada tarea cuenta como medio día
        puntos = (100 - carga) * 0.40 + (a_tiempo if a_tiempo is not None else 70) * 0.25 \
            + ((calidad - 1) / 4 * 100 if calidad else 70) * 0.15 + min(len(parecidas), 3) / 3 * 100 * 0.20 - vencidas * 5
        razones = [f'{n} tarea(s) abierta(s)' + (f', {vencidas} vencida(s)' if vencidas else '')]
        if a_tiempo is not None:
            razones.append(f'{round(a_tiempo)} % a tiempo')
        if calidad:
            razones.append(f'calidad {calidad:.1f}/5')
        if parecidas:
            razones.append(f'ya hizo {len(parecidas)} parecida(s): «{parecidas[0][:50]}»')
        puesto = getattr(getattr(u, 'perfil', None), 'puesto_trabajo', None)
        filas.append({'id': u.pk, 'nombre': _nombre(u), 'puesto': puesto.nombre if puesto else None, 'puntos': round(puntos, 1),
                      'carga': round(carga), 'abiertas': n, 'vencidas': vencidas, 'a_tiempo': round(a_tiempo) if a_tiempo is not None else None,
                      'calidad': round(calidad, 1) if calidad else None, 'parecidas': len(parecidas), 'razon': ' · '.join(razones)})
    filas.sort(key=lambda f: -f['puntos'])
    return filas[:limite]


# ------------------------------------------------------------------ Borrador de evaluación
SISTEMA_EVALUACION = (
    "Ayudas a un supervisor de ADZONE (agencia de marketing en República Dominicana) a redactar la evaluación de desempeño de una persona "
    "de su equipo. Escribe en español y habla de la persona evaluada en tercera persona "
    "(«Ana entrega…»). Usa SOLO los datos que te dan; no inventes hechos. Tono respetuoso, concreto y útil. Responde SOLO con JSON válido: "
    '{"fortalezas": "2-4 frases", "a_mejorar": "2-3 frases con acciones concretas", "comentario": "1-2 frases de cierre"}.')


def _datos_evaluacion(evaluacion):
    from .ficha import _sin_monitoreo, ficha
    u = evaluacion.evaluado
    hoy = timezone.localdate()
    # A la API nunca va la actividad en la computadora, aunque quien evalúa pueda verla
    f = _sin_monitoreo(ficha(u, hoy.replace(day=1), visor=evaluacion.evaluador, meses=6))
    t = f.get('tareas') or {}
    return {
        'nombre': u.first_name or _nombre(u), 'puesto': (f.get('persona') or {}).get('puesto'), 'tipo': evaluacion.get_tipo_display(),
        'tareas_mes': {k: t.get(k) for k in ('validadas', 'a_tiempo_pct', 'calidad_pct', 'vencidas', 'a_la_primera_pct') if k in t},
        'kpis': [{'nombre': k.get('nombre'), 'meta': _f(k.get('meta')), 'valor': _f(k.get('valor')), 'cumplimiento': _f(k.get('cumplimiento'))}
                 for k in (f.get('kpis') or []) if not k.get('oculto')][:8],
        'asistencia': {k: (f.get('horario') or {}).get(k) for k in ('adherencia', 'tardanzas', 'ausencias') if k in (f.get('horario') or {})},
        'tendencia_puntaje': [x.get('puntaje') for x in (f.get('tendencia') or [])],
        'alertas': [a.get('texto') for a in (f.get('alertas') or [])][:5],
    }


def borrador_evaluacion(evaluacion):
    d = _datos_evaluacion(evaluacion)
    texto = ia.preguntar(SISTEMA_EVALUACION, 'Datos (JSON):\n' + json.dumps(d, ensure_ascii=False, default=str), max_tokens=700)
    if texto:
        try:
            j = json.loads(texto[texto.index('{'):texto.rindex('}') + 1])
            return {'fortalezas': str(j.get('fortalezas', ''))[:2000], 'a_mejorar': str(j.get('a_mejorar', ''))[:2000],
                    'comentario': str(j.get('comentario', ''))[:2000], 'con_ia': True, 'datos': d}
        except (ValueError, AttributeError):
            pass
    return {**_sin_ia_evaluacion(d), 'con_ia': False, 'datos': d}


def _sin_ia_evaluacion(d):
    t, nombre = d['tareas_mes'], d['nombre']
    fuertes, mejorar = [], []
    if (t.get('a_tiempo_pct') or 0) >= 85:
        fuertes.append(f"{nombre} entrega a tiempo ({t['a_tiempo_pct']:g} % de sus tareas del mes).")
    elif t.get('a_tiempo_pct') is not None:
        mejorar.append(f"Subir las entregas a tiempo (hoy {t['a_tiempo_pct']:g} %): planificar la semana y avisar antes si una fecha corre riesgo.")
    if (t.get('calidad_pct') or 0) >= 80:
        fuertes.append(f"La calidad de su trabajo es buena ({t['calidad_pct']:g} %).")
    elif t.get('calidad_pct') is not None:
        mejorar.append("Revisar el trabajo con la lista de validación antes de entregarlo, para reducir devoluciones.")
    altos = [k['nombre'] for k in d['kpis'] if (k.get('cumplimiento') or 0) >= 100]
    bajos = [k for k in d['kpis'] if k.get('cumplimiento') is not None and k['cumplimiento'] < 80]
    if altos:
        fuertes.append(f"Cumple o supera: {', '.join(altos[:3])}.")
    for k in bajos[:2]:
        mejorar.append(f"«{k['nombre']}» va al {k['cumplimiento']:g} %: acordar con el supervisor cómo acercarse a la meta.")
    if (d['asistencia'].get('tardanzas') or 0) > 2:
        mejorar.append(f"Puntualidad: {d['asistencia']['tardanzas']} llegadas tarde este mes.")
    return {'fortalezas': ' '.join(fuertes) or f"{nombre} cumple con sus responsabilidades del puesto.",
            'a_mejorar': ' '.join(mejorar) or "Mantener el ritmo y proponer una mejora concreta para su área.",
            'comentario': "Borrador generado con los datos del mes: revísalo y ajústalo con lo que tú has observado."}
