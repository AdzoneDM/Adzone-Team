"""Ficha de una computadora (el «Computer Details» de Teramind): cómo se usó su tiempo en un rango de fechas."""
from collections import Counter, defaultdict
from datetime import timedelta

from django.utils import timezone

from apps.asistencia.servicios import rango
from .models import IMPRODUCTIVA, NEUTRAL, PRODUCTIVA, Actividad, AlertaEnviada, Captura, Incidencia
from .servicios import _resumir

HUECO_SESION = timedelta(minutes=2)  # dos minutos seguidos en la misma ventana, con hasta 1 minuto de hueco, son la misma sesión


def _nombre(u):
    return (u.get_full_name() or u.username) if u else None


def _tarea(registro):
    if registro is None:
        return None
    if registro.tarea_id:
        return registro.tarea.titulo
    if registro.orden_id:
        return f'{registro.orden.numero or registro.orden.solicitud} · {registro.orden.titulo}'
    if registro.proyecto_id:
        return registro.proyecto.nombre
    return registro.descripcion or None


def sesiones(filas):
    """Une minutos seguidos de la misma persona, aplicación, sitio y ventana en una sola fila del registro."""
    salida, actual = [], None
    for f in filas:
        clave = (f.usuario_id, f.app, f.dominio, f.titulo)
        if actual and actual['clave'] == clave and f.minuto - actual['ultimo'] <= HUECO_SESION:
            actual['ultimo'] = f.minuto
            actual['minutos'] += 1
            actual['activos'] += f.activos >= 30
            actual['cats'][f.categoria] += 1
            actual['tarea'] = actual['tarea'] or _tarea(f.registro)
            continue
        if actual:
            salida.append(actual)
        actual = {'clave': clave, 'inicio': f.minuto, 'ultimo': f.minuto, 'minutos': 1, 'activos': int(f.activos >= 30),
                  'cats': Counter({f.categoria: 1}), 'usuario': f.usuario, 'tarea': _tarea(f.registro)}
    if actual:
        salida.append(actual)
    return [{'inicio': s['inicio'], 'fin': s['ultimo'] + timedelta(minutes=1), 'minutos': s['minutos'], 'activos': s['activos'],
             'persona': _nombre(s['usuario']), 'usuario': s['clave'][0], 'app': s['clave'][1], 'dominio': s['clave'][2], 'titulo': s['clave'][3],
             'categoria': s['cats'].most_common(1)[0][0], 'tarea': s['tarea']} for s in salida]


