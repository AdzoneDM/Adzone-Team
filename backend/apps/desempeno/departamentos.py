"""
Espacio de cada departamento: resumen (qué hace, objetivos, estructura), KPIs del mes o del trimestre, personal
(cargo, supervisor, funciones y KPIs), políticas, procedimientos, documentación y seguimiento.

Quién ve qué (mínimo privilegio), por departamento:
- COMPLETO: Dirección y Gestión del Talento → todos los departamentos, toda su gente.
- EQUIPO: quien tiene gente a cargo en el área → su gente con KPIs y seguimiento.
- MIEMBRO: quien trabaja en el área (puesto principal o adicional) → la información del área, sus compañeros
  (cargo, funciones, supervisor), políticas, procedimientos y documentos; de KPIs y seguimiento, solo lo suyo.
Los salarios solo con «Salarios»; los KPIs que salen de la computadora solo con «Ver el monitoreo».
"""
from calendar import monthrange
from collections import defaultdict
from datetime import date

from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import exceptions, status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.models import Departamento, DocumentoArea
from apps.core.permisos import tiene
from apps.kpis.models import KPIAsignado
from .models import ResultadoKPI, Tarea
from .permisos import equipo_gestionable
from .puntaje import calcular_ranking, kpis_del_mes

PC_FUENTES = ('ACTIVIDAD_PC', 'PRODUCTIVIDAD_PC')
MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
COMPLETO, EQUIPO, MIEMBRO = 'completo', 'equipo', 'miembro'
EXTENSIONES = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.png', '.jpg', '.jpeg', '.txt', '.csv', '.zip')


def _nombre(u):
    return (u.get_full_name() or u.username) if u else None


def _todo(user):
    return tiene(user, 'direccion') or tiene(user, 'talento.rrhh')


def _mis_deptos(user):
    """Departamentos donde trabaja (puesto principal y puestos adicionales)."""
    per = getattr(user, 'perfil', None)
    ids = set()
    if per and per.puesto_trabajo_id:
        ids.add(per.puesto_trabajo.departamento_id)
        adicionales = getattr(per, 'puestos_adicionales', None)
        if adicionales is not None:
            ids.update(adicionales.values_list('departamento_id', flat=True))
    return ids


def _equipo(user):
    if tiene(user, 'equipo.ver'):
        return User.objects.filter(pk__in=equipo_gestionable(user, 'equipo.ver').values('pk'), is_active=True)
    return User.objects.none()


def departamentos_visibles(user):
    if _todo(user):
        return Departamento.objects.all().order_by('orden', 'nombre')
    ids = set(_equipo(user).values_list('perfil__puesto_trabajo__departamento', flat=True)) | _mis_deptos(user)
    return Departamento.objects.filter(pk__in=ids).order_by('orden', 'nombre')


def nivel(user, depto):
    if _todo(user):
        return COMPLETO
    if _equipo(user).filter(perfil__puesto_trabajo__departamento=depto).exists():
        return EQUIPO
    if depto.pk in _mis_deptos(user):
        return MIEMBRO
    return None


def _gente(depto):
    """Quien trabaja en el área: puesto principal en ella, o un puesto adicional de ella."""
    q = Q(perfil__puesto_trabajo__departamento=depto)
    try:
        q |= Q(perfil__puestos_adicionales__departamento=depto)
    except Exception:  # noqa: BLE001 (sin puestos adicionales en esta versión)
        pass
    return (User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=False).filter(q).distinct()
            .select_related('perfil__puesto_trabajo__supervisor').order_by('perfil__puesto_trabajo__nombre', 'first_name'))


def puede_editar(user, depto):
    """Información, procedimientos y documentos del área: Dirección, Gestión del Talento o el encargado del área."""
    if _todo(user):
        return True
    per = getattr(user, 'perfil', None)
    return bool(per and per.puesto_trabajo_id and per.puesto_trabajo.departamento_id == depto.pk
                and per.puesto_trabajo.subordinados.exists() and _es_tope(per.puesto_trabajo))


