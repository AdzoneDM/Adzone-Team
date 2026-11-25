"""Reportes de facturas en Excel (.xlsx) y PDF.

Las filas y los totales salen siempre de la misma función (`datos`), a partir de las facturas que cumplen los filtros: así el Excel, el PDF y la
vista previa de totales nunca se contradicen, y los totales corresponden exclusivamente a lo filtrado.

Reglas de los montos: «facturado» y «pagado» cuentan solo facturas emitidas o pagadas (un borrador todavía no es una factura y una anulada ya no vale);
«pendiente» es el saldo de las emitidas. Cada moneda se suma por separado (nunca se mezclan RD$ y US$).
"""
import io
from decimal import Decimal
from xml.sax.saxutils import escape

from django.utils import timezone

from .models import SITUACIONES, redondear

MAX_FILAS_PDF = 2000          # un PDF más largo no se puede leer; para eso está el Excel
CUENTAN_EN_MONTOS = ('EMITIDA', 'PAGADA')
ENCABEZADOS = ['Número', 'NCF / e-CF', 'Cliente', 'RNC', 'Fecha de emisión', 'Vencimiento', 'Concepto', 'Proyecto / orden', 'Moneda', 'Subtotal',
               'Impuestos (ITBIS)', 'Total facturado', 'Monto pagado', 'Balance pendiente', 'Estado de pago', 'Días', 'Fecha de registro']


def _concepto(f):
    if f.titulo:
        return f.titulo
    primera = next(iter(f.lineas.all()), None)
    return primera.descripcion if primera else ''


def _dias_texto(f):
    d = f.dias_para_vencer
    if d is None:
        return ''
    return f"{-d} de atraso" if d < 0 else "vence hoy" if d == 0 else f"faltan {d}"


def datos(qs):
    """Las filas (una por factura) y el resumen de lo filtrado."""
    facturas = list(qs.select_related('cliente', 'proyecto', 'orden').prefetch_related('lineas'))
    filas = []
    por_moneda = {}
    conteo = {k: 0 for k in SITUACIONES}
    for f in facturas:
        sit = f.situacion
        conteo[sit] += 1
        filas.append({
            'numero': f.numero, 'ncf': f.ncf, 'cliente': f.cliente.nombre, 'rnc': f.cliente.rnc or '', 'fecha': f.fecha, 'vencimiento': f.vencimiento,
            'concepto': _concepto(f), 'proyecto': (f.orden.codigo if f.orden_id else (f.proyecto.nombre if f.proyecto_id else '')), 'moneda': f.moneda,
            'subtotal': f.subtotal, 'itbis': f.itbis, 'total': f.total, 'pagado': f.pagado, 'saldo': f.saldo,
            'estado': SITUACIONES[sit], 'dias': _dias_texto(f), 'registro': timezone.localtime(f.fecha_creacion).date() if f.fecha_creacion else None,
        })
        if f.estado in CUENTAN_EN_MONTOS:
            m = por_moneda.setdefault(f.moneda, {'moneda': f.moneda, 'subtotal': Decimal('0'), 'itbis': Decimal('0'), 'facturado': Decimal('0'),
                                                 'pagado': Decimal('0'), 'pendiente': Decimal('0'), 'cantidad': 0})
            m['subtotal'] += f.subtotal
            m['itbis'] += f.itbis
            m['facturado'] += f.total
            m['pagado'] += f.pagado
            m['pendiente'] += f.saldo
            m['cantidad'] += 1
    for m in por_moneda.values():
        for k in ('subtotal', 'itbis', 'facturado', 'pagado', 'pendiente'):
            m[k] = redondear(m[k])
    resumen = {
        'cantidad': len(facturas),
        'pendientes': conteo['PENDIENTE'] + conteo['POR_VENCER'] + conteo['VENCIDA'],   # emitidas con saldo por cobrar
        'por_vencer': conteo['POR_VENCER'], 'vencidas': conteo['VENCIDA'], 'pagadas': conteo['PAGADA'],
        'borradores': conteo['BORRADOR'], 'anuladas': conteo['ANULADA'],
        'monedas': sorted(por_moneda.values(), key=lambda m: m['moneda']),
    }
    return filas, resumen


def _fila_lista(r):
    return [r['numero'], r['ncf'], r['cliente'], r['rnc'], r['fecha'], r['vencimiento'], r['concepto'], r['proyecto'], r['moneda'], r['subtotal'],
            r['itbis'], r['total'], r['pagado'], r['saldo'], r['estado'], r['dias'], r['registro']]