def ficha(dispositivo, desde, hasta, persona=None, texto=''):
    qs = (Actividad.objects.filter(dispositivo=dispositivo, minuto__range=rango(desde, hasta))
          .select_related('usuario', 'registro__tarea', 'registro__orden', 'registro__proyecto').order_by('minuto'))
    if persona:
        qs = qs.filter(usuario_id=persona)
    filas = list(qs)
    personas = Counter(f.usuario for f in filas)
    if texto:
        t = texto.lower()
        filas = [f for f in filas if t in (f.app or '').lower() or t in (f.dominio or '').lower() or t in (f.titulo or '').lower()]

    # Actividad por día: activo (productivo, neutral, improductivo) e inactivo
    dias = {}
    d = desde
    while d <= hasta:
        dias[d] = Counter()
        d += timedelta(days=1)
    # Mapa de teclado y ratón: día de la semana × hora, con la intensidad promedio y los minutos
    mapa = defaultdict(lambda: [0, 0])
    tareas = Counter()
    for f in filas:
        local = timezone.localtime(f.minuto)
        c = dias.setdefault(local.date(), Counter())
        c['registrados'] += 1
        if f.activos >= 30:
            c['activos'] += 1
            c[f.categoria] += 1
        m = mapa[(local.weekday(), local.hour)]
        m[0] += 1
        m[1] += f.intensidad
        nombre_tarea = _tarea(f.registro)
        if nombre_tarea:
            tareas[nombre_tarea] += 1
    por_dia = [{'dia': k, 'registrados': v['registrados'], 'activos': v['activos'], 'inactivos': v['registrados'] - v['activos'],
                'productivos': v[PRODUCTIVA], 'neutrales': v[NEUTRAL], 'improductivos': v[IMPRODUCTIVA]} for k, v in sorted(dias.items())]
    mapa_horas = [[{'minutos': mapa[(dia, h)][0], 'intensidad': round(mapa[(dia, h)][1] / mapa[(dia, h)][0]) if mapa[(dia, h)][0] else None}
                   for h in range(24)] for dia in range(7)]

    usuarios = [u.pk for u in personas] or [dispositivo.usuario_id]
    incid = [{'id': i.pk, 'tipo': 'REGLA', 'fecha': i.ultima, 'persona': _nombre(i.usuario), 'titulo': i.regla.nombre, 'riesgo': i.regla.riesgo,
              'detalle': f'{i.minutos} min · {i.ejemplo}', 'estado': i.estado}
             for i in Incidencia.objects.filter(usuario_id__in=usuarios, dia__range=(desde, hasta)).select_related('regla', 'usuario')
             if i.minutos >= i.regla.minutos_minimos]
    avisos = [{'id': a.pk, 'tipo': a.tipo, 'fecha': a.creada, 'persona': _nombre(a.usuario), 'titulo': {
                  'SIN_PC': 'Marcó entrada y la computadora no reportaba', 'INACTIVO': 'Inactivo en jornada',
                  'IMPRODUCTIVO': 'Día con mucho tiempo improductivo', 'TARDE': 'Llegó tarde', 'SIN_MARCAR': 'No marcó entrada'}.get(a.tipo, a.tipo),
               'riesgo': None, 'detalle': a.detalle, 'estado': None}
              for a in AlertaEnviada.objects.filter(usuario_id__in=usuarios, creada__range=rango(desde, hasta),
                                                     tipo__in=('SIN_PC', 'INACTIVO', 'IMPRODUCTIVO')).select_related('usuario')]
    alertas = sorted(incid + avisos, key=lambda x: x['fecha'], reverse=True)

    lista = sesiones(filas)
    lista.reverse()
    caps = list(Captura.objects.filter(dispositivo=dispositivo, tomada_en__range=rango(desde, hasta)).order_by('-tomada_en')[:300])
    ahora = timezone.now()
    return {
        'equipo': {
            'id': dispositivo.pk, 'nombre': dispositivo.nombre, 'nombre_equipo': dispositivo.nombre_equipo, 'sistema': dispositivo.sistema,
            'version_agente': dispositivo.version_agente, 'ip': dispositivo.ip, 'activo': dispositivo.activo, 'monitorear': dispositivo.monitorear,
            'persona': _nombre(dispositivo.usuario), 'usuario': dispositivo.usuario_id, 'creado': dispositivo.creado,
            'ultimo_contacto': dispositivo.ultimo_contacto,
            'en_linea': bool(dispositivo.activo and dispositivo.ultimo_contacto and ahora - dispositivo.ultimo_contacto < timedelta(minutes=5)),
            'activo_fijo': ({'id': dispositivo.activo_fijo.pk, 'codigo': dispositivo.activo_fijo.codigo, 'nombre': dispositivo.activo_fijo.nombre}
                            if hasattr(dispositivo, 'activo_fijo') else None),
        },
        'desde': desde, 'hasta': hasta,
        'personas': [{'id': u.pk, 'nombre': _nombre(u), 'minutos': n} for u, n in personas.most_common()],
        'resumen': {k: v for k, v in _resumir(filas).items()},
        'por_dia': por_dia, 'mapa_horas': mapa_horas,
        'tareas': [{'nombre': k, 'minutos': v} for k, v in tareas.most_common(10)],
        'registro': lista[:500], 'sesiones_total': len(lista),
        'alertas': alertas[:200],
        'capturas': [{'id': c.pk, 'hora': timezone.localtime(c.tomada_en).strftime('%d/%m %H:%M'), 'app': c.app} for c in caps],
        'ips': [{'ip': i.ip, 'primera': i.primera, 'ultima': i.ultima, 'veces': i.veces} for i in dispositivo.ips.all()[:50]],
    }
