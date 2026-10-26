"""Finanzas operativas. Todo aquí es solo para Finanzas (departamento de Administración) y administradores."""
import os
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.operaciones.models import OrdenTrabajo
from apps.operaciones.permisos import es_finanzas
from . import servicios
from .models import Cotizacion, Factura, Gasto, Pago, redondear
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
        tipo = request.data.get('crear_orden')
        if tipo:
            from apps.operaciones import servicios as op_srv
            from apps.operaciones.formularios import TIPOS
            from apps.core.models import Departamento
            if tipo not in TIPOS:
                return Response({"detail": "Tipo de orden desconocido."}, status=status.HTTP_400_BAD_REQUEST)
            depto = Departamento.objects.filter(nombre=TIPOS[tipo]['departamento']).first()
            if depto is None:
                return Response({"detail": f"No existe el departamento {TIPOS[tipo]['departamento']}."}, status=status.HTTP_400_BAD_REQUEST)
            orden = OrdenTrabajo.objects.create(
                tipo=tipo, titulo=(cot.titulo or f"Según {cot.numero}")[:200], cliente=cot.cliente, proyecto=cot.proyecto,
                departamento=depto, descripcion="\n".join(f"• {l.cantidad:g} × {l.descripcion}" for l in cot.lineas.all()),
                monto=cot.subtotal, solicitada_por=request.user, detalles={})
            op_srv.registrar(orden, request.user, f"Creada desde la cotización {cot.numero}")
            op_srv.al_crear(orden, request.user)
        datos = self.get_serializer(cot).data
        datos['orden_creada'] = {'id': orden.pk, 'numero': orden.numero} if orden else None
        return Response(datos)

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

    def get_queryset(self):
        qs = _filtros(Factura.objects.select_related('cliente', 'proyecto', 'orden', 'cotizacion', 'creada_por')
                      .prefetch_related('lineas', 'pagos'), self.request.query_params)
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
        if orden.facturas.exclude(estado='ANULADA').exists():
            return Response({"detail": f"{orden.numero} ya tiene factura."}, status=status.HTTP_400_BAD_REQUEST)
        factura = servicios.factura_desde(orden, request.user)
        return Response(self.get_serializer(factura).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def emitir(self, request, pk=None):
        f = self.get_object()
        if f.estado != 'BORRADOR':
            return Response({"detail": "Ya fue emitida."}, status=status.HTTP_400_BAD_REQUEST)
        if f.total <= 0:
            return Response({"detail": "La factura está en cero."}, status=status.HTTP_400_BAD_REQUEST)
        servicios.emitir(f, request.user, int(request.data.get('dias_credito') or 30))
        return Response(self.get_serializer(f).data)

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
        servicios.registrar_pago(f, request.user, **s.validated_data)
        return Response(self.get_serializer(self.get_queryset().get(pk=f.pk)).data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([EsFinanzas])
def borrar_pago_view(request, pk):
    pago = Pago.objects.select_related('factura').filter(pk=pk).first()
    if pago is None:
        raise Http404
    factura = pago.factura
    pago.delete()
    factura.actualizar_pagos()
    return Response(FacturaSerializer(Factura.objects.prefetch_related('lineas', 'pagos').get(pk=factura.pk)).data)


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


def serializers_error(msg):
    from rest_framework.exceptions import ValidationError
    return ValidationError({'comprobante': [msg]})


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
    sin_facturar = (OrdenTrabajo.objects.filter(estado__in=['LISTA', 'ENTREGADA']).exclude(cliente__tipo='INTERNO')
                    .exclude(facturas__estado__in=['BORRADOR', 'EMITIDA', 'PAGADA']).select_related('cliente').distinct())
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
        'por_facturar': [{'id': o.pk, 'numero': o.numero, 'titulo': o.titulo, 'cliente': o.cliente.nombre, 'estado': o.estado,
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