def _es_tope(puesto):
    return puesto.supervisor_id is None or puesto.supervisor.departamento_id != puesto.departamento_id


# ------------------------------------------------------------------ KPIs
def _periodos(anio, mes, vista):
    if vista == 'trimestral':
        inicio = (mes - 1) // 3 * 3 + 1
        meses = [date(anio, m, 1) for m in range(inicio, inicio + 3)]
    else:
        meses = [date(anio, mes, 1)]
    hoy = timezone.localdate()
    return [m for m in meses if m <= hoy.replace(day=1)] or meses[:1]


def _estado(cumpl, umbral=80):
    return 'SIN_DATO' if cumpl is None else ('CUMPLE' if cumpl >= 100 else ('CERCA' if cumpl >= umbral else 'BAJO'))


def _kpis_persona(u, meses, ve_pc):
    """Todos los KPIs del puesto (también los que aún no tienen dato), con el promedio de los meses del periodo."""
    asignados = list(KPIAsignado.objects.filter(puesto_trabajo=u.perfil.puesto_trabajo, activo=True)
                     .select_related('plantilla_kpi').order_by('plantilla_kpi__nombre'))
    por_kpi = defaultdict(list)
    for m in meses:
        fin = date(m.year, m.month, monthrange(m.year, m.month)[1])
        manuales = ResultadoKPI.objects.filter(colaborador=u, periodo=m).select_related('kpi_asignado__plantilla_kpi')
        for f in kpis_del_mes(u, m, fin, manuales):
            por_kpi[f['kpi_asignado_id']].append(f)
    salida = []
    for k in asignados:
        p = k.plantilla_kpi
        datos = por_kpi.get(k.pk, [])
        oculto = (p.fuente in PC_FUENTES and not k.es_entrada_manual) and not ve_pc
        con_valor = [d for d in datos if d.get('valor') is not None]
        cumplimientos = [d['cumplimiento'] for d in datos if d.get('cumplimiento') is not None]
        valor = round(sum(d['valor'] for d in con_valor) / len(con_valor), 2) if con_valor else None
        meta = next((d.get('meta') for d in datos if d.get('meta') is not None), None)
        if meta is None and k.meta_numerica is not None:
            meta = float(k.meta_numerica)
        cumpl = round(sum(cumplimientos) / len(cumplimientos), 1) if cumplimientos else None
        salida.append({
            'id': k.pk, 'plantilla': p.pk, 'nombre': p.nombre, 'unidad': p.unidad_medida, 'menor_es_mejor': p.menor_es_mejor,
            'meta': meta, 'valor': None if oculto else valor, 'cumplimiento': None if oculto else cumpl,
            'estado': 'RESERVADO' if oculto else _estado(cumpl, float(k.umbral_alerta)), 'manual': k.es_entrada_manual,
            'ponderacion': float(k.ponderacion), 'formula': p.formula, 'fuente_datos': p.fuente_datos,
        })
    return salida


def _resumen_kpis(personas):
    """KPIs del departamento: cada KPI juntando a las personas que lo tienen (promedio de cumplimiento)."""
    grupos = {}
    for per in personas:
        for k in per.get('kpis') or []:
            g = grupos.setdefault(k['plantilla'], {'nombre': k['nombre'], 'unidad': k['unidad'], 'metas': set(), 'valores': [],
                                                  'cumplimientos': [], 'personas': 0, 'reservado': False})
            g['personas'] += 1
            if k['meta'] is not None:
                g['metas'].add(k['meta'])
            g['reservado'] |= k['estado'] == 'RESERVADO'
            if k['valor'] is not None:
                g['valores'].append(k['valor'])
            if k['cumplimiento'] is not None:
                g['cumplimientos'].append(k['cumplimiento'])
    salida = []
    for plantilla, g in grupos.items():
        cumpl = round(sum(g['cumplimientos']) / len(g['cumplimientos']), 1) if g['cumplimientos'] else None
        salida.append({
            'plantilla': plantilla, 'nombre': g['nombre'], 'unidad': g['unidad'],
            'meta': next(iter(g['metas'])) if len(g['metas']) == 1 else None,
            'valor': round(sum(g['valores']) / len(g['valores']), 2) if g['valores'] else None,
            'cumplimiento': cumpl, 'personas': g['personas'], 'con_dato': len(g['cumplimientos']),
            'estado': 'RESERVADO' if g['reservado'] and cumpl is None else _estado(cumpl),
        })
    return sorted(salida, key=lambda x: x['nombre'])


