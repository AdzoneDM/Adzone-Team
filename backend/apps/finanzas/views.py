"""Finanzas operativas. Todo aquí es solo para Finanzas (departamento de Administración) y administradores."""
import csv
import mimetypes
import os
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action, api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.operaciones.models import OrdenTrabajo
from apps.operaciones.permisos import es_finanzas
from . import servicios
from .models import AdjuntoFactura, Cotizacion, Factura, Gasto, Pago, redondear
from .serializers import CotizacionSerializer, FacturaSerializer, GastoSerializer, PagoSerializer


class EsFinanzas(permissions.BasePermission):
    message = "Solo Finanzas o la dirección pueden ver esto."

    def has_permission(self, request, view):
        return es_finanzas(request.user)


def _fecha(texto, defecto):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return defecto


def _filtros(qs, p):
    if p.get('estado'):
        qs = qs.filter(estado__in=p['estado'].split(','))
    if p.get('cliente'):
        qs = qs.filter(cliente_id=p['cliente'])
    if p.get('proyecto'):
        qs = qs.filter(proyecto_id=p['proyecto'])
    if p.get('desde'):
        qs = qs.filter(fecha__gte=p['desde'])
    if p.get('hasta'):
        qs = qs.filter(fecha__lte=p['hasta'])
    if p.get('q'):
        qs = qs.filter(Q(numero__icontains=p['q']) | Q(cliente__nombre__icontains=p['q']) | Q(titulo__icontains=p['q']))
    return qs


EXTENSIONES_IMAGEN = ('.jpg', '.jpeg', '.png', '.webp')
EXTENSIONES_ARCHIVO = EXTENSIONES_IMAGEN + ('.pdf',)
# Documentos de oficina que se pueden adjuntar a una factura (además de fotos y PDF). Sin ZIP: aquí no hacen falta.
EXTENSIONES_OFICINA = ('.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.csv', '.txt')
MAX_DOCUMENTO_MB = 15


def _revisar_documento(f, que, campo):
    """Documento de oficina (Word, Excel, PowerPoint, OpenDocument, CSV, texto): hasta 15 MB, con el contenido que dice su extensión
    y revisado con el antivirus (con la misma política que el chat: si no se puede revisar, no se acepta)."""
    from apps.chat import antivirus
    from apps.desempeno.serializers import FIRMAS_DOCUMENTO
    ext = os.path.splitext(f.name)[1].lower()
    if f.size > MAX_DOCUMENTO_MB * 1024 * 1024:
        raise serializers_error(f"{que} pesa más de {MAX_DOCUMENTO_MB} MB.", campo)
    if ext in FIRMAS_DOCUMENTO:
        f.seek(0)
        cabeza = f.read(8)
        f.seek(0)
        if not any(cabeza.startswith(x) for x in FIRMAS_DOCUMENTO[ext]):
            raise serializers_error(f"{que} no es un archivo {ext[1:].upper()} válido (aunque tenga ese nombre).", campo)
    elif ext in ('.csv', '.txt'):
        f.seek(0)
        if b'\0' in f.read(4096):
            raise serializers_error(f"{que} no es un archivo de texto válido.", campo)
        f.seek(0)
    if settings.CHAT_ANTIVIRUS != 'omitir':
        estado, detalle = antivirus.escanear(f)
        if estado == antivirus.INFECTADO:
            raise serializers_error(f"El antivirus detectó una amenaza en {que} ({detalle}). No se guardó.", campo)
        if estado == antivirus.NO_DISPONIBLE:
            raise serializers_error(f"No se pudo revisar {que} con el antivirus en este momento. Inténtalo de nuevo en unos minutos.", campo)
    return False


def _revisar_archivo(f, que="El archivo", campo="comprobante", documentos=False):
    """Foto o PDF de hasta 10 MB (con `documentos=True` también documentos de oficina, hasta 15 MB). Devuelve si es una imagen.
    Una «foto» que no se puede abrir como imagen se rechaza."""
    ext = os.path.splitext(f.name)[1].lower()
    if documentos and ext in EXTENSIONES_OFICINA:
        return _revisar_documento(f, que, campo)
    if ext not in EXTENSIONES_ARCHIVO:
        raise serializers_error(f"{que} tiene que ser una foto (JPG, PNG, WEBP), un PDF" + (" o un documento de oficina (Word, Excel, PowerPoint, CSV o texto)." if documentos else "."), campo)
    if f.size > 10 * 1024 * 1024:
        raise serializers_error(f"{que} pesa más de 10 MB.", campo)
    es_imagen = ext in EXTENSIONES_IMAGEN
    if es_imagen:
        from PIL import Image
        try:
            Image.open(f).verify()
        except Exception:  # noqa: BLE001 (cualquier falla al abrirla = no es una imagen válida)
            raise serializers_error(f"{que} no es una imagen válida.", campo)
        finally:
            f.seek(0)
    return es_imagen


