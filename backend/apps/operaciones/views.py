import mimetypes
import os
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.desempeno.models import Tarea
from apps.desempeno.permisos import es_administrador, puesto_de
from . import servicios
from . import servicios_ot as ot
from .formatos import AREA_CHOICES, G4_CANALES, catalogo
from .models import (
    Acta, ArchivoOrden, AreaConfig, Cliente, Firma, OrdenArea, OrdenTrabajo, Proyecto, SolicitudCambio, TiempoEstandar, Traspaso,
)
from .permisos import (
    areas_que_supervisa, departamentos_a_cargo, es_almacen, es_coordinacion, es_finanzas, es_gerencia, filtro_ordenes,
    filtro_proyectos, gestiona_algo, puede_gestionar_orden, puede_gestionar_proyecto, supervisa_area, ve_montos,
)
from .serializers import (
    ActaSerializer, ArchivoSerializer, AreaConfigSerializer, CambioSerializer, ClienteSerializer, ComentarioSerializer,
    EventoSerializer, FirmaSerializer, IncidenciaSerializer, OrdenAreaSerializer, OrdenSerializer, ProyectoSerializer,
    TiempoEstandarSerializer, TraspasoSerializer,
)

EXTENSIONES = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.pdf', '.ai', '.psd', '.eps', '.svg', '.zip', '.rar', '.doc',
               '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.mp4', '.mov', '.mp3', '.wav', '.txt', '.csv', '.cdr'}
MAX_MB = 25


def _filtrar(qs, q):
    return qs if q is None else qs.filter(q).distinct()


# ------------------------------------------------------------------ Clientes
class ClienteViewSet(viewsets.ModelViewSet):
    """Todos consultan y pueden registrar un cliente nuevo; editar y borrar es de quien gestiona o Finanzas."""
    serializer_class = ClienteSerializer

    def get_queryset(self):
        qs = Cliente.objects.annotate(
            ordenes_abiertas=Count('ordenes', filter=Q(ordenes__estado__in=OrdenTrabajo.ABIERTAS), distinct=True),
            proyectos_activos=Count('proyectos', filter=Q(proyectos__estado__in=['PLANIFICADO', 'EN_CURSO']), distinct=True),
        )
        p = self.request.query_params
        if p.get('q'):
            qs = qs.filter(Q(nombre__icontains=p['q']) | Q(contacto__icontains=p['q']) | Q(rnc__icontains=p['q']))
        if p.get('activos') == '1':
            qs = qs.filter(activo=True)
        return qs.order_by('nombre')

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

    def _exigir(self):
        if not (gestiona_algo(self.request.user) or es_finanzas(self.request.user)):
            raise PermissionDenied("Solo quien gestiona un departamento o Finanzas puede cambiar clientes.")

    def perform_update(self, serializer):
        self._exigir()
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        self._exigir()
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({"detail": "Este cliente tiene órdenes, proyectos o facturas. Márcalo como inactivo."},
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True)
    def resumen(self, request, pk=None):
        cliente = self.get_object()
        user = request.user
        ordenes = _filtrar(cliente.ordenes.select_related('departamento', 'cliente'), filtro_ordenes(user))
        proyectos = _filtrar(cliente.proyectos.select_related('departamento', 'cliente'), filtro_proyectos(user))
        datos = {
            'ordenes': OrdenSerializer(ordenes.prefetch_related('equipo', 'areas', 'facturas')[:50], many=True,
                                       context={'request': request}).data,
            'proyectos': ProyectoSerializer(proyectos.prefetch_related('miembros', 'tareas', 'ordenes'), many=True,
                                            context={'request': request}).data,
        }
        if es_finanzas(user):
            from apps.finanzas.models import Factura
            facturas = Factura.objects.filter(cliente=cliente).exclude(estado='ANULADA')
            datos['finanzas'] = {
                'facturado': sum(f.total for f in facturas if f.estado != 'BORRADOR'),
                'cobrado': sum(f.pagado for f in facturas),
                'saldo': sum(f.saldo for f in facturas if f.estado == 'EMITIDA'),
                'facturas': [{'id': f.id, 'numero': f.numero, 'fecha': f.fecha, 'total': f.total, 'saldo': f.saldo,
                              'estado': f.estado, 'vencida': f.vencida} for f in facturas[:20]],
            }
        return Response(datos)