# ------------------------------------------------------------------ Estructura, seguimiento, políticas, documentos
def _estructura(gente):
    puestos = {u.perfil.puesto_trabajo_id for u in gente}
    encargados, supervisores, personal = [], [], []
    for u in gente:
        p = u.perfil.puesto_trabajo
        fila = {'id': u.pk, 'nombre': _nombre(u), 'cargo': p.nombre}
        if _es_tope(p) and p.subordinados.exists():
            encargados.append(fila)
        elif p.subordinados.filter(pk__in=puestos).exists():
            supervisores.append(fila)
        else:
            personal.append(fila)
    return {'encargados': encargados, 'supervisores': supervisores, 'personal': personal}


def _seguimiento(u, meses):
    desde = meses[0]
    ultimo = meses[-1]
    hasta = date(ultimo.year, ultimo.month, monthrange(ultimo.year, ultimo.month)[1])
    hoy = timezone.localdate()
    mias = Tarea.objects.filter(Q(colaborador=u) | Q(companeros=u)).exclude(estado='CANCELADA').distinct()
    abiertas = mias.filter(estado__in=('PENDIENTE', 'EN_PROGRESO', 'EN_REVISION'))
    validadas = list(mias.filter(estado='COMPLETADA', fecha_completada__range=(desde, hasta)).only('fecha_completada', 'fecha_limite', 'estado'))
    a_tiempo = sum(1 for t in validadas if t.a_tiempo)
    from apps.talento.models import Evaluacion, PlanMejora
    evals = Evaluacion.objects.filter(evaluado=u, ciclo__desde__lte=hasta, ciclo__hasta__gte=desde)
    # La última evaluación cerrada o enviada de su supervisor (la que cuenta), y si tiene un plan de mejora en curso
    ultima = (Evaluacion.objects.filter(evaluado=u, tipo='SUPERVISOR', estado__in=('ENVIADA', 'EN_REVISION', 'CERRADA'))
              .select_related('ciclo').order_by('-ciclo__hasta', '-enviada').first())
    plan = PlanMejora.objects.filter(colaborador=u, estado='ABIERTO').order_by('-inicio').first()
    return {
        'ultima_evaluacion': {'ciclo': ultima.ciclo.nombre, 'promedio': ultima.promedio, 'estado': ultima.get_estado_display()} if ultima else None,
        'plan_mejora': {'id': plan.pk, 'inicio': plan.inicio, 'motivo': plan.motivo[:120]} if plan else None,
        'abiertas': abiertas.count(), 'vencidas': abiertas.filter(fecha_limite__lt=hoy).count(),
        'por_validar': abiertas.filter(estado='EN_REVISION').count(), 'validadas': len(validadas),
        'a_tiempo_pct': round(a_tiempo / len(validadas) * 100) if validadas else None,
        'evaluaciones': {'total': evals.count(), 'pendientes': evals.filter(estado='PENDIENTE').count()},
    }


