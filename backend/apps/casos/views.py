from datetime import date

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.archivos import entregar, tipo_por_extension
from apps.core.models import Departamento

from . import permisos, servicios
from .models import Caso, EvidenciaCaso


def _n(u):
    return (u.get_full_name() or u.username) if u else None


def _fecha(v):
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        raise ValueError('Fecha no válida.') from None


def _ficha(c, hoy):
    return {
        'id': c.id, 'codigo': c.codigo, 'titulo': c.titulo, 'tipo': c.tipo, 'tipo_texto': c.get_tipo_display(),
        'categoria': c.categoria, 'categoria_texto': c.get_categoria_display(), 'impacto': c.impacto,
        'prioridad': c.prioridad, 'estado': c.estado, 'estado_texto': c.get_estado_display(),
        'area_origen': c.area_origen.nombre if c.area_origen_id else None,
        'area_asignada': c.area_asignada.nombre if c.area_asignada_id else None, 'area_asignada_id': c.area_asignada_id,
        'responsable': _n(c.responsable), 'responsable_id': c.responsable_id, 'responsable_confirmado': c.responsable_confirmado,
        'reportado_por': _n(c.reportado_por), 'recibido': c.recibido, 'proxima_revision': c.proxima_revision,
        'fecha_estimada': c.fecha_estimada, 'bloqueado': c.bloqueado, 'motivo_bloqueo': c.motivo_bloqueo,
        'vencido': c.vencido(hoy), 'cerrado': c.cerrado, 'reaperturas': c.reaperturas,
    }


def _detalle(request, c):
    u, hoy = request.user, timezone.localdate()
    ops = permisos.es_operaciones(u)
    abierto = c.abierto
    atiende = permisos.puede_atender(u, c)
    d = _ficha(c, hoy) | {
        'descripcion': c.descripcion, 'impacto_texto': c.get_impacto_display(), 'referencia': c.referencia,
        'resultado': c.resultado, 'validado_por': _n(c.validado_por), 'validacion': c.validacion,
        'evidencias': [{'id': e.id, 'nombre': e.nombre, 'tamano': e.tamano, 'subido_por': _n(e.subido_por), 'fecha': e.fecha,
                        'es_imagen': e.nombre.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))} for e in c.evidencias.all()],
        'movimientos': [{'id': m.id, 'tipo': m.tipo, 'tipo_texto': m.get_tipo_display(), 'usuario': _n(m.usuario), 'nota': m.nota,
                         'datos': m.datos, 'fecha': m.fecha} for m in c.movimientos.select_related('usuario')],
        'acciones': {
            'clasificar': ops and abierto, 'unir': ops and abierto, 'escalar': ops and abierto and bool(c.area_asignada_id),
            'designar': abierto and bool(c.area_asignada_id) and (ops or permisos.gestiona_area(u, c)),
            'confirmar': abierto and bool(c.responsable_id) and not c.responsable_confirmado and (c.responsable_id == u.pk or permisos.gestiona_area(u, c)),
            'atender': abierto and atiende and c.estado != 'PENDIENTE_VALIDACION',
            'tecnica': abierto and permisos.es_tecnologia(c) and (atiende or c.responsable_id == u.pk),
            'validar': c.estado == 'PENDIENTE_VALIDACION' and (c.reportado_por_id == u.pk or ops),
            'cerrar': ops and abierto, 'reabrir': not abierto and (ops or c.reportado_por_id == u.pk), 'info': True,
        },
    }
    if d['acciones']['designar']:
        d['candidatos'] = [{'id': p.id, 'nombre': _n(p)} for p in servicios.personas_del_area(c.area_asignada)]
    return d


@api_view(['GET'])
def opciones_view(request):
    return Response({
        'tipos': Caso.TIPOS, 'categorias': Caso.CATEGORIAS, 'impactos': Caso.IMPACTOS, 'prioridades': Caso.PRIORIDADES, 'estados': Caso.ESTADOS,
        'departamentos': list(Departamento.objects.order_by('nombre').values('id', 'nombre')),
        'es_operaciones': permisos.es_operaciones(request.user),
        'dias_revision': {p: servicios.dias_revision(p) for p, _ in Caso.PRIORIDADES},
        'respuestas_tecnicas': list(servicios.RESPUESTAS_TECNICAS.items()),
    })


