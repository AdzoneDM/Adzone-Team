"""Expediente del cliente: todo el trabajo hecho para él (proyectos, órdenes, tareas, archivos y entregas), con quién lo hizo,
quién lo asignó, quién lo cambió y cuándo, y el reporte del período en PDF o Excel.

Las tareas que se muestran respetan los permisos de siempre: Dirección ve todas; los demás, las suyas, las de su equipo y las que asignaron.
"""
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from apps.desempeno.models import EvidenciaArchivo, HistorialTarea, Tarea
from apps.desempeno.permisos import equipo_gestionable, es_administrador

ESTADOS = dict(Tarea.ESTADO_CHOICES)


def _n(u):
    return (u.get_full_name() or u.username) if u else None


def tareas_del_cliente(cliente, user):
    qs = Tarea.objects.filter(Q(cliente_ref=cliente) | Q(proyecto__cliente=cliente) | Q(orden__cliente=cliente))
    if not es_administrador(user):
        subs = equipo_gestionable(user, 'equipo.ver')
        qs = qs.filter(Q(colaborador=user) | Q(companeros=user) | Q(colaborador__in=subs) | Q(asignada_por=user))
    return qs.distinct()


def _dia(v):
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def rango(params):
    """dia=AAAA-MM-DD | mes=AAAA-MM | desde/hasta. Devuelve (desde, hasta) o (None, None)."""
    if params.get('dia'):
        d = _dia(params['dia'])
        return d, d
    if params.get('mes'):
        try:
            a, m = map(int, params['mes'].split('-')[:2])
            ini = date(a, m, 1)
            fin = (date(a + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
            return ini, fin
        except ValueError:
            return None, None
    return _dia(params.get('desde')), _dia(params.get('hasta'))


def filtrar(qs, params):
    """Empleado, período (trabajó en esos días: entre que empezó y que la entregó o terminó), proyecto y estado."""
    if params.get('empleado'):
        qs = qs.filter(Q(colaborador_id=params['empleado']) | Q(companeros__id=params['empleado'])).distinct()
    if params.get('proyecto'):
        qs = qs.filter(proyecto_id=params['proyecto']) if params['proyecto'] != 'sin' else qs.filter(proyecto__isnull=True)
    if params.get('estado'):
        qs = qs.filter(estado=params['estado'])
    if params.get('q'):
        qs = qs.filter(Q(titulo__icontains=params['q']) | Q(descripcion__icontains=params['q']))
    desde, hasta = rango(params)
    if desde or hasta:
        z = timezone.get_current_timezone()
        if hasta:   # empezó (o se creó) antes de que termine el período
            fin = timezone.make_aware(datetime.combine(hasta, time.max), z)
            qs = qs.filter(Q(fecha_inicio_trabajo__lte=fin) | Q(fecha_inicio_trabajo__isnull=True, fecha_creacion__lte=fin))
        if desde:   # y no se había terminado antes de que empiece
            ini = timezone.make_aware(datetime.combine(desde, time.min), z)
            qs = qs.filter(Q(fecha_entrega_real__gte=ini) | Q(fecha_completada__gte=desde)
                           | Q(fecha_entrega_real__isnull=True, fecha_completada__isnull=True))
    return qs


def ficha_tarea(t, modificaciones):
    orden = t.orden
    return {
        'id': t.id, 'titulo': t.titulo, 'descripcion': (t.descripcion or '')[:600], 'estado': t.estado, 'estado_texto': ESTADOS.get(t.estado, t.estado),
        'proyecto': f'{t.proyecto.codigo} · {t.proyecto.nombre}' if t.proyecto_id else None, 'proyecto_id': t.proyecto_id,
        'orden': orden.codigo if orden else None, 'orden_id': t.orden_id,
        'responsable': _n(t.colaborador), 'responsable_id': t.colaborador_id, 'companeros': [_n(u) for u in t.companeros.all()],
        'asignada_por': _n(t.asignada_por), 'creada': t.fecha_creacion,
        'inicio_trabajo': t.fecha_inicio_trabajo, 'fecha_limite': t.fecha_limite, 'entregada': t.fecha_entrega_real,
        'finalizada': t.fecha_validacion or (t.fecha_completada if t.estado == 'COMPLETADA' else None),
        'resuelta_por': _n(t.validada_por), 'entrega_cliente': orden.fecha_entrega if orden and orden.fecha_entrega else None,
        'evidencia_nota': t.evidencia_nota, 'evidencia_enlace': t.evidencia_enlace,
        'evidencias': [{'id': e.id, 'nombre': e.nombre_original or e.archivo.name.rsplit('/', 1)[-1], 'es_imagen': e.es_imagen,
                        'url': f'/api/desempeno/evidencias/{e.id}/archivo/', 'purgado': e.purgado} for e in t.evidencias.all()],
        'modificaciones': modificaciones.get(t.id, []),
    }


def tareas(qs):
    qs = qs.select_related('colaborador', 'asignada_por', 'validada_por', 'proyecto', 'orden').prefetch_related('companeros', 'evidencias')
    lista = list(qs.order_by('-fecha_creacion')[:1000])
    mods = {}
    for h in HistorialTarea.objects.filter(tarea__in=lista).exclude(accion__in=['COMENTADA']).select_related('usuario').order_by('fecha'):
        mods.setdefault(h.tarea_id, []).append({'accion': h.get_accion_display(), 'usuario': _n(h.usuario), 'fecha': h.fecha,
                                               'detalle': (h.comentario or '')[:300]})
    return [ficha_tarea(t, mods) for t in lista]


def archivos(cliente, qs_tareas):
    """Evidencias de las tareas (que se pueden ver) y archivos de las órdenes del cliente."""
    from .models import ArchivoOrden
    ev = [{'tipo': 'Evidencia de tarea', 'nombre': e.nombre_original or 'archivo', 'fecha': e.fecha, 'subido_por': _n(e.subido_por),
           'de': e.tarea.titulo, 'url': f'/api/desempeno/evidencias/{e.id}/archivo/', 'es_imagen': e.es_imagen, 'purgado': e.purgado}
          for e in EvidenciaArchivo.objects.filter(tarea__in=qs_tareas).select_related('tarea', 'subido_por').order_by('-fecha')[:500]]
    ao = [{'tipo': f'Orden {a.orden.codigo} · {a.get_categoria_display()}', 'nombre': a.nombre_original, 'fecha': a.fecha, 'subido_por': _n(a.subido_por),
           'de': a.orden.titulo, 'url': f'/api/operaciones/archivos/{a.id}/', 'es_imagen': (a.tipo or '').startswith('image/'), 'purgado': False}
          for a in ArchivoOrden.objects.filter(orden__cliente=cliente).select_related('orden', 'subido_por')[:500]]
    return sorted(ev + ao, key=lambda x: x['fecha'], reverse=True)


def entregas(cliente, qs_tareas, ordenes):
    """Historial de entregas: órdenes entregadas al cliente y tareas entregadas/terminadas."""
    filas = [{'tipo': 'Orden de trabajo', 'que': f'{o.codigo} · {o.titulo}', 'fecha': o.fecha_entrega, 'recibido_por': o.recibido_por,
              'estado': o.get_estado_display()} for o in ordenes if o.fecha_entrega]
    for t in qs_tareas.filter(Q(fecha_entrega_real__isnull=False) | Q(estado='COMPLETADA')).select_related('colaborador', 'validada_por'):
        filas.append({'tipo': 'Tarea', 'que': t.titulo, 'fecha': (t.fecha_entrega_real.date() if t.fecha_entrega_real else t.fecha_completada),
                      'recibido_por': f'Hecha por {_n(t.colaborador)}' + (f' · validó {_n(t.validada_por)}' if t.validada_por_id else ''),
                      'estado': ESTADOS.get(t.estado, t.estado)})
    return sorted([f for f in filas if f['fecha']], key=lambda f: f['fecha'], reverse=True)


# ------------------------------------------------------------------ Reporte (PDF y Excel)
def _f(v, hora=False):
    if not v:
        return '—'
    if isinstance(v, datetime):
        v = timezone.localtime(v)
        return v.strftime('%d/%m/%Y %H:%M' if hora else '%d/%m/%Y')
    return v.strftime('%d/%m/%Y')


def datos_reporte(cliente, user, params):
    from .permisos import filtro_ordenes, filtro_proyectos
    desde, hasta = rango(params)
    qs = filtrar(tareas_del_cliente(cliente, user), params)
    lista = tareas(qs)
    proyectos = cliente.proyectos.all()
    f = filtro_proyectos(user)
    proyectos = proyectos.filter(f).distinct() if f is not None else proyectos
    ordenes = cliente.ordenes.all()
    f = filtro_ordenes(user)
    ordenes = ordenes.filter(f).distinct() if f is not None else ordenes
    if params.get('proyecto') and params['proyecto'] != 'sin':
        proyectos = proyectos.filter(pk=params['proyecto'])
        ordenes = ordenes.filter(proyecto_id=params['proyecto'])
    if desde:
        ordenes = ordenes.filter(Q(fecha_entrega__isnull=True) | Q(fecha_entrega__gte=desde))
    if hasta:
        ordenes = ordenes.filter(fecha_creacion__date__lte=hasta)
    return {'cliente': cliente, 'desde': desde, 'hasta': hasta, 'tareas': lista, 'proyectos': list(proyectos), 'ordenes': list(ordenes),
            'generado': timezone.localtime(), 'por': _n(user)}


def excel(d):
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = 'Trabajos realizados'
    c = d['cliente']
    ws.append([f'Reporte de trabajos realizados — {c.nombre}'])
    ws['A1'].font = Font(bold=True, size=14)
    ws.append([f"Período: {_f(d['desde'])} al {_f(d['hasta'])}" if d['desde'] or d['hasta'] else 'Período: todo el historial'])
    ws.append([f"Generado el {_f(d['generado'], True)} por {d['por']}"])
    ws.append([])
    cab = ['Tarea', 'Descripción', 'Proyecto', 'Orden', 'Responsable', 'Con', 'Asignada por', 'Creada', 'Empezó', 'Entregada',
           'Finalizada', 'Resuelta por', 'Entrega al cliente', 'Estado', 'Evidencias', 'Modificaciones']
    ws.append(cab)
    for celda in ws[5]:
        celda.font = Font(bold=True, color='FFFFFF')
        celda.fill = PatternFill('solid', fgColor='224B9A')
    for t in d['tareas']:
        ws.append([t['titulo'], t['descripcion'], t['proyecto'] or '', t['orden'] or '', t['responsable'] or '', ', '.join(t['companeros']),
                   t['asignada_por'] or '', _f(t['creada'], True), _f(t['inicio_trabajo'], True), _f(t['entregada'], True), _f(t['finalizada'], True),
                   t['resuelta_por'] or '', _f(t['entrega_cliente']), t['estado_texto'],
                   ', '.join(e['nombre'] for e in t['evidencias']) + (f" · {t['evidencia_enlace']}" if t['evidencia_enlace'] else ''),
                   '\n'.join(f"{_f(m['fecha'], True)} {m['usuario'] or ''}: {m['accion']}" for m in t['modificaciones'])])
    for col, ancho in zip('ABCDEFGHIJKLMNOP', (34, 40, 26, 12, 22, 22, 20, 16, 16, 16, 16, 20, 14, 14, 30, 46)):
        ws.column_dimensions[col].width = ancho
    for fila in ws.iter_rows(min_row=6):
        for celda in fila:
            celda.alignment = Alignment(wrap_text=True, vertical='top')
    ws.freeze_panes = 'A6'
    hp = wb.create_sheet('Proyectos y órdenes')
    hp.append(['Tipo', 'Código', 'Nombre', 'Estado', 'Responsable / área', 'Inicio', 'Entrega'])
    for celda in hp[1]:
        celda.font = Font(bold=True)
    for p in d['proyectos']:
        hp.append(['Proyecto', p.codigo, p.nombre, p.get_estado_display(), _n(p.responsable) or '', _f(p.fecha_inicio), _f(p.fecha_fin)])
    for o in d['ordenes']:
        hp.append(['Orden de trabajo', o.codigo, o.titulo, o.get_estado_display(), o.departamento.nombre if o.departamento_id else '',
                   _f(o.fecha_aprobacion), _f(o.fecha_entrega)])
    for col, ancho in zip('ABCDEFG', (16, 14, 40, 20, 24, 14, 14)):
        hp.column_dimensions[col].width = ancho
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def pdf(d):
    from io import BytesIO
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    b = BytesIO()
    doc = SimpleDocTemplate(b, pagesize=landscape(letter), leftMargin=1.2 * cm, rightMargin=1.2 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
                            title=f"Trabajos realizados — {d['cliente'].nombre}")
    est = getSampleStyleSheet()
    chico = ParagraphStyle('chico', parent=est['Normal'], fontSize=7.5, leading=9.5)
    normal = ParagraphStyle('n', parent=est['Normal'], fontSize=9.5, leading=12)
    titulo = ParagraphStyle('t', parent=est['Title'], fontSize=17, textColor=colors.HexColor('#224b9a'), alignment=0)
    sub = ParagraphStyle('s', parent=est['Heading2'], fontSize=12, textColor=colors.HexColor('#16357a'), spaceBefore=10)
    P = lambda t, s=chico: Paragraph(escape(str(t or '—')).replace('\n', '<br/>'), s)  # noqa: E731
    c = d['cliente']
    partes = []
    cabecera = [[Paragraph(f'Reporte de trabajos realizados<br/><font size=12 color="#3d4a63">{escape(c.nombre)}</font>', titulo)]]
    if c.logo:
        try:
            cabecera[0].insert(0, Image(c.logo.path, width=2.2 * cm, height=2.2 * cm, kind='proportional'))
        except Exception:  # noqa: BLE001 (sin logo legible, el reporte sale igual)
            pass
    partes.append(Table(cabecera, hAlign='LEFT'))
    periodo = f"{_f(d['desde'])} al {_f(d['hasta'])}" if d['desde'] or d['hasta'] else 'todo el historial'
    datos_cliente = ' · '.join(x for x in [c.get_tipo_display(), f'RNC {c.rnc}' if c.rnc else '', c.contacto, c.telefono, c.correo] if x)
    partes += [P(f"Período consultado: {periodo}", normal), P(datos_cliente, normal),
               P(f"Generado el {_f(d['generado'], True)} por {d['por']} · ADZONE", chico), Spacer(1, 6)]
    estilo = TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#224b9a')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                         ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d6dbe6')),
                         ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f7fb')])])
    if d['proyectos'] or d['ordenes']:
        partes.append(Paragraph('Proyectos y órdenes de trabajo', sub))
        filas = [[P(x) for x in ('Tipo', 'Código', 'Nombre', 'Estado', 'Inicio', 'Entrega')]]
        filas += [[P('Proyecto'), P(p.codigo), P(p.nombre), P(p.get_estado_display()), P(_f(p.fecha_inicio)), P(_f(p.fecha_fin))] for p in d['proyectos']]
        filas += [[P('Orden'), P(o.codigo), P(o.titulo), P(o.get_estado_display()), P(_f(o.fecha_aprobacion)), P(_f(o.fecha_entrega))] for o in d['ordenes']]
        t = Table(filas, colWidths=[2.2 * cm, 2.6 * cm, 10 * cm, 3.6 * cm, 2.6 * cm, 2.6 * cm], repeatRows=1)
        t.setStyle(estilo)
        partes.append(t)
    partes.append(Paragraph(f"Trabajos realizados ({len(d['tareas'])})", sub))
    filas = [[P(x) for x in ('Trabajo', 'Proyecto / orden', 'Responsable', 'Asignó', 'Ejecución', 'Finalizada y entrega', 'Estado', 'Evidencias')]]
    for t in d['tareas']:
        filas.append([
            P(f"{t['titulo']}\n{t['descripcion'][:300]}"), P(' / '.join(x for x in [t['proyecto'], t['orden']] if x) or '—'),
            P(', '.join([t['responsable'] or '—', *t['companeros']])), P(t['asignada_por']),
            P(f"Empezó: {_f(t['inicio_trabajo'], True)}\nEntregó: {_f(t['entregada'], True)}"),
            P(f"Finalizada: {_f(t['finalizada'], True)}" + (f"\npor {t['resuelta_por']}" if t['resuelta_por'] else '') + f"\nAl cliente: {_f(t['entrega_cliente'])}"),
            P(t['estado_texto']),
            P('\n'.join([e['nombre'] for e in t['evidencias']][:6] + ([t['evidencia_enlace']] if t['evidencia_enlace'] else [])) or '—'),
        ])
    tabla = Table(filas, colWidths=[6.6 * cm, 3.4 * cm, 3 * cm, 2.6 * cm, 3.4 * cm, 3.4 * cm, 2 * cm, 3 * cm], repeatRows=1)
    tabla.setStyle(estilo)
    partes.append(tabla)
    doc.build(partes)
    return b.getvalue()