def _politicas(depto, gente, ve_todo, yo):
    from apps.talento.models import AceptacionPolitica, Politica
    qs = (Politica.objects.filter(activa=True, borrador=False)
          .filter(Q(para_todos=True) | Q(departamentos=depto) | Q(puestos__departamento=depto)).distinct().order_by('para_todos', 'titulo'))
    ids = {u.pk: u for u in gente}
    salida = []
    for p in qs:
        if p.para_todos:
            aplican = set(ids)
        else:
            deptos, puestos = set(p.departamentos.values_list('pk', flat=True)), set(p.puestos.values_list('pk', flat=True))
            aplican = {i for i, u in ids.items() if u.perfil.puesto_trabajo_id in puestos or u.perfil.puesto_trabajo.departamento_id in deptos}
        aceptaron = set(AceptacionPolitica.objects.filter(politica=p, version=p.version, usuario_id__in=aplican).values_list('usuario_id', flat=True))
        alcance = ('Toda la empresa' if p.para_todos else
                   ', '.join(sorted({pu.nombre for pu in p.puestos.all() if pu.departamento_id == depto.pk})) if not p.departamentos.filter(pk=depto.pk).exists()
                   else 'Todo el departamento')
        fila = {'id': p.pk, 'codigo': p.codigo, 'responsable': p.responsable, 'aplica_a': alcance or 'Puestos del área',
                'titulo': p.titulo, 'categoria': p.get_categoria_display(), 'resumen': p.resumen, 'version': p.version,
                'vigente_desde': p.vigente_desde, 'alcance': 'Toda la empresa' if p.para_todos else 'Este departamento',
                'requiere_aceptacion': p.requiere_aceptacion, 'me_aplica': yo.pk in aplican, 'la_acepte': yo.pk in aceptaron}
        if ve_todo:
            fila.update(aplican=len(aplican), aceptaron=len(aceptaron),
                        pendientes=sorted(_nombre(ids[i]) for i in aplican - aceptaron) if p.requiere_aceptacion else [])
        salida.append(fila)
    return salida


PREFIJO = {'PROCEDIMIENTO': 'PRO', 'MANUAL': 'MAN', 'FORMULARIO': 'FOR', 'REPORTE': 'REP', 'OTRO': 'DOC'}


def _doc(d):
    return {'id': d.pk, 'codigo': f"{PREFIJO.get(d.tipo, 'DOC')}-{d.pk:03d}", 'tipo': d.tipo, 'tipo_nombre': d.get_tipo_display(), 'titulo': d.titulo, 'resumen': d.resumen,
            'contenido': d.contenido, 'archivo': bool(d.archivo), 'nombre_archivo': d.nombre_archivo, 'solo_encargados': d.solo_encargados,
            'version': d.version, 'actualizado': d.actualizado, 'actualizado_por': _nombre(d.actualizado_por)}


# ------------------------------------------------------------------ Vistas
@api_view(['GET'])
def departamentos_view(request):
    deptos = list(departamentos_visibles(request.user))
    if not deptos:
        raise exceptions.PermissionDenied("Todavía no tienes un departamento asignado.")
    return Response([{'id': d.pk, 'nombre': d.nombre, 'color': d.color, 'color_fondo': d.color_fondo, 'nivel': nivel(request.user, d)}
                     for d in deptos])


