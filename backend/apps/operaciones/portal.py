"""
Portal del cliente: un enlace seguro (por WhatsApp o correo, sin contraseña) para ver sus órdenes, aprobar los artes
que el equipo envió (G4) y firmar el acta de entrega (F-12). Lo crea quien lleva la OT (Coordinación, el comercial,
el responsable o la Dirección). Vence a los 30 días (configurable) y se puede revocar.
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import exceptions, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.desempeno.servicios import avisar
from .models import Acta, ArchivoOrden, EnlaceCliente, Firma, OrdenArea, OrdenTrabajo
from .permisos import es_coordinacion
from .servicios_ot import disparar, enlace, finanzas, registrar

DIAS = 30
ESTADO_CLIENTE = {
    'SOLICITADA': 'Recibida', 'DEVUELTA': 'Recibida', 'LIBERADA': 'En preparación', 'EN_PRODUCCION': 'En producción',
    'LISTA': 'Lista para entrega', 'ENTREGADA': 'Entregada', 'CERRADA': 'Entregada', 'EN_PAUSA': 'En pausa', 'CANCELADA': 'Cancelada',
}


def _huella(token):
    return hashlib.sha256((settings.SECRET_KEY + ':portal:' + token).encode()).hexdigest()


def puede_crear(user, orden):
    from apps.core.permisos import tiene
    return bool(tiene(user, 'direccion') or es_coordinacion(user) or orden.asesor_comercial_id == user.pk or orden.responsable_id == user.pk)


# ------------------------------------------------------------------ Del lado del equipo
@api_view(['GET', 'POST'])
def enlaces_view(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo.objects.select_related('cliente'), pk=orden_id)
    if not puede_crear(request.user, orden):
        raise exceptions.PermissionDenied("El enlace para el cliente lo crea Coordinación, el comercial o el responsable de la OT.")
    if request.method == 'POST':
        dias = request.data.get('dias') or DIAS
        try:
            dias = min(max(int(dias), 1), 90)
        except (TypeError, ValueError):
            raise exceptions.ValidationError({'dias': 'Entre 1 y 90.'})
        token = secrets.token_urlsafe(32)
        e = EnlaceCliente.objects.create(cliente=orden.cliente, orden=None if request.data.get('todas') else orden, huella=_huella(token),
                                         para=(request.data.get('para') or orden.contacto or '')[:150], creado_por=request.user,
                                         vence=timezone.now() + timedelta(days=dias))
        registrar(orden, request.user, "Creó un enlace del portal del cliente", f"Para {e.para or orden.cliente.nombre} · vence en {dias} días")
        return Response({**_enlace(e), 'url': request.build_absolute_uri(f'/portal/{token}')}, status=status.HTTP_201_CREATED)
    lista = EnlaceCliente.objects.filter(cliente=orden.cliente).filter(orden__isnull=True) | EnlaceCliente.objects.filter(orden=orden)
    return Response([_enlace(e) for e in lista.select_related('creado_por').order_by('-creado')[:30]])


def _enlace(e):
    return {'id': e.pk, 'para': e.para, 'todas': e.orden_id is None, 'creado': e.creado, 'vence': e.vence, 'revocado': e.revocado,
            'vigente': not e.revocado and e.vence > timezone.now(), 'usos': e.usos, 'ultimo_uso': e.ultimo_uso,
            'creado_por': (e.creado_por.get_full_name() or e.creado_por.username) if e.creado_por else None}


@api_view(['POST'])
def revocar_view(request, pk):
    e = get_object_or_404(EnlaceCliente.objects.select_related('orden'), pk=pk)
    orden = e.orden or OrdenTrabajo.objects.filter(cliente=e.cliente).first()
    if orden is None or not puede_crear(request.user, orden):
        raise exceptions.PermissionDenied("No puedes revocar este enlace.")
    e.revocado = True
    e.save(update_fields=['revocado'])
    if e.orden_id:
        registrar(e.orden, request.user, "Revocó un enlace del portal del cliente", e.para)
    return Response(_enlace(e))


# ------------------------------------------------------------------ Del lado del cliente (sin sesión)
class PortalThrottle(AnonRateThrottle):
    scope = 'portal'
    rate = '60/min'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}

    def allow_request(self, request, view):
        if settings.DEBUG and not getattr(settings, 'PORTAL_LIMITAR_EN_DEBUG', False):
            return True
        return super().allow_request(request, view)


def publico(vista):
    return api_view(vista.metodos)(authentication_classes([])(permission_classes([AllowAny])(throttle_classes([PortalThrottle])(vista))))


def _abrir(token, contar=False):
    e = EnlaceCliente.objects.select_related('cliente', 'orden').filter(huella=_huella(str(token))).first()
    if e is None or e.revocado or e.vence <= timezone.now():
        raise exceptions.NotFound("Este enlace ya no está disponible. Pide uno nuevo a ADZONE.")
    if contar:
        EnlaceCliente.objects.filter(pk=e.pk).update(usos=e.usos + 1, ultimo_uso=timezone.now())
    return e


def _ordenes(e):
    qs = OrdenTrabajo.objects.filter(cliente=e.cliente).exclude(estado='CANCELADA')
    if e.orden_id:
        qs = qs.filter(pk=e.orden_id)
    return qs.prefetch_related('areas', 'archivos', 'actas')


def _archivos_de(oa):
    return [{'id': a.pk, 'nombre': a.nombre_original, 'tipo': a.tipo, 'fecha': a.fecha} for a in oa.archivos.all() if a.categoria in ('ARTE', 'APROBACION')]


def _orden(o):
    areas = [a for a in o.areas.all() if a.estado != 'CANCELADA']
    terminadas = sum(1 for a in areas if a.estado == 'TERMINADA')
    return {
        'id': o.pk, 'numero': o.numero or o.solicitud, 'titulo': o.titulo, 'estado': ESTADO_CLIENTE.get(o.estado, o.get_estado_display()),
        'fecha_compromiso': o.fecha_compromiso, 'fecha_entrega': o.fecha_entrega, 'areas': len(areas), 'terminadas': terminadas,
        'por_aprobar': [{'id': a.pk, 'numero': a.numero, 'que': a.que_produce, 'ronda': a.g4_ronda, 'archivos': _archivos_de(a)}
                        for a in areas if a.estado == 'EN_APROBACION'],
        'aprobadas': [{'numero': a.numero, 'que': a.que_produce, 'fecha': a.g4_fecha, 'por': a.g4_aprobado_por}
                      for a in areas if a.g4_aprobado],
        'actas': [{'id': ac.pk, 'numero': ac.numero, 'fecha': ac.fecha, 'firmada': ac.firmada, 'lista': bool(ac.liberada_por_id) and not ac.firmada,
                   'modalidad': ac.get_modalidad_display(), 'items': ac.items, 'direccion': ac.direccion}
                  for ac in o.actas.all()],
    }


def portal_view(request, token):
    e = _abrir(token, contar=True)
    from apps.finanzas.models import Factura
    facturas = Factura.objects.filter(cliente=e.cliente, estado__in=['EMITIDA', 'PAGADA'])
    if e.orden_id:
        facturas = facturas.filter(orden_id=e.orden_id)
    return Response({
        'cliente': e.cliente.nombre, 'para': e.para, 'vence': e.vence, 'una_orden': e.orden_id is not None,
        'ordenes': [_orden(o) for o in _ordenes(e).order_by('-fecha_creacion')[:50]],
        'facturas': [{'numero': f.ncf or f.cashflow_numero or f.numero, 'fecha': f.fecha, 'total': f.total, 'pagado': f.pagado,
                      'estado': f.get_estado_display(), 'moneda': f.moneda} for f in facturas.order_by('-fecha')[:50]],
    })


portal_view.metodos = ['GET']
portal_view = publico(portal_view)


def archivo_view(request, token, pk):
    e = _abrir(token)
    a = ArchivoOrden.objects.filter(pk=pk, orden__in=_ordenes(e), categoria__in=('ARTE', 'APROBACION')).first()
    if a is None:
        raise Http404
    try:
        f = a.archivo.open('rb')
    except FileNotFoundError:
        raise Http404
    en_linea = (a.tipo or '').startswith('image/') or a.tipo == 'application/pdf'
    return FileResponse(f, as_attachment=not en_linea, filename=a.nombre_original, content_type=a.tipo or 'application/octet-stream')


archivo_view.metodos = ['GET']
archivo_view = publico(archivo_view)


def _texto(v, n):
    return str(v or '').strip()[:n]


@transaction.atomic
def aprobar_view(request, token, oa_id):
    """El cliente aprueba o pide cambios a lo que se le envió (G4). Queda por escrito con su nombre, fecha e IP."""
    e = _abrir(token)
    oa = get_object_or_404(OrdenArea.objects.select_for_update().select_related('orden'), pk=oa_id, orden__in=_ordenes(e))
    if oa.estado != 'EN_APROBACION':
        raise exceptions.ValidationError('Esto ya no está esperando tu aprobación.')
    nombre = _texto(request.data.get('nombre'), 150)
    comentario = _texto(request.data.get('comentario'), 2000)
    aprobado = request.data.get('aprobado') is True
    if len(nombre) < 3:
        raise exceptions.ValidationError({'nombre': 'Escribe tu nombre.'})
    if not aprobado and len(comentario) < 3:
        raise exceptions.ValidationError({'comentario': 'Cuéntanos qué cambios necesitas.'})
    ip = request.META.get('REMOTE_ADDR')
    ultimo = next(iter(_archivos_de(oa)), None)
    oa.g4_aprobado = aprobado
    oa.g4_canales = ['Portal del cliente']
    oa.g4_fecha = timezone.now()
    oa.g4_aprobado_por = nombre
    oa.g4_version = (ultimo['nombre'] if ultimo else '')[:60]
    oa.g4_con_cambios = False
    oa.estado = 'EN_EJECUCION'
    if not aprobado and oa.revision_interna_por_id:
        oa.revision_interna_por = None  # la nueva versión vuelve a pasar por la revisión interna
    oa.save()
    detalle = f"{nombre} · portal del cliente · IP {ip}" + (f" · {comentario}" if comentario else '')
    if aprobado:
        registrar(oa.orden, None, f"{oa.numero}: cliente aprobó en el portal (G4)", detalle)
        Firma.objects.create(orden=oa.orden, oa=oa, contexto='G4', rol='Cliente', nombre=nombre)
    else:
        registrar(oa.orden, None, f"{oa.numero}: cliente pidió cambios en el portal (ronda {oa.g4_ronda})", detalle)
    gente = [oa.responsable, oa.orden.responsable, oa.orden.asesor_comercial, *[u for t in oa.tareas.all() for u in t.companeros.all()]]
    avisar(gente, 'ORDEN' if aprobado else 'DEVUELTA',
           f"{'Aprobado' if aprobado else 'Cambios pedidos'} por el cliente: {oa.numero}", f"{nombre}: {comentario or 'aprobó sin comentarios.'}",
           enlace=enlace(oa.orden, oa))
    disparar('OA_ESTADO', oa, None)
    return Response({'ok': True})


aprobar_view.metodos = ['POST']
aprobar_view = publico(aprobar_view)


@transaction.atomic
def firmar_view(request, token, acta_id):
    """El cliente firma el acta de entrega en su celular. Con eso la OT queda entregada (E6) y se puede facturar."""
    e = _abrir(token)
    acta = get_object_or_404(Acta.objects.select_for_update().select_related('orden'), pk=acta_id, orden__in=_ordenes(e))
    if acta.firmada:
        raise exceptions.ValidationError('El acta ya está firmada.')
    if not acta.liberada_por_id:
        raise exceptions.ValidationError('El acta todavía no está lista para firmar.')
    nombre = _texto(request.data.get('nombre'), 150)
    firma = str(request.data.get('firma') or '')
    conformidad = request.data.get('conformidad')
    if len(nombre) < 3:
        raise exceptions.ValidationError({'nombre': 'Escribe tu nombre.'})
    if conformidad not in dict(Acta.CONFORMIDAD):
        raise exceptions.ValidationError({'conformidad': 'Indica cómo recibes el trabajo.'})
    if not firma.startswith('data:image/png;base64,') or len(firma) > 400000:
        raise exceptions.ValidationError({'firma': 'Firma con el dedo en el recuadro.'})
    acta.conformidad = conformidad
    acta.observaciones_cliente = _texto(request.data.get('observaciones'), 2000)
    acta.firmada = True
    acta.save(update_fields=['conformidad', 'observaciones_cliente', 'firmada'])
    Firma.objects.create(orden=acta.orden, contexto='ACTA', rol='Cliente (portal)', nombre=nombre,
                         documento=_texto(request.data.get('cedula'), 20), imagen=firma)
    orden = acta.orden
    orden.estado = 'ENTREGADA'
    orden.fecha_entrega = acta.fecha
    orden.recibido_por = nombre
    orden.save(update_fields=['estado', 'fecha_entrega', 'recibido_por'])
    registrar(orden, None, f"Entregada (E6) · acta {acta.numero} firmada en el portal",
              f"Recibió {nombre} · {acta.get_conformidad_display()} · IP {request.META.get('REMOTE_ADDR')}")
    avisar([orden.solicitada_por, orden.asesor_comercial, orden.responsable, *finanzas()], 'ORDEN', f"Entregada: {orden.numero}",
           f"{nombre} firmó el acta en el portal. Ya se puede facturar.", enlace=enlace(orden))
    disparar('ORDEN_ESTADO', orden, None)
    return Response({'ok': True})


firmar_view.metodos = ['POST']
firmar_view = publico(firmar_view)