def _enviar(campo, descargar=False, nombre=None):
    """Un archivo guardado: fotos y PDF se ven en el navegador (y en la vista previa de la propia plataforma); todo lo demás se descarga,
    sin que el navegador lo interprete ni lo ejecute (`nosniff` + `sandbox`)."""
    tipo = mimetypes.guess_type(campo.name)[0] or 'application/octet-stream'
    en_linea = tipo in ('image/jpeg', 'image/png', 'image/webp', 'application/pdf') and not descargar
    r = FileResponse(campo.open('rb'), filename=nombre or os.path.basename(campo.name), as_attachment=not en_linea,
                     content_type=tipo if en_linea else 'application/octet-stream')
    r['X-Content-Type-Options'] = 'nosniff'
    if en_linea:
        r['X-Frame-Options'] = 'SAMEORIGIN'   # la vista previa de la factura la incrusta; desde otro sitio sigue sin poder
    else:
        r['Content-Security-Policy'] = "sandbox; default-src 'none'"
    return r


class CotizacionViewSet(viewsets.ModelViewSet):
    serializer_class = CotizacionSerializer
    permission_classes = [EsFinanzas]

    def get_queryset(self):
        return _filtros(Cotizacion.objects.select_related('cliente', 'proyecto', 'creada_por').prefetch_related('lineas'),
                        self.request.query_params)

    def perform_create(self, serializer):
        serializer.save(creada_por=self.request.user,
                        valida_hasta=serializer.validated_data.get('valida_hasta') or timezone.localdate() + timedelta(days=15))

    def destroy(self, request, *args, **kwargs):
        if self.get_object().estado != 'BORRADOR':
            return Response({"detail": "Solo se borra una cotización en borrador."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    def _estado(self, cot, desde, hacia):
        if cot.estado not in desde:
            return Response({"detail": f"No se puede: la cotización está «{cot.get_estado_display()}»."},
                            status=status.HTTP_400_BAD_REQUEST)
        cot.estado = hacia
        cot.save(update_fields=['estado'])
        return None

    @action(detail=True, methods=['post'])
    def enviar(self, request, pk=None):
        cot = self.get_object()
        return self._estado(cot, ['BORRADOR'], 'ENVIADA') or Response(self.get_serializer(cot).data)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        cot = self.get_object()
        return self._estado(cot, ['BORRADOR', 'ENVIADA'], 'RECHAZADA') or Response(self.get_serializer(cot).data)

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        """El cliente dijo que sí. Opcional: crear de una vez la orden de trabajo."""
        cot = self.get_object()
        error = self._estado(cot, ['BORRADOR', 'ENVIADA'], 'APROBADA')
        if error:
            return error
        servicios.disparar('COTIZACION_APROBADA', cot, request.user)
        orden = None
        if request.data.get('crear_orden'):
            from apps.operaciones import servicios_ot
            from apps.operaciones.formatos import G0
            orden = OrdenTrabajo.objects.create(
                titulo=(cot.titulo or f"Según {cot.numero}")[:200], cliente=cot.cliente, proyecto=cot.proyecto, cotizacion=cot,
                numero_cotizacion=cot.numero, descripcion="\n".join(f"• {l.cantidad:g} × {l.descripcion}" for l in cot.lineas.all()),
                monto=cot.subtotal, solicitada_por=request.user, asesor_comercial=cot.creada_por or request.user,
                contacto=cot.cliente.contacto, telefono=cot.cliente.telefono, correo=cot.cliente.correo,
                direccion_entrega=cot.cliente.direccion, g0={dict(G0)['cotizacion_aprobada']: True})
            servicios_ot.registrar(orden, request.user, f"Solicitud creada desde la cotización {cot.numero}")
            servicios_ot.al_solicitar(orden, request.user)
        datos = self.get_serializer(cot).data
        datos['orden_creada'] = {'id': orden.pk, 'numero': orden.codigo} if orden else None
        return Response(datos)

    @action(detail=True, methods=['post'])
    def cashflow(self, request, pk=None):
        """Envía la cotización a Cashflow."""
        from apps.integraciones.cashflow.cliente import CashflowError
        from apps.integraciones.cashflow.servicios import enviar_cotizacion
        cot = self.get_object()
        try:
            enviar_cotizacion(cot, request.user)
        except CashflowError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(cot).data)

    @action(detail=True, methods=['post'])
    def facturar(self, request, pk=None):
        cot = self.get_object()
        if cot.estado != 'APROBADA':
            return Response({"detail": "Solo se factura una cotización aprobada."}, status=status.HTTP_400_BAD_REQUEST)
        factura = servicios.factura_desde(cot, request.user)
        return Response(FacturaSerializer(factura).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def duplicar(self, request, pk=None):
        cot = self.get_object()
        lineas = list(cot.lineas.all())
        nueva = Cotizacion.objects.create(cliente=cot.cliente, proyecto=cot.proyecto, titulo=cot.titulo, moneda=cot.moneda,
                                          notas=cot.notas, condiciones=cot.condiciones, creada_por=request.user,
                                          valida_hasta=timezone.localdate() + timedelta(days=15))
        for l in lineas:
            nueva.lineas.create(descripcion=l.descripcion, cantidad=l.cantidad, precio=l.precio, aplica_itbis=l.aplica_itbis, orden=l.orden)
        nueva.recalcular()
        return Response(self.get_serializer(nueva).data, status=status.HTTP_201_CREATED)


class FacturaViewSet(viewsets.ModelViewSet):
    serializer_class = FacturaSerializer
    permission_classes = [EsFinanzas]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = _filtros(Factura.objects.select_related('cliente', 'proyecto', 'orden', 'cotizacion', 'creada_por')
                      .prefetch_related('lineas', 'pagos', 'adjuntos'), self.request.query_params)
        if self.request.query_params.get('vencidas') == '1':
            qs = qs.filter(estado='EMITIDA', vencimiento__lt=timezone.localdate())
        if self.request.query_params.get('por_cobrar') == '1':
            qs = qs.filter(estado='EMITIDA')
        return qs

    def perform_create(self, serializer):
        serializer.save(creada_por=self.request.user)

    def destroy(self, request, *args, **kwargs):
        if self.get_object().estado != 'BORRADOR':
            return Response({"detail": "Una factura emitida no se borra: se anula."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def desde_orden(self, request):
        orden = OrdenTrabajo.objects.filter(pk=request.data.get('orden')).first()
        if orden is None:
            return Response({"detail": "No encontré esa orden."}, status=status.HTTP_404_NOT_FOUND)
        anticipo = bool(request.data.get('anticipo'))
        vivas = orden.facturas.exclude(estado='ANULADA')
        facturado = sum((f.subtotal for f in vivas), Decimal('0'))
        pendiente = (orden.monto or Decimal('0')) - facturado
        monto = None
        if anticipo:
            # Anticipos y abonos antes de entregar: el primero por el anticipo requerido; los demás, por lo que se indique.
            try:
                monto = Decimal(str(request.data.get('monto'))) if request.data.get('monto') not in (None, '') else None
            except Exception:  # noqa: BLE001
                return Response({"monto": ["Monto inválido."]}, status=status.HTTP_400_BAD_REQUEST)
            if monto is None:
                monto = orden.anticipo_requerido if not vivas.filter(es_anticipo=True).exists() else pendiente
            if not monto or monto <= 0:
                return Response({"detail": "Anota el monto del anticipo."}, status=status.HTTP_400_BAD_REQUEST)
            if monto > pendiente:
                return Response({"detail": f"Solo quedan RD$ {pendiente:,.2f} por facturar en {orden.codigo}."},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            # F-12: sin acta firmada no se factura.
            if orden.estado not in ('ENTREGADA', 'CERRADA'):
                return Response({"detail": "Sin acta de entrega firmada no se factura. Si es el anticipo, factúralo como anticipo."},
                                status=status.HTTP_400_BAD_REQUEST)
            if vivas.filter(es_anticipo=False).exists():
                return Response({"detail": f"{orden.codigo} ya tiene factura."}, status=status.HTTP_400_BAD_REQUEST)
            if pendiente <= 0:
                return Response({"detail": f"{orden.codigo} ya quedó facturada completa con los anticipos."},
                                status=status.HTTP_400_BAD_REQUEST)
        factura = servicios.factura_desde(orden, request.user, anticipo=anticipo, monto_anticipo=monto)
        return Response(self.get_serializer(factura).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def emitir(self, request, pk=None):
        f = self.get_object()
        if f.estado != 'BORRADOR':
            return Response({"detail": "Ya fue emitida."}, status=status.HTTP_400_BAD_REQUEST)
        if f.orden_id and not f.es_anticipo and f.orden.estado not in ('ENTREGADA', 'CERRADA'):
            return Response({"detail": "Sin acta de entrega firmada no se factura."}, status=status.HTTP_400_BAD_REQUEST)
        if f.total <= 0:
            return Response({"detail": "La factura está en cero."}, status=status.HTTP_400_BAD_REQUEST)
        servicios.emitir(f, request.user, int(request.data.get('dias_credito') or 30))
        return Response(self.get_serializer(f).data)

    @action(detail=True, methods=['post'])
    def cashflow(self, request, pk=None):
        """Crea la factura fiscal en Cashflow (asigna NCF / e-CF) y la deja emitida aquí."""
        from apps.integraciones.cashflow.cliente import CashflowError
        from apps.integraciones.cashflow.servicios import emitir_factura
        f = self.get_object()
        if f.estado not in ('BORRADOR', 'EMITIDA'):
            return Response({"detail": "Solo se envía una factura en borrador o emitida."}, status=status.HTTP_400_BAD_REQUEST)
        if f.orden_id and not f.es_anticipo and f.orden.estado not in ('ENTREGADA', 'CERRADA'):
            return Response({"detail": "Sin acta de entrega firmada no se factura."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            emitir_factura(f, request.user)
        except CashflowError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(self.get_queryset().get(pk=f.pk)).data)

    @action(detail=True, methods=['post'])
    def cashflow_actualizar(self, request, pk=None):
        """Trae de Cashflow el estado, el NCF y los pagos."""
        from apps.integraciones.cashflow.cliente import CashflowError
        from apps.integraciones.cashflow.servicios import actualizar_factura
        f = self.get_object()
        try:
            nuevos = actualizar_factura(f, request.user)
        except CashflowError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        datos = self.get_serializer(self.get_queryset().get(pk=f.pk)).data
        datos['pagos_nuevos'] = nuevos
        return Response(datos)

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        f = self.get_object()
        if f.pagos.exists():
            return Response({"detail": "Tiene pagos registrados: bórralos antes de anularla."}, status=status.HTTP_400_BAD_REQUEST)
        f.estado = 'ANULADA'
        f.notas = (f.notas + f"\nAnulada: {request.data.get('motivo', '')}").strip()
        f.save(update_fields=['estado', 'notas'])
        return Response(self.get_serializer(f).data)

    @action(detail=True, methods=['post'])
    def pagos(self, request, pk=None):
        f = self.get_object()
        if f.estado not in ('EMITIDA', 'PAGADA'):
            return Response({"detail": "Emite la factura antes de registrar pagos."}, status=status.HTTP_400_BAD_REQUEST)
        s = PagoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if s.validated_data['monto'] > f.saldo:
            return Response({"monto": [f"El saldo es {f.saldo:,.2f}. No se puede cobrar de más."]}, status=status.HTTP_400_BAD_REQUEST)
        comprobante = request.FILES.get('comprobante')
        if comprobante:
            _revisar_archivo(comprobante, "El comprobante")  # antes de cobrar: si el archivo no sirve, no se registra nada
        pago = servicios.registrar_pago(f, request.user, **s.validated_data)
        if comprobante:
            pago.comprobante = comprobante
            pago.save(update_fields=['comprobante'])
        return Response(self.get_serializer(self.get_queryset().get(pk=f.pk)).data, status=status.HTTP_201_CREATED)


    MAX_ADJUNTOS = 50

    def _tipo_adjunto(self, request, defecto='OTRO'):
        tipo = str(request.data.get('tipo') or defecto).upper()
        if tipo not in dict(AdjuntoFactura.TIPOS):
            raise serializers_error("Elige qué tipo de documento es: " + ", ".join(n.lower() for _, n in AdjuntoFactura.TIPOS) + ".", 'tipo')
        return tipo

    @action(detail=True, methods=['post'], url_path='adjuntos')
    def subir_adjuntos(self, request, pk=None):
        """Agrega imágenes, PDF o documentos de oficina a la factura (varios a la vez, en el campo «archivos»; `tipo` y `nota` opcionales)."""
        f = self.get_object()
        archivos = request.FILES.getlist('archivos') or request.FILES.getlist('archivo')
        if not archivos:
            raise serializers_error("Elige al menos una imagen, PDF o documento.", 'archivos')
        if len(archivos) > 10:
            raise serializers_error("Sube hasta 10 archivos a la vez.", 'archivos')
        if f.adjuntos.count() + len(archivos) > self.MAX_ADJUNTOS:
            raise serializers_error(f"Una factura admite hasta {self.MAX_ADJUNTOS} archivos.", 'archivos')
        tipo = self._tipo_adjunto(request)
        revisados = [(a, _revisar_archivo(a, f"«{a.name}»", 'archivos', documentos=True)) for a in archivos]
        for a, es_imagen in revisados:
            AdjuntoFactura.objects.create(factura=f, archivo=a, nombre=a.name[:150], es_imagen=es_imagen, tipo=tipo,
                                          nota=str(request.data.get('nota') or '')[:200], subido_por=request.user)
        return Response(self.get_serializer(self.get_queryset().get(pk=f.pk)).data, status=status.HTTP_201_CREATED)

    def _adjunto(self, adjunto_id):
        a = AdjuntoFactura.objects.filter(factura=self.get_object(), pk=adjunto_id).first()
        if a is None:
            raise Http404
        return a

    @action(detail=True, methods=['get', 'delete', 'patch'], url_path=r'adjuntos/(?P<adjunto_id>[0-9]+)')
    def adjunto(self, request, pk=None, adjunto_id=None):
        """GET: ver o descargar (`?descargar=1`). PATCH: cambiar `tipo`, `nota` o `nombre`. DELETE: quitar el archivo."""
        a = self._adjunto(adjunto_id)
        if request.method == 'DELETE':
            a.archivo.delete(save=False)
            a.delete()
            return Response(self.get_serializer(self.get_queryset().get(pk=pk)).data)
        if request.method == 'PATCH':
            if 'tipo' in request.data:
                a.tipo = self._tipo_adjunto(request)
            if 'nota' in request.data:
                a.nota = str(request.data.get('nota') or '')[:200]
            if 'nombre' in request.data:
                nombre = str(request.data.get('nombre') or '').strip()[:150]
                if not nombre:
                    raise serializers_error("El nombre no puede quedar vacío.", 'nombre')
                a.nombre = nombre
            a.save()
            return Response(self.get_serializer(self.get_queryset().get(pk=pk)).data)
        return _enviar(a.archivo, descargar=request.query_params.get('descargar') == '1', nombre=a.nombre)

    @action(detail=True, methods=['post'], url_path=r'adjuntos/(?P<adjunto_id>[0-9]+)/reemplazar')
    def reemplazar_adjunto(self, request, pk=None, adjunto_id=None):
        """Cambia el archivo por otro, conservando su lugar en la factura (tipo, nota y quién lo subió originalmente se mantienen)."""
        a = self._adjunto(adjunto_id)
        nuevo = request.FILES.get('archivo')
        if not nuevo:
            raise serializers_error("Elige el archivo nuevo.", 'archivo')
        es_imagen = _revisar_archivo(nuevo, f"«{nuevo.name}»", 'archivo', documentos=True)
        viejo = a.archivo
        a.archivo, a.nombre, a.es_imagen = nuevo, nuevo.name[:150], es_imagen
        a.save()
        viejo.delete(save=False)   # el anterior se borra del disco solo después de guardar el nuevo
        return Response(self.get_serializer(self.get_queryset().get(pk=pk)).data)

    @action(detail=False, methods=['get'])
    def reporte(self, request):
        """Excel (CSV) de las facturas con los mismos filtros de la pantalla, o de los pagos con su comprobante (`tipo=pagos`)."""
        p = request.query_params
        r = HttpResponse(content_type='text/csv; charset=utf-8')
        hoy = timezone.localdate()
        r.write('\ufeff')
        w = csv.writer(r)
        if p.get('tipo') == 'pagos':
            r['Content-Disposition'] = f'attachment; filename="pagos-{hoy}.csv"'
            qs = Pago.objects.select_related('factura__cliente', 'registrado_por').order_by('fecha', 'id')
            if p.get('desde'):
                qs = qs.filter(fecha__gte=p['desde'])
            if p.get('hasta'):
                qs = qs.filter(fecha__lte=p['hasta'])
            if p.get('cliente'):
                qs = qs.filter(factura__cliente_id=p['cliente'])
            w.writerow(['Fecha del pago', 'Factura', 'Cliente', 'Monto', 'Moneda', 'Forma de pago', 'Referencia', 'Comprobante', 'Registrado por'])
            totales = {}
            for x in qs:
                m = x.factura.moneda
                totales[m] = totales.get(m, Decimal('0')) + x.monto
                w.writerow([x.fecha.isoformat(), x.factura.numero, x.factura.cliente.nombre, x.monto, m, x.get_metodo_display(), x.referencia,
                            'Sí' if x.comprobante else 'No', (x.registrado_por.get_full_name() or x.registrado_por.username) if x.registrado_por else ''])
            w.writerow([])
            for m, t in totales.items():
                w.writerow(['TOTAL', '', '', t, m])
            return r
        r['Content-Disposition'] = f'attachment; filename="facturas-{hoy}.csv"'
        qs = _filtros(Factura.objects.select_related('cliente', 'orden', 'cotizacion').prefetch_related('pagos', 'adjuntos'), p).order_by('fecha', 'id')
        if p.get('vencidas') == '1':
            qs = qs.filter(estado='EMITIDA', vencimiento__lt=hoy)
        if p.get('por_cobrar') == '1':
            qs = qs.filter(estado='EMITIDA')
        w.writerow(['Número', 'Fecha', 'Cliente', 'RNC', 'Título', 'Estado', 'NCF', 'Moneda', 'Subtotal', 'ITBIS', 'Total', 'Pagado', 'Saldo',
                    'Vencimiento', 'Días de atraso', 'Pagos', 'Último pago', 'Comprobantes de pago', 'Imágenes y documentos', 'Orden', 'Cotización'])
        totales = {}
        for f in qs:
            pagos = list(f.pagos.all())
            atraso = (hoy - f.vencimiento).days if f.vencida else 0
            t = totales.setdefault(f.moneda, [Decimal('0')] * 3)
            if f.estado != 'ANULADA':
                t[0] += f.total
                t[1] += f.pagado
                t[2] += f.saldo
            w.writerow([f.numero, f.fecha.isoformat(), f.cliente.nombre, f.cliente.rnc or '', f.titulo, f.get_estado_display(), f.ncf, f.moneda,
                        f.subtotal, f.itbis, f.total, f.pagado, f.saldo, f.vencimiento.isoformat() if f.vencimiento else '', atraso, len(pagos),
                        max((x.fecha for x in pagos), default='') if pagos else '', sum(1 for x in pagos if x.comprobante), len(f.adjuntos.all()),
                        f.orden.codigo if f.orden_id else '', f.cotizacion.numero if f.cotizacion_id else ''])
        w.writerow([])
        for m, (tot, pag, sal) in totales.items():
            w.writerow(['TOTAL (sin anuladas)', '', '', '', '', '', '', m, '', '', tot, pag, sal])
        return r


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([EsFinanzas])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def comprobante_pago_view(request, pk):
    """El comprobante de un pago: verlo o descargarlo (GET), agregarlo o cambiarlo después de registrar el pago (POST) y quitarlo (DELETE)."""
    pago = Pago.objects.select_related('factura').filter(pk=pk).first()
    if pago is None:
        raise Http404
    if request.method == 'GET':
        if not pago.comprobante:
            raise Http404
        return _enviar(pago.comprobante, descargar=request.query_params.get('descargar') == '1')
    if request.method == 'POST':
        archivo = request.FILES.get('comprobante')
        if not archivo:
            raise serializers_error("Elige la foto o el PDF del comprobante.")
        _revisar_archivo(archivo, "El comprobante")
        if pago.comprobante:
            pago.comprobante.delete(save=False)
        pago.comprobante = archivo
        pago.save(update_fields=['comprobante'])
    elif pago.comprobante:
        pago.comprobante.delete(save=False)
        pago.comprobante = None
        pago.save(update_fields=['comprobante'])
    return Response(FacturaSerializer(Factura.objects.prefetch_related('lineas', 'pagos', 'adjuntos').get(pk=pago.factura_id)).data)


@api_view(['DELETE'])
@permission_classes([EsFinanzas])
def borrar_pago_view(request, pk):
    pago = Pago.objects.select_related('factura').filter(pk=pk).first()
    if pago is None:
        raise Http404
    factura = pago.factura
    pago.delete()
    factura.actualizar_pagos()
    return Response(FacturaSerializer(Factura.objects.prefetch_related('lineas', 'pagos', 'adjuntos').get(pk=factura.pk)).data)


class GastoViewSet(viewsets.ModelViewSet):
    serializer_class = GastoSerializer
    permission_classes = [EsFinanzas]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = Gasto.objects.select_related('proyecto', 'orden')
        p = self.request.query_params
        if p.get('desde'):
            qs = qs.filter(fecha__gte=p['desde'])
        if p.get('hasta'):
            qs = qs.filter(fecha__lte=p['hasta'])
        if p.get('categoria'):
            qs = qs.filter(categoria=p['categoria'])
        if p.get('proyecto'):
            qs = qs.filter(proyecto_id=p['proyecto'])
        if p.get('q'):
            qs = qs.filter(Q(concepto__icontains=p['q']) | Q(proveedor__icontains=p['q']))
        return qs

    def _comprobante(self, gasto):
        f = self.request.FILES.get('comprobante')
        if f:
            if os.path.splitext(f.name)[1].lower() not in ('.pdf', '.jpg', '.jpeg', '.png', '.webp'):
                raise serializers_error("El comprobante tiene que ser foto o PDF.")
            if f.size > 10 * 1024 * 1024:
                raise serializers_error("El comprobante pesa más de 10 MB.")
            gasto.comprobante = f
            gasto.save(update_fields=['comprobante'])

    def perform_create(self, serializer):
        self._comprobante(serializer.save(registrado_por=self.request.user))

    def perform_update(self, serializer):
        self._comprobante(serializer.save())

    @action(detail=True)
    def comprobante(self, request, pk=None):
        g = self.get_object()
        if not g.comprobante:
            raise Http404
        return FileResponse(g.comprobante.open('rb'), filename=os.path.basename(g.comprobante.name))


def serializers_error(msg, campo='comprobante'):
    from rest_framework.exceptions import ValidationError
    return ValidationError({campo: [msg]})


@api_view(['GET'])
@permission_classes([EsFinanzas])
def resumen_view(request):
    hoy = timezone.localdate()
    mes = _fecha((request.query_params.get('mes') or '') + '-01' if request.query_params.get('mes') else None, hoy.replace(day=1))
    inicio = mes.replace(day=1)
    fin = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    facturas_mes = Factura.objects.filter(fecha__range=(inicio, fin), estado__in=['EMITIDA', 'PAGADA'])
    pagos_mes = Pago.objects.filter(fecha__range=(inicio, fin))
    gastos_mes = Gasto.objects.filter(fecha__range=(inicio, fin))
    por_cobrar = [f for f in Factura.objects.filter(estado='EMITIDA').select_related('cliente')]
    facturado = sum((f.subtotal for f in facturas_mes), Decimal('0'))
    gastos = sum((g.monto for g in gastos_mes), Decimal('0'))
    por_categoria = {}
    for g in gastos_mes:
        por_categoria[g.get_categoria_display()] = por_categoria.get(g.get_categoria_display(), Decimal('0')) + g.monto
    deudores = {}
    for f in por_cobrar:
        d = deudores.setdefault(f.cliente_id, {'cliente_id': f.cliente_id, 'cliente': f.cliente.nombre, 'saldo': Decimal('0'), 'vencido': Decimal('0')})
        d['saldo'] += f.saldo
        if f.vencida:
            d['vencido'] += f.saldo
    # Entregadas (acta firmada) a las que todavía les falta facturar parte del monto.
    sin_facturar = []
    for o in (OrdenTrabajo.objects.filter(estado='ENTREGADA', monto__gt=0).exclude(cliente__tipo='INTERNO')
              .select_related('cliente').prefetch_related('facturas')):
        facturado = sum((f.subtotal for f in o.facturas.all() if f.estado not in ('ANULADA',)), Decimal('0'))
        if facturado < o.monto:
            sin_facturar.append(o)
    cot_abiertas = Cotizacion.objects.filter(estado__in=['BORRADOR', 'ENVIADA'])
    return Response({
        'mes': inicio.isoformat()[:7],
        'facturado': redondear(facturado),
        'itbis': redondear(sum((f.itbis for f in facturas_mes), Decimal('0'))),
        'cobrado': redondear(sum((p.monto for p in pagos_mes), Decimal('0'))),
        'gastos': redondear(gastos),
        'resultado': redondear(facturado - gastos),
        'por_cobrar': redondear(sum((f.saldo for f in por_cobrar), Decimal('0'))),
        'vencido': redondear(sum((f.saldo for f in por_cobrar if f.vencida), Decimal('0'))),
        'antiguedad': servicios.antiguedad(hoy),
        'gastos_por_categoria': [{'categoria': k, 'monto': redondear(v)} for k, v in sorted(por_categoria.items(), key=lambda x: -x[1])],
        'deudores': sorted(deudores.values(), key=lambda d: -d['saldo'])[:8],
        'por_facturar': [{'id': o.pk, 'numero': o.codigo, 'titulo': o.titulo, 'cliente': o.cliente.nombre, 'estado': o.estado,
                          'estado_nombre': o.get_estado_display(), 'monto': o.monto, 'fecha_entrega': o.fecha_entrega}
                         for o in sin_facturar[:30]],
        'cotizaciones_abiertas': {'cantidad': cot_abiertas.count(),
                                  'monto': redondear(sum((c.total for c in cot_abiertas), Decimal('0')))},
    })


@api_view(['GET'])
@permission_classes([EsFinanzas])
def rentabilidad_view(request):
    """Por proyecto o por cliente: facturado (sin ITBIS) − gastos − costo de las horas."""
    from apps.tiempo.models import RegistroTiempo
    hoy = timezone.localdate()
    desde = _fecha(request.query_params.get('desde'), hoy.replace(month=1, day=1))
    hasta = _fecha(request.query_params.get('hasta'), hoy)
    por = request.query_params.get('por', 'proyecto')
    facturas = list(Factura.objects.filter(fecha__range=(desde, hasta), estado__in=['EMITIDA', 'PAGADA']).select_related('cliente', 'proyecto'))
    gastos = list(Gasto.objects.filter(fecha__range=(desde, hasta)).select_related('proyecto__cliente', 'orden__cliente'))
    registros = list(RegistroTiempo.objects.filter(inicio__date__range=(desde, hasta), fin__isnull=False)
                     .select_related('usuario__perfil', 'proyecto__cliente', 'orden__cliente'))

    def clave_de(obj, tipo):
        if por == 'cliente':
            if tipo == 'factura':
                return obj.cliente_id, obj.cliente.nombre
            c = (obj.orden.cliente if obj.orden_id else obj.proyecto.cliente if obj.proyecto_id else None)
            return (c.pk, c.nombre) if c else (None, None)
        p = obj.proyecto if obj.proyecto_id else (obj.orden.proyecto if getattr(obj, 'orden_id', None) and obj.orden.proyecto_id else None)
        return (p.pk, f"{p.codigo} · {p.nombre}") if p else (None, None)

    grupos = {}
    for tipo, lista in (('factura', facturas), ('gasto', gastos), ('tiempo', registros)):
        for obj in lista:
            k, nombre = clave_de(obj, tipo)
            if k is None:
                continue
            g = grupos.setdefault(k, {'id': k, 'nombre': nombre, 'f': [], 'g': [], 't': []})
            g[tipo[0]].append(obj)
    filas = []
    for g in grupos.values():
        filas.append({'id': g['id'], 'nombre': g['nombre'], **servicios.rentabilidad(g['f'], g['g'], g['t'])})
    filas.sort(key=lambda x: -x['facturado'])
    return Response({'desde': desde, 'hasta': hasta, 'por': por, 'filas': filas})


# ------------------------------------------------------------------ v10: rentabilidad por OT, cliente y departamento; tasas de cambio
from .models import TasaCambio  # noqa: E402


@api_view(['GET'])
@permission_classes([EsFinanzas])
def rentabilidad_ordenes_view(request):
    from .rentabilidad import MARGEN_MINIMO, rentabilidad_ordenes
    hoy = timezone.localdate()
    desde = _fecha(request.query_params.get('desde'), hoy.replace(day=1))
    hasta = _fecha(request.query_params.get('hasta'), hoy)
    try:
        minimo = float(request.query_params.get('margen_minimo') or MARGEN_MINIMO)
    except ValueError:
        return Response({'margen_minimo': 'Debe ser un número.'}, status=400)
    datos = rentabilidad_ordenes(desde, hasta, minimo)
    if request.query_params.get('formato') == 'csv':
        r = HttpResponse(content_type='text/csv; charset=utf-8')
        r['Content-Disposition'] = f'attachment; filename="rentabilidad-ot-{desde}-a-{hasta}.csv"'
        r.write('﻿')
        w = csv.writer(r)
        w.writerow(['OT', 'Trabajo', 'Cliente', 'Departamento', 'Estado', 'Vendido', 'Facturado', 'Ingreso usado', 'Mano de obra', 'Materiales',
                    'Equipos', 'Freelance y pauta', 'Transporte', 'Otros', 'Costo total', 'Utilidad', 'Margen %', 'Horas', 'Retrabajo'])
        for f in datos['ordenes']:
            w.writerow([f['numero'], f['titulo'], f['cliente'], f['departamento'], f['estado'], f['vendido'], f['facturado'], f['ingreso'],
                        f['mano_obra'], f['materiales'], f['equipos'], f['externos'], f['transporte'], f['otros'], f['costo'], f['utilidad'],
                        '' if f['margen'] is None else f['margen'], f['horas'], f['retrabajo']])
        return r
    return Response(datos)


@api_view(['GET'])
@permission_classes([EsFinanzas])
def rentabilidad_orden_view(request, pk):
    from apps.operaciones.models import OrdenTrabajo
    from .rentabilidad import detalle_orden
    ot = OrdenTrabajo.objects.select_related('cliente', 'cotizacion').filter(pk=pk).first()
    if ot is None:
        return Response({'detail': 'No existe.'}, status=404)
    return Response(detalle_orden(ot))


class TasaSerializer(serializers.ModelSerializer):
    class Meta:
        model = TasaCambio
        fields = ['id', 'fecha', 'usd_dop', 'fuente']

    def validate_usd_dop(self, v):
        if v <= 0 or v > 1000:
            raise serializers.ValidationError('Revisa la tasa: RD$ por cada US$ 1.')
        return v


class TasaViewSet(viewsets.ModelViewSet):
    queryset = TasaCambio.objects.all()
    serializer_class = TasaSerializer
    permission_classes = [EsFinanzas]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def perform_create(self, serializer):
        serializer.save(registrada_por=self.request.user)
