"""Organigrama estructural y nominal: matriz de reporte y coordinación, revisión de coherencia, registro de cambios y versiones."""
from django.db import transaction
from django.db.models import Max, Prefetch
from django.utils import timezone

from .models import CambioOrganigrama, PerfilUsuario, PuestoDeTrabajo, VersionOrganigrama

CAMPOS = {'nombre': 'Nombre del cargo', 'unidad': 'Unidad', 'departamento': 'Departamento', 'supervisor': 'Superior directo',
          'coordina_con': 'Coordinación operativa', 'alta': 'Puesto nuevo', 'baja': 'Puesto eliminado'}


def foto(puesto):
    """Lo que interesa del puesto para el registro de cambios."""
    return {
        'nombre': puesto.nombre, 'unidad': puesto.unidad or '', 'departamento': puesto.departamento.nombre if puesto.departamento_id else '',
        'supervisor': puesto.supervisor.nombre if puesto.supervisor_id else '(ninguno: máximo nivel)',
        'coordina_con': ', '.join(sorted(p.nombre for p in puesto.coordina_con.all())) if puesto.pk else '',
    }


def registrar(usuario, puesto, antes, despues):
    for campo, valor in despues.items():
        if antes.get(campo, '') != valor:
            CambioOrganigrama.objects.create(usuario=usuario, puesto=puesto, puesto_nombre=despues['nombre'], campo=campo,
                                             antes=str(antes.get(campo, ''))[:1000], despues=str(valor)[:1000])


def _puestos():
    return list(PuestoDeTrabajo.objects.select_related('departamento', 'supervisor').prefetch_related(
        Prefetch('perfiles_usuarios', queryset=PerfilUsuario.objects.select_related('user').prefetch_related('puestos_adicionales')),
        Prefetch('perfiles_adicionales', queryset=PerfilUsuario.objects.select_related('user')),
        'coordina_con', 'coordinado_por'))


def ocupantes(p):
    titulares = [pf for pf in p.perfiles_usuarios.all() if pf.user.is_active]
    adicionales = [pf for pf in p.perfiles_adicionales.all() if pf.user.is_active]
    return titulares, adicionales


def situacion(p):
    """Vacante (nadie lo ocupa), compartido (lo cubre alguien con otro puesto, o su titular también ocupa otro) u ocupado."""
    titulares, adicionales = ocupantes(p)
    if not titulares and not adicionales:
        return 'VACANTE'
    if adicionales or any(pf.puestos_adicionales.all() for pf in titulares):
        return 'COMPARTIDO'
    return 'OCUPADO'


def _nombre(u):
    return u.get_full_name() or u.username


def matriz():
    puestos = _puestos()
    por_id = {p.id: p for p in puestos}
    filas = []
    for p in puestos:
        titulares, adicionales = ocupantes(p)
        cadena, sup, vistos = [], p.supervisor_id, set()
        while sup and sup in por_id and sup not in vistos:   # vía de escalamiento: superior directo y hacia arriba
            vistos.add(sup)
            s = por_id[sup]
            gente = [_nombre(pf.user) for pf in s.perfiles_usuarios.all() if pf.user.is_active]
            cadena.append(f"{s.nombre}{f' ({gente[0]})' if gente else ' (vacante)'}")
            sup = s.supervisor_id
        filas.append({
            'id': p.id, 'puesto': p.nombre, 'unidad': p.unidad, 'departamento': p.departamento.nombre if p.departamento_id else '',
            'superior': p.supervisor.nombre if p.supervisor_id else None, 'superior_id': p.supervisor_id,
            'superior_unidad': p.supervisor.unidad if p.supervisor_id else None,
            'coordina_con': sorted(x.nombre for x in p.coordina_con.all()),
            'coordinado_por': sorted(x.nombre for x in p.coordinado_por.all()),
            'personas': [_nombre(pf.user) for pf in titulares], 'cubre': [_nombre(pf.user) for pf in adicionales],
            'situacion': situacion(p), 'escalamiento': cadena,
        })
    orden = _orden_jerarquico(puestos)
    filas.sort(key=lambda f: orden.get(f['id'], 9999))
    return filas


def _orden_jerarquico(puestos):
    hijos = {}
    for p in puestos:
        hijos.setdefault(p.supervisor_id if p.supervisor_id in {x.id for x in puestos} else None, []).append(p)
    orden, n = {}, 0
    pila = sorted(hijos.get(None, []), key=lambda x: x.nombre, reverse=True)
    while pila:
        p = pila.pop()
        if p.id in orden:
            continue
        orden[p.id] = n
        n += 1
        pila.extend(sorted(hijos.get(p.id, []), key=lambda x: x.nombre, reverse=True))
    return orden