@api_view(['GET', 'PATCH'])
def departamento_view(request, pk):
    depto = get_object_or_404(departamentos_visibles(request.user), pk=pk)
    yo = request.user
    acceso = nivel(yo, depto)
    if acceso is None:
        raise exceptions.NotFound()
    if request.method == 'PATCH':
        if not puede_editar(yo, depto):
            raise exceptions.PermissionDenied("La información del área la cambia la Dirección o el encargado del área.")
        for campo, largo in (('descripcion', 255), ('objetivos', 4000)):
            if campo in request.data:
                setattr(depto, campo, str(request.data.get(campo) or '')[:largo])
        depto.save(update_fields=['descripcion', 'objetivos', 'fecha_modificacion'])
        return Response({'ok': True})

    hoy = timezone.localdate()
    try:
        anio = int(request.query_params.get('anio', hoy.year))
        mes = int(request.query_params.get('mes', hoy.month))
        assert 2020 <= anio <= hoy.year + 1 and 1 <= mes <= 12
    except (ValueError, AssertionError):
        raise exceptions.ValidationError('Periodo no válido.')
    vista = 'trimestral' if request.query_params.get('vista') == 'trimestral' else 'mensual'
    meses = _periodos(anio, mes, vista)
    ve_pc, ve_salario = tiene(yo, 'monitoreo.ver'), tiene(yo, 'personal.salarios')

    gente = list(_gente(depto))
    if acceso == COMPLETO:
        con_detalle = {u.pk for u in gente}
    elif acceso == EQUIPO:
        con_detalle = set(_equipo(yo).values_list('pk', flat=True)) | {yo.pk}
    else:
        con_detalle = {yo.pk}
    puntajes = defaultdict(list)
    if con_detalle:
        for m in meses:
            for f in calcular_ranking(m):
                if f['colaborador_id'] in con_detalle and f.get('puntaje_total') is not None:
                    puntajes[f['colaborador_id']].append(f['puntaje_total'])
    nombres_puesto = defaultdict(list)
    for u in gente:
        nombres_puesto[u.perfil.puesto_trabajo_id].append(_nombre(u))

    personas = []
    for u in gente:
        per, puesto = u.perfil, u.perfil.puesto_trabajo
        fila = {
            'id': u.pk, 'nombre': _nombre(u), 'cargo': puesto.nombre, 'soy_yo': u.pk == yo.pk,
            'supervisor': ', '.join(nombres_puesto.get(puesto.supervisor_id, [])) or (puesto.supervisor.nombre if puesto.supervisor_id else None),
            'funciones': [f.strip(' -•\t') for f in (puesto.funciones_principales or '').splitlines() if f.strip(' -•\t')][:12],
            'objetivo_puesto': puesto.objetivo, 'detalle': u.pk in con_detalle,
        }
        if u.pk in con_detalle:
            pts = puntajes.get(u.pk)
            fila.update(puntaje=round(sum(pts) / len(pts), 1) if pts else None, kpis=_kpis_persona(u, meses, ve_pc or u.pk == yo.pk),
                        seguimiento=_seguimiento(u, meses),
                        salario=float(per.salario_mensual) if ve_salario and per.salario_mensual else None)
        personas.append(fila)

    detalle = [p for p in personas if p['detalle']]
    kpis = _resumen_kpis(detalle)
    medidos = [k for k in kpis if k['cumplimiento'] is not None]
    rendimiento = round(sum(min(k['cumplimiento'], 100) for k in medidos) / len(medidos), 1) if medidos else None
    cumplidos = sum(1 for k in medidos if k['cumplimiento'] >= 100)
    quien = depto.nombre if acceso != MIEMBRO else 'tu trabajo en ' + depto.nombre
    nombre_periodo = (f"el {['primer', 'segundo', 'tercer', 'cuarto'][(meses[0].month - 1) // 3]} trimestre" if vista == 'trimestral'
                      else MESES[meses[0].month - 1])
    if rendimiento is None:
        texto = f"En {nombre_periodo}, {quien} todavía no tiene KPIs medidos."
    else:
        estado = ('cumple sus metas principales' if cumplidos == len(medidos) else
                  f"cumple {cumplidos} de {len(medidos)} KPIs medidos" if cumplidos else "aún no alcanza las metas principales")
        texto = f"En {nombre_periodo}, {quien} tiene un rendimiento de {rendimiento:g}% y {estado}."
        sin = sum(1 for k in kpis if k['estado'] == 'SIN_DATO')
        if sin:
            texto += f" {sin} KPI(s) sin dato todavía."
    docs = DocumentoArea.objects.filter(departamento=depto).select_related('actualizado_por')
    if acceso == MIEMBRO:
        docs = docs.filter(solo_encargados=False)
    seg = [p for p in detalle]
    return Response({
        'departamento': {'id': depto.pk, 'nombre': depto.nombre, 'descripcion': depto.descripcion, 'color': depto.color,
                         'color_fondo': depto.color_fondo, 'objetivos': [o.strip(' -•\t') for o in depto.objetivos.splitlines() if o.strip(' -•\t')]},
        'nivel': acceso, 'anio': anio, 'mes': mes, 'vista': vista, 'meses': [m.isoformat() for m in meses],
        'estructura': _estructura(gente),
        'resumen': {'rendimiento': rendimiento, 'cumplidos': cumplidos, 'medidos': len(medidos), 'kpis': len(kpis),
                    'personas': len(gente), 'texto': texto},
        'kpis': kpis, 'personas': personas,
        'seguimiento': {
            'abiertas': sum(p['seguimiento']['abiertas'] for p in seg), 'vencidas': sum(p['seguimiento']['vencidas'] for p in seg),
            'por_validar': sum(p['seguimiento']['por_validar'] for p in seg),
            'evaluaciones_pendientes': sum(p['seguimiento']['evaluaciones']['pendientes'] for p in seg),
        },
        'politicas': _politicas(depto, gente, acceso != MIEMBRO, yo),
        'documentos': [_doc(d) for d in docs],
        'puede': {'ingresar': tiene(yo, 'direccion'), 'metas': tiene(yo, 'direccion'), 'integrante': tiene(yo, 'personal.usuarios'),
                  'politicas': tiene(yo, 'talento.rrhh'), 'editar': puede_editar(yo, depto)},
    })


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def documentos_view(request, pk):
    depto = get_object_or_404(Departamento, pk=pk)
    if not puede_editar(request.user, depto):
        raise exceptions.PermissionDenied("Los procedimientos y documentos del área los publica la Dirección o el encargado del área.")
    return Response(_guardar_doc(request, DocumentoArea(departamento=depto)), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def documento_view(request, pk):
    d = get_object_or_404(DocumentoArea.objects.select_related('departamento'), pk=pk)
    acceso = nivel(request.user, d.departamento)
    if acceso is None or (d.solo_encargados and acceso == MIEMBRO):
        raise exceptions.NotFound()
    if request.method == 'GET':
        if not d.archivo:
            raise exceptions.NotFound()
        from apps.core.archivos import entregar
        import mimetypes
        try:
            f = d.archivo.open('rb')
        except (FileNotFoundError, ValueError):
            raise exceptions.NotFound()
        r = entregar(f, d.nombre_archivo or d.titulo, mimetypes.guess_type(d.archivo.name)[0] or 'application/octet-stream')
        r['Cache-Control'] = 'private, no-store'
        return r
    if not puede_editar(request.user, d.departamento):
        raise exceptions.PermissionDenied("Los documentos del área los cambia la Dirección o el encargado del área.")
    if request.method == 'DELETE':
        d.archivo.delete(save=False) if d.archivo else None
        d.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    d.version += 1
    return Response(_guardar_doc(request, d))


def _guardar_doc(request, d):
    datos = request.data
    titulo = str(datos.get('titulo', d.titulo) or '').strip()[:150]
    if len(titulo) < 3:
        raise exceptions.ValidationError({'titulo': 'Escribe un título.'})
    tipo = datos.get('tipo', d.tipo)
    if tipo not in dict(DocumentoArea.TIPOS):
        raise exceptions.ValidationError({'tipo': 'Tipo no válido.'})
    d.titulo, d.tipo = titulo, tipo
    d.resumen = str(datos.get('resumen', d.resumen) or '')[:300]
    d.contenido = str(datos.get('contenido', d.contenido) or '')[:20000]
    if 'solo_encargados' in datos:
        d.solo_encargados = str(datos.get('solo_encargados')).lower() in ('true', '1', 'on')
    archivo = request.FILES.get('archivo')
    if archivo:
        import os
        if os.path.splitext(archivo.name)[1].lower() not in EXTENSIONES:
            raise exceptions.ValidationError({'archivo': 'Sube PDF, Word, Excel, PowerPoint, imagen, texto o ZIP.'})
        if archivo.size > 20 * 1024 * 1024:
            raise exceptions.ValidationError({'archivo': 'Máximo 20 MB.'})
        if d.archivo:
            d.archivo.delete(save=False)
        d.archivo, d.nombre_archivo = archivo, archivo.name[:200]
    if not d.contenido.strip() and not d.archivo:
        raise exceptions.ValidationError({'contenido': 'Escribe los pasos o sube un archivo.'})
    d.actualizado_por = request.user
    d.save()
    return _doc(d)