# ------------------------------------------------------------------ Excel
def excel(filas, resumen, filtros, quien):
    """Libro .xlsx con la hoja «Resumen» (filtros, conteos y totales) y la hoja «Facturas» (una fila por factura). Todo texto se guarda como texto:
    un nombre que empiece con «=» no se interpreta nunca como fórmula."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    azul, gris = PatternFill('solid', fgColor='16336B'), PatternFill('solid', fgColor='EEF1F6')
    borde = Border(bottom=Side(style='thin', color='D6DBE4'))
    dinero = '#,##0.00'

    def poner(ws, fila, col, valor, formato=None, negrita=False, relleno=None, color=None, alinea=None):
        c = ws.cell(row=fila, column=col, value=valor)
        if isinstance(valor, str):
            c.data_type = 's'
        if formato:
            c.number_format = formato
        if negrita or color:
            c.font = Font(bold=negrita, color=color)
        if relleno:
            c.fill = relleno
        if alinea:
            c.alignment = Alignment(horizontal=alinea, vertical='top', wrap_text=True)
        return c

    wb = Workbook()
    ws = wb.active
    ws.title = 'Resumen'
    ws.column_dimensions['A'].width = 34
    for col in 'BCDEF':
        ws.column_dimensions[col].width = 20
    poner(ws, 1, 1, 'Reporte de facturas · AdZone Team', negrita=True).font = Font(bold=True, size=14, color='16336B')
    ahora = timezone.localtime()
    poner(ws, 2, 1, f"Generado el {ahora:%d/%m/%Y %H:%M} por {quien.get_full_name() or quien.username}")
    fila = 4
    poner(ws, fila, 1, 'Filtros aplicados', negrita=True, relleno=gris)
    poner(ws, fila, 2, '', relleno=gris)
    for etiqueta, valor in (filtros or [('Filtros', 'Sin filtros: todas las facturas')]):
        fila += 1
        poner(ws, fila, 1, etiqueta)
        poner(ws, fila, 2, valor)
    fila += 2
    poner(ws, fila, 1, 'Cantidad', negrita=True, relleno=gris)
    poner(ws, fila, 2, '', relleno=gris)
    for etiqueta, clave in (('Facturas consultadas', 'cantidad'), ('Pendientes de cobro', 'pendientes'), ('  de ellas, por vencer', 'por_vencer'),
                            ('  de ellas, vencidas', 'vencidas'), ('Pagadas', 'pagadas'), ('Borradores', 'borradores'), ('Anuladas', 'anuladas')):
        fila += 1
        poner(ws, fila, 1, etiqueta)
        poner(ws, fila, 2, resumen[clave], formato='0', alinea='right')
    fila += 2
    for j, t in enumerate(['Montos por moneda', 'Subtotal', 'Impuestos (ITBIS)', 'Total facturado', 'Monto pagado', 'Balance pendiente']):
        poner(ws, fila, j + 1, t, negrita=True, relleno=gris, alinea=None if j == 0 else 'right')
    for m in resumen['monedas']:
        fila += 1
        poner(ws, fila, 1, f"{m['moneda']} ({m['cantidad']} facturas)")
        for j, k in enumerate(('subtotal', 'itbis', 'facturado', 'pagado', 'pendiente')):
            poner(ws, fila, j + 2, m[k], formato=dinero)
    if not resumen['monedas']:
        fila += 1
        poner(ws, fila, 1, 'Sin facturas emitidas o pagadas en este reporte')
    fila += 2
    poner(ws, fila, 1, 'Los montos cuentan solo facturas emitidas o pagadas (no borradores ni anuladas). Cada moneda se suma por separado.').font = Font(italic=True, color='5B6577')

    ws2 = wb.create_sheet('Facturas')
    anchos = [16, 14, 30, 14, 14, 14, 36, 18, 9, 14, 14, 16, 14, 16, 14, 14, 14]
    for j, (t, a) in enumerate(zip(ENCABEZADOS, anchos), start=1):
        poner(ws2, 1, j, t, negrita=True, relleno=azul, color='FFFFFF', alinea='center')
        ws2.column_dimensions[get_column_letter(j)].width = a
    ws2.row_dimensions[1].height = 32
    for i, r in enumerate(filas, start=2):
        for j, v in enumerate(_fila_lista(r), start=1):
            c = poner(ws2, i, j, v)
            c.border = borde
            if j in (5, 6, 17):
                c.number_format = 'DD/MM/YYYY'
            elif 10 <= j <= 14:
                c.number_format = dinero
    ultima = len(filas) + 1
    ws2.freeze_panes = 'C2'
    if filas:
        ws2.auto_filter.ref = f"A1:{get_column_letter(len(ENCABEZADOS))}{ultima}"
    fila = ultima + 2
    for m in resumen['monedas']:
        poner(ws2, fila, 1, f"TOTAL {m['moneda']} (sin borradores ni anuladas)", negrita=True)
        for col, k in ((10, 'subtotal'), (11, 'itbis'), (12, 'facturado'), (13, 'pagado'), (14, 'pendiente')):
            poner(ws2, fila, col, m[k], formato=dinero, negrita=True)
        fila += 1
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ PDF
def _latin(texto):
    """El PDF usa la letra estándar (Helvetica): lo que no existe en ella se cambia por «?» en vez de salir como un cuadro negro."""
    return str(texto or '').encode('latin-1', 'replace').decode('latin-1')


def pdf(filas, resumen, filtros, quien):
    """PDF horizontal con los filtros, el resumen y la tabla de facturas (el encabezado se repite en cada página)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    azul = colors.HexColor('#16336B')
    hojas = getSampleStyleSheet()
    normal = ParagraphStyle('n', parent=hojas['Normal'], fontName='Helvetica', fontSize=6.8, leading=8.4)
    derecha = ParagraphStyle('d', parent=normal, alignment=2)
    titulo = ParagraphStyle('t', parent=hojas['Title'], fontName='Helvetica-Bold', fontSize=16, textColor=azul, alignment=0, spaceAfter=2)
    menor = ParagraphStyle('m', parent=normal, fontSize=8.5, leading=11, textColor=colors.HexColor('#5B6577'))
    p = lambda t, e=normal: Paragraph(escape(_latin(t)), e)   # noqa: E731
    dinero = lambda v: f"{v:,.2f}"   # noqa: E731

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=1.0 * cm, rightMargin=1.0 * cm, topMargin=1.2 * cm, bottomMargin=1.4 * cm,
                            title='Reporte de facturas', author='AdZone Team')
    ahora = timezone.localtime()

    def pie(canvas, d):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.HexColor('#5B6577'))
        canvas.drawString(1.0 * cm, 0.8 * cm, _latin(f"AdZone Team · Reporte de facturas · {ahora:%d/%m/%Y %H:%M}"))
        canvas.drawRightString(landscape(letter)[0] - 1.0 * cm, 0.8 * cm, f"Página {d.page}")
        canvas.restoreState()

    historia = [Paragraph('Reporte de facturas', titulo),
                p(f"Generado el {ahora:%d/%m/%Y %H:%M} por {quien.get_full_name() or quien.username}", menor)]
    for etiqueta, valor in (filtros or [('Filtros', 'Sin filtros: todas las facturas')]):
        historia.append(p(f"{etiqueta}: {valor}", menor))
    historia.append(Spacer(1, 8))

    conteos = [['Facturas consultadas', resumen['cantidad']], ['Pendientes de cobro', resumen['pendientes']], ['Vencidas', resumen['vencidas']],
               ['Pagadas', resumen['pagadas']]]
    t1 = Table([[p(a, normal), p(str(b), derecha)] for a, b in conteos], colWidths=[4.2 * cm, 1.6 * cm])
    montos = [[p('Moneda', normal), p('Facturado', derecha), p('Pagado', derecha), p('Pendiente', derecha)]]
    for m in resumen['monedas']:
        montos.append([p(f"{m['moneda']} ({m['cantidad']})"), p(dinero(m['facturado']), derecha), p(dinero(m['pagado']), derecha), p(dinero(m['pendiente']), derecha)])
    if not resumen['monedas']:
        montos.append([p('Sin facturas emitidas o pagadas'), '', '', ''])
    t2 = Table(montos, colWidths=[3.2 * cm, 3.4 * cm, 3.4 * cm, 3.4 * cm])
    for t in (t1, t2):
        t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#D6DBE4')), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEF1F6')),
                               ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
    resumen_tabla = Table([[t1, t2]], colWidths=[6.4 * cm, 14 * cm], hAlign='LEFT')
    resumen_tabla.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    historia += [resumen_tabla, p('Los montos cuentan solo facturas emitidas o pagadas. Cada moneda se suma por separado.', menor), Spacer(1, 8)]

    cab = ['Número', 'Cliente', 'Emisión', 'Vence', 'Concepto', 'Mon.', 'Subtotal', 'ITBIS', 'Total', 'Pagado', 'Balance', 'Estado', 'Registro']
    cuerpo = [[p(c, ParagraphStyle('h', parent=normal, textColor=colors.white, fontName='Helvetica-Bold')) for c in cab]]
    for r in filas:
        cuerpo.append([p(r['numero']), p(r['cliente']), p(f"{r['fecha']:%d/%m/%Y}" if r['fecha'] else ''), p(f"{r['vencimiento']:%d/%m/%Y}" if r['vencimiento'] else ''),
                       p(r['concepto']), p(r['moneda']), p(dinero(r['subtotal']), derecha), p(dinero(r['itbis']), derecha), p(dinero(r['total']), derecha),
                       p(dinero(r['pagado']), derecha), p(dinero(r['saldo']), derecha),
                       p(r['estado'] + (f" ({r['dias']})" if r['dias'] else '')), p(f"{r['registro']:%d/%m/%Y}" if r['registro'] else '')])
    if not filas:
        cuerpo.append([p('Ninguna factura cumple estos filtros.')] + [''] * (len(cab) - 1))
    ancho = [2.5, 2.6, 1.75, 1.75, 2.6, 1.0, 2.0, 1.5, 2.0, 2.0, 2.0, 2.1, 1.75]   # suman 25.5 cm: lo que cabe en una hoja carta horizontal
    tabla = Table(cuerpo, colWidths=[a * cm for a in ancho], repeatRows=1)
    estilo = [('BACKGROUND', (0, 0), (-1, 0), azul), ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#D6DBE4')), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
              ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2), ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3)]
    for i in range(2, len(cuerpo), 2):
        estilo.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F6F8FB')))
    tabla.setStyle(TableStyle(estilo))
    historia.append(tabla)
    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()