def revision(filas):
    """Criterios de aceptación que se pueden comprobar solos."""
    avisos = []
    raices = [f for f in filas if not f['superior']]
    if len(raices) > 1:
        avisos.append({'tipo': 'superior', 'texto': f'Hay {len(raices)} puestos sin superior directo; solo el órgano de máximo nivel debería no tenerlo.',
                       'puestos': [f['puesto'] for f in raices]})
    sin_unidad = [f['puesto'] for f in filas if not f['unidad']]
    if sin_unidad:
        avisos.append({'tipo': 'unidad', 'texto': f'{len(sin_unidad)} puesto(s) sin unidad del organigrama estructural.', 'puestos': sin_unidad})
    # Una unidad debe tener una sola dependencia: si sus puestos reportan a unidades distintas, no coinciden ambas versiones
    deps = {}
    for f in filas:
        if f['unidad']:
            deps.setdefault(f['unidad'], set()).add(f['superior_unidad'] or f['superior'] or '—')
    choque = [u for u, d in deps.items() if len(d - {u}) > 1]
    if choque:
        avisos.append({'tipo': 'dependencia', 'texto': 'Unidades cuyos puestos reportan a unidades distintas (revisa que el estructural y el nominal coincidan).',
                       'puestos': choque})
    return avisos


def estado_version():
    v = VersionOrganigrama.objects.select_related('aprobada_por').first()
    pendientes = CambioOrganigrama.objects.filter(version__isnull=True).count()
    return {'version': {'numero': v.numero, 'vigente_desde': v.vigente_desde, 'aprobada_por': _nombre(v.aprobada_por) if v.aprobada_por else None,
                        'aprobada_en': v.aprobada_en, 'notas': v.notas} if v else None,
            'cambios_pendientes': pendientes}


@transaction.atomic
def aprobar(usuario, vigente_desde, notas=''):
    numero = (VersionOrganigrama.objects.aggregate(m=Max('numero'))['m'] or 0) + 1
    v = VersionOrganigrama.objects.create(numero=numero, vigente_desde=vigente_desde or timezone.localdate(), notas=notas or '',
                                          aprobada_por=usuario, matriz=matriz())
    CambioOrganigrama.objects.filter(version__isnull=True).update(version=v)
    return v


def excel(filas, version):
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = 'Matriz de reporte'
    titulo = f"Matriz de reporte y coordinación — ADZONE · {'versión ' + str(version['numero']) + ', vigente desde ' + version['vigente_desde'].strftime('%d/%m/%Y') if version else 'borrador (sin versión aprobada)'}"
    ws.append([titulo])
    ws['A1'].font = Font(bold=True, size=13)
    ws.append([])
    cab = ['Unidad', 'Cargo (puesto)', 'Departamento', 'Superior directo', 'Coordinación operativa con', 'Coordinan con este',
           'Personas', 'Cubierto por (puesto adicional)', 'Situación', 'Vía de escalamiento']
    ws.append(cab)
    for c in ws[3]:
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='224B9A')
    for f in filas:
        ws.append([f['unidad'], f['puesto'], f['departamento'], f['superior'] or '— (máximo nivel)', ', '.join(f['coordina_con']),
                   ', '.join(f['coordinado_por']), ', '.join(f['personas']), ', '.join(f['cubre']),
                   {'VACANTE': 'Vacante', 'COMPARTIDO': 'Compartido', 'OCUPADO': 'Ocupado'}[f['situacion']], ' → '.join(f['escalamiento'])])
    for col, ancho in zip('ABCDEFGHIJ', (30, 36, 18, 34, 34, 30, 30, 26, 12, 70)):
        ws.column_dimensions[col].width = ancho
    for fila in ws.iter_rows(min_row=4):
        for c in fila:
            c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.freeze_panes = 'A4'
    cambios = wb.create_sheet('Registro de cambios')
    cambios.append(['Fecha', 'Puesto', 'Qué cambió', 'Antes', 'Después', 'Quién', 'Versión'])
    for c in cambios[1]:
        c.font = Font(bold=True)
    for c in CambioOrganigrama.objects.select_related('usuario', 'version')[:2000]:
        cambios.append([timezone.localtime(c.fecha).strftime('%d/%m/%Y %H:%M'), c.puesto_nombre, CAMPOS.get(c.campo, c.campo), c.antes, c.despues,
                        _nombre(c.usuario) if c.usuario else '', c.version.numero if c.version else 'Pendiente'])
    for col, ancho in zip('ABCDEFG', (17, 34, 22, 40, 40, 24, 10)):
        cambios.column_dimensions[col].width = ancho
    b = BytesIO()
    wb.save(b)
    return b.getvalue()