@api_view(['GET', 'POST'])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def casos_view(request):
    if request.method == 'POST':
        titulo, descripcion = (request.data.get('titulo') or '').strip(), (request.data.get('descripcion') or '').strip()
        errores = {}
        if not titulo:
            errores['titulo'] = ['Escribe un título corto.']
        if len(descripcion) < 10:
            errores['descripcion'] = ['Describe qué pasa (con al menos una frase).']
        for campo, opciones in (('tipo', Caso.TIPOS), ('categoria', Caso.CATEGORIAS), ('impacto', Caso.IMPACTOS)):
            v = request.data.get(campo)
            if v and v not in dict(opciones):
                errores[campo] = ['Opción no válida.']
        if errores:
            return Response(errores, status=status.HTTP_400_BAD_REQUEST)
        try:
            caso = servicios.reportar(request.user, {**{k: request.data.get(k) for k in ('tipo', 'categoria', 'impacto', 'referencia')},
                                                     'titulo': titulo[:160], 'descripcion': descripcion[:4000]}, request.FILES.getlist('evidencias'))
        except ValueError as e:
            return Response({'evidencias': [str(e)]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_detalle(request, caso), status=status.HTTP_201_CREATED)

    u, p, hoy = request.user, request.query_params, timezone.localdate()
    qs = Caso.objects.select_related('area_origen', 'area_asignada', 'responsable', 'reportado_por')
    f = permisos.filtro(u)
    if f is not None:
        qs = qs.filter(f)
    vista = p.get('vista') or 'todos'
    if vista == 'mios':
        qs = qs.filter(reportado_por=u)
    elif vista == 'a_cargo':
        qs = qs.filter(Q(responsable=u) | Q(area_asignada_id__in=permisos.departamentos_de(u)))
    if p.get('estado') == 'abiertos':
        qs = qs.filter(estado__in=Caso.ABIERTOS)
    elif p.get('estado') == 'vencidos':
        qs = qs.filter(estado__in=Caso.ABIERTOS, proxima_revision__lt=hoy)
    elif p.get('estado') in dict(Caso.ESTADOS):
        qs = qs.filter(estado=p['estado'])
    if p.get('area'):
        qs = qs.filter(area_asignada_id=p['area']) if p['area'] != 'sin' else qs.filter(area_asignada__isnull=True)
    if p.get('prioridad'):
        qs = qs.filter(prioridad=p['prioridad'] if p['prioridad'] != 'sin' else '')
    if p.get('q'):
        t = p['q'].strip()
        qs = qs.filter(Q(titulo__icontains=t) | Q(codigo__icontains=t) | Q(descripcion__icontains=t) | Q(referencia__icontains=t))
    datos = {'casos': [_ficha(c, hoy) for c in qs[:300]]}
    if permisos.es_operaciones(u) and vista == 'todos':
        base = Caso.objects.all()
        datos['resumen'] = servicios.resumen(base, hoy)
    return Response(datos)


def _caso(request, pk):
    c = get_object_or_404(Caso.objects.select_related('area_origen', 'area_asignada', 'responsable', 'reportado_por', 'validado_por'), pk=pk)
    if not permisos.puede_ver(request.user, c):
        from django.http import Http404
        raise Http404
    return c


@api_view(['GET'])
def caso_view(request, pk):
    return Response(_detalle(request, _caso(request, pk)))


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def accion_view(request, pk):
    from django.contrib.auth.models import User
    c, d, u = _caso(request, pk), request.data, request.user
    a = d.get('accion')
    try:
        if a == 'info':
            servicios.agregar_info(u, c, (d.get('nota') or '').strip(), request.FILES.getlist('evidencias'))
        elif a == 'clasificar':
            area = Departamento.objects.filter(pk=d.get('area')).first()
            servicios.clasificar(u, c, d.get('prioridad'), area, d.get('categoria') or None, d.get('tipo') or None, _fecha(d.get('proxima_revision')), d.get('nota') or '')
        elif a == 'unir':
            destino = Caso.objects.filter(codigo__iexact=(d.get('destino') or '').strip()).first()
            if destino is None:
                raise ValueError('No existe un caso con ese código.')
            servicios.unir(u, c, destino)
        elif a == 'designar':
            servicios.designar(u, c, User.objects.filter(pk=d.get('responsable')).first())
        elif a == 'confirmar':
            servicios.confirmar_responsable(u, c)
        elif a == 'avance':
            servicios.avance(u, c, d.get('nota') or '', _fecha(d.get('proxima_revision')), _fecha(d.get('fecha_estimada')))
        elif a == 'bloquear':
            servicios.bloquear(u, c, d.get('nota') or '', _fecha(d.get('proxima_revision')))
        elif a == 'desbloquear':
            servicios.desbloquear(u, c, d.get('nota') or '')
        elif a == 'escalar':
            servicios.escalar(u, c, d.get('nota') or '')
        elif a == 'solucion':
            servicios.solucion(u, c, d.get('nota') or '')
        elif a == 'tecnica':
            servicios.respuesta_tecnica(u, c, d.get('resultado'), d.get('nota') or '', d.get('autorizacion') or '')
        elif a == 'validar':
            servicios.validar(u, c, str(d.get('conforme')).lower() in ('1', 'true', 'si', 'sí'), d.get('nota') or '')
        elif a == 'cerrar':
            servicios.cerrar(u, c, d.get('resultado') or '', d.get('validacion') or '')
        elif a == 'reabrir':
            servicios.reabrir(u, c, d.get('nota') or '')
        else:
            return Response({'detail': 'Acción desconocida.'}, status=status.HTTP_400_BAD_REQUEST)
    except servicios.NoPermitido:
        raise PermissionDenied('No te corresponde esta acción en este caso.')
    except ValueError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    c.refresh_from_db()
    return Response(_detalle(request, c))


@api_view(['GET'])
def evidencia_view(request, pk, eid):
    c = _caso(request, pk)
    e = get_object_or_404(EvidenciaCaso, pk=eid, caso=c)
    return entregar(e.archivo.open('rb'), e.nombre, tipo_por_extension(e.nombre), request)