# ------------------------------------------------------------------ Proyectos
class ProyectoViewSet(viewsets.ModelViewSet):
    serializer_class = ProyectoSerializer

    def get_queryset(self):
        user = self.request.user
        qs = _filtrar(Proyecto.objects.select_related('cliente', 'departamento', 'responsable'), filtro_proyectos(user))
        qs = qs.prefetch_related('miembros', 'tareas', 'ordenes')
        p = self.request.query_params
        if p.get('estado'):
            qs = qs.filter(estado__in=p['estado'].split(','))
        if p.get('cliente'):
            qs = qs.filter(cliente_id=p['cliente'])
        if p.get('departamento'):
            qs = qs.filter(departamento_id=p['departamento'])
        if p.get('activos') == '1':
            qs = qs.filter(estado__in=['PLANIFICADO', 'EN_CURSO', 'EN_PAUSA'])
        if p.get('mios') == '1':
            qs = qs.filter(Q(responsable=user) | Q(miembros=user)).distinct()
        if p.get('q'):
            qs = qs.filter(Q(nombre__icontains=p['q']) | Q(codigo__icontains=p['q']) | Q(cliente__nombre__icontains=p['q']))
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not (gestiona_algo(user) or es_finanzas(user)):
            raise PermissionDenied("Los proyectos los crea quien gestiona un departamento.")
        depto = serializer.validated_data.get('departamento')
        a_cargo = departamentos_a_cargo(user)
        if depto and a_cargo is not None and depto.pk not in a_cargo and not es_finanzas(user):
            raise PermissionDenied("Solo puedes crear proyectos de los departamentos que gestionas.")
        proyecto = serializer.save(creado_por=user, responsable=serializer.validated_data.get('responsable') or user)
        servicios.avisar([*proyecto.miembros.all(), proyecto.responsable], 'PROYECTO', f"Te sumaron a {proyecto.codigo}: {proyecto.nombre}",
                         f"Cliente: {proyecto.cliente}.", enlace=f"/proyectos/{proyecto.pk}", excepto=user)

    def perform_update(self, serializer):
        if not puede_gestionar_proyecto(self.request.user, serializer.instance):
            raise PermissionDenied("Solo el responsable del proyecto o quien gestiona su departamento puede cambiarlo.")
        antes = set(serializer.instance.miembros.values_list('pk', flat=True))
        proyecto = serializer.save()
        nuevos = [u for u in proyecto.miembros.all() if u.pk not in antes]
        servicios.avisar(nuevos, 'PROYECTO', f"Te sumaron a {proyecto.codigo}: {proyecto.nombre}", f"Cliente: {proyecto.cliente}.",
                         enlace=f"/proyectos/{proyecto.pk}", excepto=self.request.user)

    def destroy(self, request, *args, **kwargs):
        proyecto = self.get_object()
        if not puede_gestionar_proyecto(request.user, proyecto):
            raise PermissionDenied("No puedes borrar este proyecto.")
        if proyecto.tareas.exists() or proyecto.ordenes.exists():
            return Response({"detail": "El proyecto tiene tareas u órdenes. Márcalo como cancelado o terminado."},
                            status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True)
    def detalle(self, request, pk=None):
        """Tareas, órdenes, horas y (si corresponde) dinero del proyecto."""
        from apps.desempeno.serializers import TareaSerializer
        from apps.tiempo.models import RegistroTiempo
        proyecto = self.get_object()
        user = request.user
        tareas = (proyecto.tareas.select_related('colaborador', 'asignada_por', 'kpi_asignado__plantilla_kpi')
                  .prefetch_related('companeros', 'pasos', 'evidencias').order_by('fecha_limite'))
        ordenes = proyecto.ordenes.select_related('cliente', 'departamento', 'responsable').prefetch_related(
            'equipo', 'areas', 'facturas')
        minutos = sum(r.minutos for r in RegistroTiempo.objects.filter(proyecto=proyecto, fin__isnull=False))
        datos = {
            'tareas': TareaSerializer(tareas, many=True, context={'request': request}).data,
            'ordenes': OrdenSerializer(ordenes, many=True, context={'request': request}).data,
            'horas': round(minutos / 60, 1),
        }
        if es_finanzas(user) or puede_gestionar_proyecto(user, proyecto):
            from apps.finanzas.servicios import rentabilidad_proyecto
            datos['finanzas'] = rentabilidad_proyecto(proyecto)
        return Response(datos)

    @action(detail=True, methods=['get', 'post'])
    def comentarios(self, request, pk=None):
        proyecto = self.get_object()
        if request.method == 'POST':
            s = ComentarioSerializer(data=request.data, context={'request': request})
            s.is_valid(raise_exception=True)
            c = s.save(proyecto=proyecto, autor=request.user)
            servicios.al_comentar(c)
            return Response(ComentarioSerializer(c, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(ComentarioSerializer(proyecto.comentarios.select_related('autor'), many=True,
                                             context={'request': request}).data)


# ------------------------------------------------------------------ OT Maestra (F-01)
def _error(e):
    return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


def _usuario_o_none(valor):
    if not valor:
        return None
    return User.objects.filter(pk=valor, is_active=True).first()


def _ordenes_visibles(user):
    return _filtrar(OrdenTrabajo.objects.all(), filtro_ordenes(user))


class OrdenViewSet(viewsets.ModelViewSet):
    serializer_class = OrdenSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        qs = OrdenTrabajo.objects.select_related('cliente', 'proyecto', 'departamento', 'solicitada_por', 'responsable',
                                                 'aprobada_por', 'asesor_comercial', 'excepcion_g0_por', 'anticipo_confirmado_por')
        qs = _filtrar(qs, filtro_ordenes(user)).prefetch_related('equipo', 'areas__responsable', 'facturas')
        p = self.request.query_params
        for campo in ('departamento', 'responsable', 'cliente', 'proyecto', 'asesor_comercial'):
            if p.get(campo):
                qs = qs.filter(**{f"{campo}_id": p[campo]})
        if p.get('area'):
            qs = qs.filter(areas__area__in=p['area'].split(',')).distinct()
        if p.get('estado'):
            qs = qs.filter(estado__in=p['estado'].split(','))
        if p.get('prioridad'):
            qs = qs.filter(prioridad__in=p['prioridad'].split(','))
        if p.get('abiertas') == '1':
            qs = qs.filter(estado__in=OrdenTrabajo.ABIERTAS)
        if p.get('mias') == '1':
            qs = qs.filter(Q(responsable=user) | Q(solicitada_por=user) | Q(asesor_comercial=user) | Q(areas__responsable=user)).distinct()
        if p.get('vencidas') == '1':
            qs = qs.filter(estado__in=['LIBERADA', 'EN_PRODUCCION', 'EN_PAUSA'], fecha_compromiso__lt=timezone.localdate())
        if p.get('desde') and p.get('hasta'):
            qs = qs.filter(Q(fecha_compromiso__range=(p['desde'], p['hasta'])) |
                           Q(fecha_compromiso__isnull=True, fecha_requerida__range=(p['desde'], p['hasta'])))
        if p.get('q'):
            q = p['q']
            qs = qs.filter(Q(numero__icontains=q) | Q(solicitud__icontains=q) | Q(titulo__icontains=q) |
                           Q(cliente__nombre__icontains=q) | Q(numero_cotizacion__icontains=q))
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        v = serializer.validated_data
        orden = serializer.save(solicitada_por=user, asesor_comercial=v.get('asesor_comercial') or user)
        ot.al_solicitar(orden, user)

    def perform_update(self, serializer):
        orden = serializer.instance
        if not self.get_serializer().get_puedo_editar(orden):
            raise PermissionDenied("Después de liberada, la OT solo la cambia Coordinación. Pide los cambios en los comentarios.")
        campos = ('titulo', 'descripcion', 'exclusiones', 'prioridad', 'fecha_requerida', 'monto', 'cliente', 'proyecto',
                  'plan_areas', 'g0', 'direccion_entrega', 'anticipo_requerido')
        cambios = [c for c in campos if c in serializer.validated_data and serializer.validated_data[c] != getattr(orden, c)]
        orden = serializer.save()
        if cambios:
            servicios.registrar(orden, self.request.user, "OT editada", ", ".join(cambios))

    def destroy(self, request, *args, **kwargs):
        orden = self.get_object()
        if orden.estado not in ('SOLICITADA', 'DEVUELTA') or not (
                es_coordinacion(request.user) or request.user.pk in (orden.solicitada_por_id, orden.asesor_comercial_id)):
            return _error("Solo se borra una solicitud que no se ha liberado. Si ya avanzó, cancélala.")
        return super().destroy(request, *args, **kwargs)

    def _coordinacion(self):
        if not es_coordinacion(self.request.user):
            raise PermissionDenied("Esto lo hace Coordinación de Producción.")

    def _respuesta(self, orden):
        return Response(self.get_serializer(self.get_queryset().get(pk=orden.pk)).data)

    @action(detail=False)
    def catalogo(self, request):
        datos = catalogo()
        datos['tiempos'] = TiempoEstandarSerializer(TiempoEstandar.objects.all(), many=True).data
        datos['mis_areas'] = areas_que_supervisa(request.user)
        datos['soy_coordinacion'] = es_coordinacion(request.user)
        datos['soy_finanzas'] = es_finanzas(request.user)
        datos['soy_gerencia'] = es_gerencia(request.user)
        datos['soy_almacen'] = es_almacen(request.user)
        return Response(datos)

    @action(detail=False, methods=['post'])
    def calcular(self, request):
        """Sección 4 del F-01: propone la fecha comprometida a partir de las áreas, su cola y la prioridad."""
        s = OrdenSerializer(data={}, context={'request': request})
        try:
            plan = s.validate_plan_areas(request.data.get('plan_areas') or [])
        except Exception as e:  # noqa: BLE001
            return Response({"plan_areas": getattr(e, 'detail', str(e))}, status=status.HTTP_400_BAD_REQUEST)
        from datetime import date
        try:
            requerida = date.fromisoformat(str(request.data.get('fecha_requerida'))[:10]) if request.data.get('fecha_requerida') else None
        except ValueError:
            requerida = None
        temp = OrdenTrabajo(prioridad=request.data.get('prioridad') or 'N', fecha_requerida=requerida,
                            rondas_incluidas=int(request.data.get('rondas_incluidas') or 2))
        r = ot.calcular_compromiso(temp, plan)
        r['por_area'] = [{'area': f['area'], 'cola_dias': ot.cola_del_area(f['area'])} for f in plan]
        return Response(r)

    @action(detail=False)
    def resumen(self, request):
        """Números del tablero: en G0, en producción, vencidas, listas y cumplimiento del mes."""
        qs = self.get_queryset()
        hoy = timezone.localdate()
        inicio_mes = hoy.replace(day=1)
        abiertas = [o for o in qs if o.estado in OrdenTrabajo.ABIERTAS]
        entregadas = [o for o in qs if o.estado in ('ENTREGADA', 'CERRADA') and o.fecha_entrega and o.fecha_entrega >= inicio_mes]
        a_tiempo = [o for o in entregadas if o.a_tiempo]
        ciclos = [(o.fecha_entrega - o.fecha_creacion.date()).days for o in entregadas]
        por_estado, por_area = {}, {}
        for o in abiertas:
            por_estado[o.estado] = por_estado.get(o.estado, 0) + 1
            for a in o.areas.all():
                if a.estado in OrdenArea.ABIERTAS:
                    por_area[a.area] = por_area.get(a.area, 0) + 1
        return Response({
            'abiertas': len(abiertas),
            'por_aprobar': por_estado.get('SOLICITADA', 0),
            'devueltas': por_estado.get('DEVUELTA', 0),
            'listas': por_estado.get('LISTA', 0),
            'por_cerrar': sum(o.estado == 'ENTREGADA' for o in qs),
            'vencidas': sum(o.vencida for o in abiertas),
            'para_hoy': sum((o.fecha_compromiso == hoy) for o in abiertas),
            'entregadas_mes': len(entregadas),
            'a_tiempo_pct': round(100 * len(a_tiempo) / len(entregadas)) if entregadas else None,
            'ciclo_promedio_dias': round(sum(ciclos) / len(ciclos), 1) if ciclos else None,
            'por_estado': por_estado,
            'por_area': por_area,
        })

    # --- G0
    @action(detail=True, methods=['post'])
    def liberar(self, request, pk=None):
        orden = self.get_object()
        fecha = request.data.get('fecha_compromiso')
        try:
            if fecha:
                from datetime import date
                fecha = date.fromisoformat(str(fecha)[:10])
                if fecha < timezone.localdate():
                    return _error("La fecha comprometida no puede estar en el pasado.")
            responsable = _usuario_o_none(request.data.get('responsable'))
            if responsable:
                orden.responsable = responsable
            ot.liberar(orden, request.user, fecha or None)
        except ValueError:
            return _error("Fecha inválida.")
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def rechazar_g0(self, request, pk=None):
        orden = self.get_object()
        try:
            ot.rechazar_g0(orden, request.user, request.data.get('causa'), request.data.get('devuelto_a') or 'Comercial')
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def reenviar(self, request, pk=None):
        orden = self.get_object()
        if not (es_coordinacion(request.user) or request.user.pk in (orden.solicitada_por_id, orden.asesor_comercial_id)):
            raise PermissionDenied("Reenvía quien pidió la OT.")
        try:
            ot.reenviar(orden, request.user)
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def confirmar_anticipo(self, request, pk=None):
        orden = self.get_object()
        if not es_finanzas(request.user):
            raise PermissionDenied("El anticipo lo confirma Administración.")
        ot.confirmar_anticipo(orden, request.user)
        return self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def excepcion(self, request, pk=None):
        orden = self.get_object()
        try:
            ot.autorizar_excepcion(orden, request.user, request.data.get('motivo'))
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def agregar_area(self, request, pk=None):
        """Coordinación suma un área a una OT ya liberada (por ejemplo, tras una Solicitud de Cambio)."""
        orden = self.get_object()
        self._coordinacion()
        if orden.estado not in OrdenTrabajo.PRODUCCION:
            return _error("Solo se agregan áreas a una OT en producción.")
        s = OrdenSerializer(data={}, context={'request': request})
        try:
            fila = s.validate_plan_areas([request.data])[0]
        except Exception as e:  # noqa: BLE001
            return Response({"detail": " ".join(map(str, getattr(e, 'detail', [str(e)])))}, status=status.HTTP_400_BAD_REQUEST)
        oa = OrdenArea.objects.create(orden=orden, area=fila['area'], secuencia=fila['secuencia'], que_produce=fila['que_produce'],
                                      fecha_entrega_interna=fila.get('fecha_entrega_interna') or orden.fecha_compromiso,
                                      tiempo_estandar_dias=fila.get('tiempo_estandar_dias'), horas_estimadas=fila.get('horas_estimadas'),
                                      g1_entrega_por=request.user,
                                      responsable_id=fila.get('responsable'), especificacion=fila.get('especificacion') or {})
        orden.plan_areas = [*orden.plan_areas, fila]
        orden.save(update_fields=['plan_areas'])
        servicios.registrar(orden, request.user, f"Área agregada: {oa.numero}", oa.que_produce)
        servicios.avisar(ot.supervisores_de(oa.area), 'ORDEN', f"Orden de Área {oa.numero}", f"{oa.que_produce}. Revisa G1.",
                         enlace=ot.enlace(orden, oa), excepto=request.user)
        ot.sincronizar_orden(orden, request.user)
        return self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def pausar(self, request, pk=None):
        orden = self.get_object()
        self._coordinacion()
        motivo = (request.data.get('motivo') or '').strip()
        if len(motivo) < 3:
            return _error("Escribe por qué se pausa.")
        error = servicios.pausar(orden, request.user, motivo)
        return _error(error) if error else self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def reanudar(self, request, pk=None):
        orden = self.get_object()
        self._coordinacion()
        error = servicios.reanudar(orden, request.user)
        return _error(error) if error else self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        orden = self.get_object()
        puede = es_coordinacion(request.user) or (orden.estado in ('SOLICITADA', 'DEVUELTA') and
                                                  request.user.pk in (orden.solicitada_por_id, orden.asesor_comercial_id))
        if not puede:
            raise PermissionDenied("No puedes cancelar esta OT.")
        motivo = (request.data.get('motivo') or '').strip()
        if len(motivo) < 3:
            return Response({"motivo": ["Escribe por qué se cancela."]}, status=status.HTTP_400_BAD_REQUEST)
        error = servicios.cancelar(orden, request.user, motivo)
        return _error(error) if error else self._respuesta(orden)

    # --- Entrega, cierre y costos
    @action(detail=True, methods=['get', 'post'])
    def actas(self, request, pk=None):
        orden = self.get_object()
        if request.method == 'POST':
            u = request.user
            if not (es_coordinacion(u) or es_finanzas(u) or supervisa_area(u, 'INS')):
                raise PermissionDenied("El acta la prepara Coordinación o el supervisor de instalación.")
            if orden.estado != 'LISTA':
                return _error("El acta se prepara cuando todas las áreas terminaron (OT lista para entregar).")
            if orden.actas.filter(firmada=False).exists():
                return _error("Ya hay un acta abierta para esta OT.")
            s = ActaSerializer(data=request.data, context={'request': request})
            s.is_valid(raise_exception=True)
            if not s.validated_data.get('items'):
                s.validated_data['items'] = [{'descripcion': a.que_produce, 'cantidad': '', 'observacion': ''}
                                             for a in orden.areas.exclude(estado='CANCELADA')]
            acta = s.save(orden=orden, direccion=s.validated_data.get('direccion') or orden.direccion_entrega,
                          contacto_sitio=s.validated_data.get('contacto_sitio') or orden.contacto)
            servicios.registrar(orden, u, f"Acta {acta.numero} preparada ({acta.get_modalidad_display()})")
            servicios.avisar(ot.finanzas(), 'FINANZAS', f"Liberar salida: {orden.codigo}",
                             "Revisa el estado de cuenta y libera la salida (G5).", enlace=ot.enlace(orden), excepto=u)
            return Response(ActaSerializer(acta, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(ActaSerializer(orden.actas.all(), many=True, context={'request': request}).data)

    @action(detail=True)
    def costos(self, request, pk=None):
        orden = self.get_object()
        if not ve_montos(request.user, orden):
            raise PermissionDenied("Los costos y el margen los ven Administración, Coordinación y quien vendió.")
        datos = ot.costos_orden(orden)
        datos['saldo'] = ot.saldo_de(orden)
        datos['pagado'] = ot.pagado_de(orden)
        return Response(datos)

    @action(detail=True, methods=['post'])
    def cerrar(self, request, pk=None):
        orden = self.get_object()
        try:
            ot.cerrar(orden, request.user)
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._respuesta(orden)

    @action(detail=True, methods=['get', 'post'])
    def cambios(self, request, pk=None):
        orden = self.get_object()
        if request.method == 'POST':
            s = CambioSerializer(data=request.data, context={'request': request, 'orden': orden})
            s.is_valid(raise_exception=True)
            c = s.save(orden=orden, solicitado_por=request.user)
            servicios.registrar(orden, request.user, f"{c.numero}: {c.get_tipo_display()}", c.descripcion[:500])
            servicios.avisar(ot.coordinadores(), 'ORDEN', f"Solicitud de {c.get_tipo_display().split(' (')[0].lower()}: {orden.codigo}",
                             c.descripcion[:300], enlace=ot.enlace(orden), excepto=request.user)
            return Response(CambioSerializer(c, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(CambioSerializer(orden.cambios.select_related('oa', 'solicitado_por'), many=True,
                                         context={'request': request}).data)

    @action(detail=True)
    def historial(self, request, pk=None):
        orden = self.get_object()
        return Response(EventoSerializer(orden.eventos.select_related('usuario'), many=True).data)

    @action(detail=True)
    def completo(self, request, pk=None):
        """Todo lo de la OT de una vez: datos, áreas, traspasos, actas, cambios, archivos, comentarios e historial."""
        orden = self.get_object()
        areas = (orden.areas.select_related('orden__cliente', 'responsable', 'g1_entrega_por', 'g1_recibe_por', 'g3_supervisor')
                 .prefetch_related('tareas__pasos', 'tareas__companeros', 'traspasos'))
        ctx = {'request': request}
        datos = {
            'orden': self.get_serializer(orden).data,
            'areas': OrdenAreaSerializer(areas, many=True, context=ctx).data,
            'traspasos': TraspasoSerializer(orden.traspasos.select_related('oa', 'entrega_por', 'recibe_por', 'destino_oa'), many=True,
                                            context=ctx).data,
            'actas': ActaSerializer(orden.actas.all(), many=True, context=ctx).data,
            'cambios': CambioSerializer(orden.cambios.select_related('oa', 'solicitado_por'), many=True, context=ctx).data,
            'firmas': FirmaSerializer(orden.firmas.all(), many=True).data,
            'archivos': ArchivoSerializer(orden.archivos.select_related('subido_por'), many=True).data,
            'comentarios': ComentarioSerializer(orden.comentarios.select_related('autor'), many=True, context=ctx).data,
            'historial': EventoSerializer(orden.eventos.select_related('usuario'), many=True).data,
            'estado_e': ot.estado_e(orden),
        }
        if es_finanzas(request.user):
            datos['facturas'] = [{'id': f.id, 'numero': f.numero, 'estado': f.estado, 'total': f.total, 'saldo': f.saldo,
                                  'es_anticipo': f.es_anticipo, 'ncf': f.ncf, 'cashflow_numero': f.cashflow_numero}
                                 for f in orden.facturas.all()]
        if ve_montos(request.user, orden):
            datos['saldo'] = ot.saldo_de(orden)
        return Response(datos)

    @action(detail=True, methods=['get', 'post'])
    def comentarios(self, request, pk=None):
        orden = self.get_object()
        if request.method == 'POST':
            s = ComentarioSerializer(data=request.data, context={'request': request})
            s.is_valid(raise_exception=True)
            c = s.save(orden=orden, autor=request.user)
            servicios.al_comentar(c)
            return Response(ComentarioSerializer(c, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(ComentarioSerializer(orden.comentarios.select_related('autor'), many=True,
                                             context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def archivos(self, request, pk=None):
        orden = self.get_object()
        archivos = request.FILES.getlist('archivos')
        if not archivos:
            return _error("Elige al menos un archivo.")
        if len(archivos) > 10:
            return _error("Como máximo 10 archivos a la vez.")
        for f in archivos:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in EXTENSIONES:
                return _error(f"«{f.name}»: ese tipo de archivo no se acepta.")
            if f.size > MAX_MB * 1024 * 1024:
                return _error(f"«{f.name}» pesa más de {MAX_MB} MB. Compártelo por enlace en un comentario.")
        oa = orden.areas.filter(pk=request.data.get('oa')).first() if request.data.get('oa') else None
        categoria = request.data.get('categoria') if request.data.get('categoria') in dict(ArchivoOrden.CATEGORIAS) else 'OTRO'
        nuevos = [ArchivoOrden.objects.create(orden=orden, oa=oa, categoria=categoria, archivo=f, nombre_original=f.name[:255],
                                              tipo=(f.content_type or mimetypes.guess_type(f.name)[0] or '')[:100],
                                              tamano=f.size, subido_por=request.user) for f in archivos]
        servicios.registrar(orden, request.user, f"Subió {len(nuevos)} archivo(s)" + (f" a {oa.numero}" if oa else ''),
                            ", ".join(a.nombre_original for a in nuevos))
        return Response(ArchivoSerializer(nuevos, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=False)
    def bitacora(self, request):
        """F-15 · Bitácora Maestra de OTs, en CSV para Excel."""
        import csv
        from django.http import HttpResponse
        qs = self.get_queryset().order_by('fecha_creacion')
        if request.query_params.get('anio'):
            qs = qs.filter(fecha_creacion__year=request.query_params['anio'])
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="bitacora-ot.csv"'
        resp.write('﻿')
        w = csv.writer(resp)
        dinero = ve_montos(request.user)
        w.writerow(['No. OT', 'Solicitud', 'Fecha solicitud', 'Cliente', 'Proyecto / trabajo', 'Asesor', 'Prioridad', 'Áreas',
                    'Fecha requerida', 'Fecha comprometida', 'Fecha entrega real', 'A tiempo', 'Estado', 'Rondas G4',
                    'Retrabajos', 'Monto', 'Costo real', 'Margen'])
        for o in qs:
            areas = list(o.areas.all())
            margen = (o.monto - o.costo_real) if (o.monto is not None and o.costo_real is not None) else ''
            w.writerow([o.numero or '', o.solicitud, f"{o.fecha_creacion:%d/%m/%Y}", o.cliente.nombre, o.titulo,
                        servicios.nombre(o.asesor_comercial) or '', o.get_prioridad_display(), ' · '.join(a.area for a in areas),
                        o.fecha_requerida or '', o.fecha_compromiso or '', o.fecha_entrega or '',
                        {True: 'Sí', False: 'No'}.get(o.a_tiempo, ''), o.get_estado_display(),
                        max([a.g4_ronda for a in areas] or [0]), sum(a.pase_retrabajo for a in areas),
                        o.monto if dinero else '', o.costo_real if dinero else '', margen if dinero else ''])
        return resp

    @action(detail=False)
    def indicadores(self, request):
        """Indicadores semanales por área (reunión de producción)."""
        from .indicadores import indicadores
        desde = request.query_params.get('desde')
        hasta = request.query_params.get('hasta')
        return Response(indicadores(request.user, desde, hasta))


# ------------------------------------------------------------------ Órdenes de Área (F-02 a F-10)
class OrdenAreaViewSet(viewsets.mixins.ListModelMixin, viewsets.mixins.RetrieveModelMixin,
                       viewsets.mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = OrdenAreaSerializer

    def get_queryset(self):
        user = self.request.user
        qs = OrdenArea.objects.select_related('orden__cliente', 'responsable', 'g1_entrega_por', 'g1_recibe_por', 'g3_supervisor')
        filtro = filtro_ordenes(user)
        if filtro is not None:
            qs = qs.filter(orden_id__in=_ordenes_visibles(user).values('pk'))
        qs = qs.prefetch_related('tareas__pasos', 'tareas__companeros', 'traspasos', 'orden__areas')
        p = self.request.query_params
        if p.get('area'):
            qs = qs.filter(area__in=p['area'].split(','))
        if p.get('estado'):
            qs = qs.filter(estado__in=p['estado'].split(','))
        if p.get('abiertas') == '1':
            qs = qs.filter(estado__in=OrdenArea.ABIERTAS).exclude(orden__estado__in=['CANCELADA', 'EN_PAUSA'])
        if p.get('orden'):
            qs = qs.filter(orden_id=p['orden'])
        if p.get('mias') == '1':
            qs = qs.filter(Q(responsable=user) | Q(tareas__companeros=user)).distinct()
        if p.get('supervisa') == '1':
            qs = qs.filter(area__in=areas_que_supervisa(user))
        return qs.order_by('fecha_entrega_interna', 'id')

    def perform_update(self, serializer):
        oa = serializer.instance
        puedo = serializer.get_puedo(oa)
        u = self.request.user
        if not (puedo.get('editar') or (puedo.get('operar') and set(serializer.validated_data) <= {'especificacion'})):
            raise PermissionDenied("Esta Orden de Área la cambia su supervisor o Coordinación.")
        if ({'servicios_externos', 'otros_materiales'} & set(serializer.validated_data)) and not puedo.get('costos'):
            raise PermissionDenied("Los costos los anota el supervisor del área o Administración.")
        oa = serializer.save()
        servicios.registrar(oa.orden, u, f"{oa.numero} actualizada", ", ".join(serializer.validated_data))

    def _resp(self, oa):
        return Response(self.get_serializer(self.get_queryset().get(pk=oa.pk)).data)

    @action(detail=True, methods=['post'])
    def recibir(self, request, pk=None):
        oa = self.get_object()
        equipo = [u for u in (_usuario_o_none(x) for x in request.data.get('equipo') or []) if u]
        fecha = request.data.get('fecha_entrega_interna') or None
        try:
            if fecha:
                from datetime import date
                fecha = date.fromisoformat(str(fecha)[:10])
            ot.recibir_g1(oa, request.user, request.data.get('g1') or {}, _usuario_o_none(request.data.get('responsable')),
                          equipo, fecha, bool(request.data.get('forzar_secuencia')))
        except ValueError:
            return _error("Fecha inválida.")
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._resp(oa)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        oa = self.get_object()
        try:
            ot.rechazar_g1(oa, request.user, request.data.get('g1') or {}, request.data.get('causa'))
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._resp(oa)

    @action(detail=True, methods=['post'])
    def reemitir(self, request, pk=None):
        oa = self.get_object()
        try:
            ot.reemitir(oa, request.user, request.data.get('nota', ''))
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._resp(oa)

    @action(detail=True, methods=['post'])
    def pedir_revision(self, request, pk=None):
        oa = self.get_object()
        try:
            ot.pedir_revision(oa, request.user)
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._resp(oa)

    @action(detail=True, methods=['post'])
    def revision_interna(self, request, pk=None):
        oa = self.get_object()
        try:
            ot.revisar_interna(oa, request.user, request.data.get('checklist') or {}, bool(request.data.get('aprobar')),
                               request.data.get('comentario', ''))
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._resp(oa)

    @action(detail=True, methods=['post'])
    def enviar_aprobacion(self, request, pk=None):
        oa = self.get_object()
        try:
            ot.enviar_a_aprobacion(oa, request.user)
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._resp(oa)

    @action(detail=True, methods=['post'])
    def registrar_g4(self, request, pk=None):
        oa = self.get_object()
        d = request.data
        try:
            aviso = ot.registrar_g4(oa, request.user, bool(d.get('aprobado')), [c for c in (d.get('canales') or []) if c in G4_CANALES],
                                    d.get('aprobado_por', ''), d.get('version', ''), bool(d.get('con_cambios')), d.get('comentario', ''))
        except ot.ErrorFlujo as e:
            return _error(e)
        r = self._resp(oa)
        r.data['aviso'] = aviso
        return r

    @action(detail=True, methods=['post'])
    def traspasar(self, request, pk=None):
        oa = self.get_object()
        destino = oa.orden.areas.filter(pk=request.data.get('destino_oa')).first() if request.data.get('destino_oa') else None
        try:
            ot.traspasar(oa, request.user, request.data.get('g2') or {}, destino, request.data.get('que_entrega', ''))
        except ot.ErrorFlujo as e:
            return _error(e)
        return self._resp(oa)

    @action(detail=True, methods=['get', 'post'])
    def incidencias(self, request, pk=None):
        oa = self.get_object()
        if request.method == 'POST':
            s = IncidenciaSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            i = s.save(oa=oa, reporta=request.user)
            texto = f"{oa.numero}: incidencia" + (f" ({i.minutos_perdidos} min perdidos)" if i.minutos_perdidos else '')
            servicios.registrar(oa.orden, request.user, texto, i.descripcion)
            return Response(IncidenciaSerializer(i).data, status=status.HTTP_201_CREATED)
        return Response(IncidenciaSerializer(oa.incidencias.select_related('reporta'), many=True).data)

    @action(detail=True)
    def costos(self, request, pk=None):
        oa = self.get_object()
        if not self.get_serializer().get_puedo(oa).get('costos'):
            raise PermissionDenied("Los costos los ven el supervisor del área, Coordinación y Administración.")
        datos = ot.costos_oa(oa)
        datos['vales'] = [{'id': v.id, 'numero': v.numero, 'estado': v.estado, 'costo': v.costo_total}
                          for v in oa.vales.prefetch_related('lineas')]
        return Response(datos)

    @action(detail=True)
    def completo(self, request, pk=None):
        oa = self.get_object()
        ctx = {'request': request}
        return Response({
            'oa': self.get_serializer(oa).data,
            'orden': OrdenSerializer(oa.orden, context=ctx).data,
            'formato': {k: oa.formato.get(k) for k in ('g1', 'especificacion', 'etapas', 'g3', 'g2', 'nota', 'nota_g4')},
            'traspasos': TraspasoSerializer(oa.traspasos.all(), many=True, context=ctx).data,
            'incidencias': IncidenciaSerializer(oa.incidencias.select_related('reporta'), many=True).data,
            'cambios': CambioSerializer(oa.cambios.all(), many=True, context=ctx).data,
            'archivos': ArchivoSerializer(oa.archivos.select_related('subido_por'), many=True).data,
            'hermanas': [{'id': a.pk, 'numero': a.numero, 'area': a.area, 'nombre': a.get_area_display(), 'estado': a.estado,
                          'secuencia': a.secuencia} for a in oa.orden.areas.exclude(pk=oa.pk)],
        })


class TraspasoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TraspasoSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Traspaso.objects.select_related('orden', 'oa', 'destino_oa', 'entrega_por', 'recibe_por')
        if filtro_ordenes(user) is not None:
            qs = qs.filter(orden_id__in=_ordenes_visibles(user).values('pk'))
        p = self.request.query_params
        if p.get('pendientes') == '1':
            qs = qs.filter(resultado='PENDIENTE')
            if not es_coordinacion(user):
                qs = qs.filter(destino_oa__area__in=areas_que_supervisa(user))
        if p.get('orden'):
            qs = qs.filter(orden_id=p['orden'])
        return qs

    @action(detail=True, methods=['post'])
    def recibir(self, request, pk=None):
        t = self.get_object()
        try:
            ot.recibir_traspaso(t, request.user, request.data.get('verificacion') or {}, bool(request.data.get('aceptar')),
                                request.data.get('causa', ''))
        except ot.ErrorFlujo as e:
            return _error(e)
        return Response(self.get_serializer(t).data)


class ActaViewSet(viewsets.mixins.RetrieveModelMixin, viewsets.mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = ActaSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Acta.objects.select_related('orden__cliente', 'liberada_por', 'supervisor')
        if filtro_ordenes(user) is not None:
            qs = qs.filter(orden_id__in=_ordenes_visibles(user).values('pk'))
        return qs

    def perform_update(self, serializer):
        acta = serializer.instance
        u = self.request.user
        if acta.firmada:
            raise PermissionDenied("El acta ya está firmada.")
        if not (es_coordinacion(u) or es_finanzas(u) or supervisa_area(u, 'INS')):
            raise PermissionDenied("El acta la prepara Coordinación o el supervisor de instalación.")
        serializer.save()

    @action(detail=True, methods=['post'])
    def liberar(self, request, pk=None):
        acta = self.get_object()
        try:
            ot.liberar_g5(acta, request.user, request.data.get('g5') or {})
        except ot.ErrorFlujo as e:
            return _error(e)
        return Response(self.get_serializer(acta).data)

    @action(detail=True, methods=['post'])
    def firmar(self, request, pk=None):
        acta = self.get_object()
        try:
            ot.firmar_acta(acta, request.user, request.data)
        except ot.ErrorFlujo as e:
            return _error(e)
        return Response(self.get_serializer(acta).data)

    @action(detail=True, methods=['post'])
    def recibir(self, request, pk=None):
        """Administración recibe el acta firmada (paso previo a facturar y cerrar)."""
        acta = self.get_object()
        if not es_finanzas(request.user):
            raise PermissionDenied("La recibe Administración.")
        if not acta.firmada:
            return _error("El acta todavía no está firmada.")
        acta.recibida_administracion = request.user
        acta.save(update_fields=['recibida_administracion'])
        servicios.registrar(acta.orden, request.user, f"Acta {acta.numero} recibida por Administración")
        return Response(self.get_serializer(acta).data)


class CambioViewSet(viewsets.mixins.ListModelMixin, viewsets.mixins.RetrieveModelMixin, viewsets.mixins.UpdateModelMixin,
                    viewsets.GenericViewSet):
    """F-14 · Solicitudes de cambio y registro de retrabajo."""
    serializer_class = CambioSerializer

    def get_queryset(self):
        user = self.request.user
        qs = SolicitudCambio.objects.select_related('orden', 'oa', 'solicitado_por', 'responsable_accion')
        if filtro_ordenes(user) is not None:
            qs = qs.filter(orden_id__in=_ordenes_visibles(user).values('pk'))
        p = self.request.query_params
        if p.get('estado'):
            qs = qs.filter(estado__in=p['estado'].split(','))
        if p.get('tipo'):
            qs = qs.filter(tipo=p['tipo'])
        return qs

    def perform_update(self, serializer):
        c = serializer.instance
        if not (es_coordinacion(self.request.user) or c.solicitado_por_id == self.request.user.pk):
            raise PermissionDenied("La cambia quien la registró o Coordinación.")
        if c.estado != 'SOLICITADA' and not es_coordinacion(self.request.user):
            raise PermissionDenied("Ya fue resuelta.")
        serializer.save()

    @action(detail=True, methods=['post'])
    def autorizar(self, request, pk=None):
        c = self.get_object()
        u = request.user
        if c.estado != 'SOLICITADA':
            return _error("Ya fue resuelta.")
        sin_costo = c.tipo == 'CAMBIO' and not c.monto_cliente
        if sin_costo and not es_gerencia(u):
            return _error("Un cambio de alcance sin costo para el cliente lo autoriza Gerencia General.")
        if not es_coordinacion(u):
            raise PermissionDenied("Autoriza Coordinación de Producción.")
        marcadas = request.data.get('autorizaciones') or {}
        from .formatos import AUTORIZACIONES_CAMBIO
        c.autorizaciones = {**{t: bool(marcadas.get(t)) for t in AUTORIZACIONES_CAMBIO}, 'por': servicios.nombre(u),
                            'fecha': timezone.localtime().isoformat(timespec='minutes')}
        if c.tipo == 'CAMBIO' and not c.autorizaciones.get(AUTORIZACIONES_CAMBIO[1]):
            return _error("Adjunta y marca la aprobación del cliente por escrito.")
        c.estado = 'AUTORIZADA'
        c.save(update_fields=['autorizaciones', 'estado'])
        orden = c.orden
        detalle = []
        nueva = (c.impacto or {}).get('fecha', {}).get('despues') if isinstance(c.impacto, dict) else None
        if nueva:
            from datetime import date
            try:
                orden.fecha_compromiso = date.fromisoformat(str(nueva)[:10])
                orden.save(update_fields=['fecha_compromiso'])
                detalle.append(f"Nueva fecha comprometida {orden.fecha_compromiso:%d/%m/%Y}")
            except ValueError:
                pass
        if c.tipo == 'CAMBIO' and c.monto_cliente:
            orden.monto = (orden.monto or 0) + c.monto_cliente
            orden.save(update_fields=['monto'])
            detalle.append(f"Monto adicional RD$ {c.monto_cliente:,.2f}")
            servicios.avisar(ot.finanzas(), 'FINANZAS', f"Cambio cobrable en {orden.codigo}", f"{c.numero}: RD$ {c.monto_cliente:,.2f}",
                             enlace=ot.enlace(orden), excepto=u)
        Firma.objects.create(orden=orden, oa=c.oa, contexto='CAMBIO', rol='Coordinación', usuario=u, nombre=servicios.nombre(u))
        servicios.registrar(orden, u, f"{c.numero} autorizada", ". ".join(detalle))
        avisados = [c.solicitado_por, c.responsable_accion]
        for codigo in c.areas_notificadas or []:
            if codigo in dict(AREA_CHOICES):
                avisados += ot.supervisores_de(codigo)
        servicios.avisar(avisados, 'ORDEN', f"{c.numero} autorizada · {orden.codigo}", c.descripcion[:300], enlace=ot.enlace(orden), excepto=u)
        return Response(self.get_serializer(c).data)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        c = self.get_object()
        if not es_coordinacion(request.user):
            raise PermissionDenied("Rechaza Coordinación de Producción.")
        if c.estado != 'SOLICITADA':
            return _error("Ya fue resuelta.")
        c.estado = 'RECHAZADA'
        c.autorizaciones = {'motivo': (request.data.get('motivo') or '')[:500], 'por': servicios.nombre(request.user)}
        c.save(update_fields=['estado', 'autorizaciones'])
        servicios.registrar(c.orden, request.user, f"{c.numero} rechazada", c.autorizaciones['motivo'])
        servicios.avisar([c.solicitado_por], 'ORDEN', f"{c.numero} rechazada", c.autorizaciones['motivo'],
                         enlace=ot.enlace(c.orden), excepto=request.user)
        return Response(self.get_serializer(c).data)


class AreaConfigViewSet(viewsets.mixins.ListModelMixin, viewsets.mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Quién supervisa cada área (recibe G1 y firma G3). Lo cambia la dirección."""
    serializer_class = AreaConfigSerializer
    pagination_class = None

    def get_queryset(self):
        for codigo in dict(AREA_CHOICES):
            AreaConfig.de(codigo)
        return AreaConfig.objects.select_related('departamento').prefetch_related('supervisores').order_by('id')

    def perform_update(self, serializer):
        if not es_gerencia(self.request.user):
            raise PermissionDenied("Los supervisores de área los asigna la dirección.")
        serializer.save()


class TiempoEstandarViewSet(viewsets.ModelViewSet):
    """Tabla de tiempos estándar (días hábiles) por área y trabajo."""
    serializer_class = TiempoEstandarSerializer
    pagination_class = None
    queryset = TiempoEstandar.objects.all()

    def _exigir(self):
        if not es_coordinacion(self.request.user):
            raise PermissionDenied("La tabla de tiempos la mantiene Coordinación.")

    def perform_create(self, serializer):
        self._exigir()
        serializer.save()

    def perform_update(self, serializer):
        self._exigir()
        serializer.save()

    def perform_destroy(self, instance):
        self._exigir()
        instance.delete()


@api_view(['GET', 'DELETE'])
def archivo_view(request, pk):
    archivo = ArchivoOrden.objects.select_related('orden').filter(pk=pk).first()
    if archivo is None:
        raise Http404
    filtro = filtro_ordenes(request.user)
    if filtro is not None and not OrdenTrabajo.objects.filter(filtro, pk=archivo.orden_id).exists():
        raise Http404
    if request.method == 'DELETE':
        if not (archivo.subido_por_id == request.user.pk or puede_gestionar_orden(request.user, archivo.orden)):
            raise PermissionDenied("Solo quien lo subió o quien gestiona la orden puede quitarlo.")
        servicios.registrar(archivo.orden, request.user, "Quitó un archivo", archivo.nombre_original)
        archivo.archivo.delete(save=False)
        archivo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    try:
        f = archivo.archivo.open('rb')
    except FileNotFoundError:
        raise Http404
    en_linea = (archivo.tipo or '').startswith('image/') or archivo.tipo == 'application/pdf'
    return FileResponse(f, as_attachment=not en_linea, filename=archivo.nombre_original,
                        content_type=archivo.tipo or 'application/octet-stream')


# ------------------------------------------------------------------ Directorio y búsqueda
@api_view(['GET'])
def directorio_view(request):
    """Personas activas (para elegir responsables, equipos y @menciones). Solo datos de trabajo."""
    usuarios = User.objects.filter(is_active=True).select_related('perfil__puesto_trabajo__departamento').order_by('first_name', 'username')
    datos = []
    for u in usuarios:
        puesto = puesto_de(u)
        datos.append({'id': u.pk, 'nombre': u.get_full_name() or u.username, 'username': u.username,
                      'puesto': puesto.nombre if puesto else None,
                      'departamento_id': puesto.departamento_id if puesto else None,
                      'departamento': puesto.departamento.nombre if puesto else None})
    return Response(datos)


@api_view(['GET'])
def buscar_view(request):
    """Buscador global (Ctrl+K): órdenes, proyectos, clientes, tareas y, para Finanzas, facturas."""
    q = (request.query_params.get('q') or '').strip()
    if len(q) < 2:
        return Response([])
    user = request.user
    res = []
    for o in _filtrar(OrdenTrabajo.objects.select_related('cliente'), filtro_ordenes(user)).filter(
            Q(numero__icontains=q) | Q(solicitud__icontains=q) | Q(titulo__icontains=q) | Q(cliente__nombre__icontains=q))[:6]:
        res.append({'tipo': 'orden', 'id': o.pk, 'titulo': f"{o.codigo} · {o.titulo}", 'sub': f"{o.cliente} · {o.get_estado_display()}",
                    'enlace': f"/ordenes/{o.pk}"})
    for p in _filtrar(Proyecto.objects.select_related('cliente'), filtro_proyectos(user)).filter(
            Q(nombre__icontains=q) | Q(codigo__icontains=q) | Q(cliente__nombre__icontains=q))[:5]:
        res.append({'tipo': 'proyecto', 'id': p.pk, 'titulo': p.nombre, 'sub': f"{p.codigo} · {p.cliente}", 'enlace': f"/proyectos/{p.pk}"})
    for c in Cliente.objects.filter(Q(nombre__icontains=q) | Q(contacto__icontains=q))[:5]:
        res.append({'tipo': 'cliente', 'id': c.pk, 'titulo': c.nombre, 'sub': c.contacto or c.get_tipo_display(), 'enlace': f"/clientes/{c.pk}"})
    tareas = Tarea.objects.filter(titulo__icontains=q)
    if not es_administrador(user):
        from apps.desempeno.permisos import subordinados
        tareas = tareas.filter(Q(colaborador=user) | Q(companeros=user) | Q(colaborador__in=subordinados(user))).distinct()
    for t in tareas.select_related('colaborador').order_by('-fecha_limite')[:5]:
        res.append({'tipo': 'tarea', 'id': t.pk, 'titulo': t.titulo, 'sub': f"{t.colaborador.get_full_name() or t.colaborador.username} · {t.get_estado_display()}",
                    'enlace': f"/mis-tareas?tarea={t.pk}" if user.pk in t.participantes_ids() else f"/equipo?ver=tareas&tarea={t.pk}"})
    if es_finanzas(user):
        from apps.finanzas.models import Cotizacion, Factura
        for f in Factura.objects.select_related('cliente').filter(Q(numero__icontains=q) | Q(cliente__nombre__icontains=q) | Q(ncf__icontains=q))[:4]:
            res.append({'tipo': 'factura', 'id': f.pk, 'titulo': f.numero, 'sub': f"{f.cliente} · {f.get_estado_display()}",
                        'enlace': f"/finanzas?ver=facturas&id={f.pk}"})
        for c in Cotizacion.objects.select_related('cliente').filter(Q(numero__icontains=q) | Q(cliente__nombre__icontains=q) | Q(titulo__icontains=q))[:4]:
            res.append({'tipo': 'cotizacion', 'id': c.pk, 'titulo': f"{c.numero} · {c.titulo or c.cliente}", 'sub': c.get_estado_display(),
                        'enlace': f"/finanzas?ver=cotizaciones&id={c.pk}"})
    return Response(res)

