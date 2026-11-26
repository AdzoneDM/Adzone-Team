from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import Departamento
from apps.desempeno.permisos import es_administrador, puesto_de

from . import servicios
from .models import SERVICIOS, Oportunidad, SolicitudServicio
from .permisos import es_comercial, filtro_solicitudes, puede_cambiar_solicitud
from .serializers import SERVICIOS_LISTA, MovimientoSerializer, OportunidadSerializer, SolicitudSerializer

CAMPOS_OPORTUNIDAD = ['titulo', 'necesidades', 'departamento', 'responsable', 'estado', 'fecha_contacto', 'proximo_seguimiento',
                      'motivo_no_concretado', 'cliente']
CAMPOS_SOLICITUD = ['servicio', 'servicio_detalle', 'departamento', 'descripcion', 'responsable', 'estado']


def _filtros_comunes(qs, p):
    if p.get('estado'):
        qs = qs.filter(estado__in=p['estado'].split(','))
    if p.get('responsable'):
        qs = qs.filter(responsable_id=p['responsable'])
    if p.get('departamento'):
        qs = qs.filter(departamento_id=p['departamento'])
    if p.get('cliente'):
        qs = qs.filter(cliente_id=p['cliente'])
    if p.get('desde'):
        qs = qs.filter(fecha_creacion__date__gte=p['desde'])
    if p.get('hasta'):
        qs = qs.filter(fecha_creacion__date__lte=p['hasta'])
    return qs


class OportunidadViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
                         mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = OportunidadSerializer
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not es_comercial(request.user):
            raise PermissionDenied("Las oportunidades comerciales son de Marketing (permiso «Oportunidades comerciales»).")

    def get_queryset(self):
        qs = (Oportunidad.objects.select_related('cliente', 'departamento', 'responsable', 'creado_por')
              .prefetch_related('solicitudes__departamento'))
        p = self.request.query_params
        qs = _filtros_comunes(qs, p)
        if p.get('vista') == 'pendientes':
            qs = qs.exclude(estado__in=Oportunidad.CERRADOS)
        elif p.get('vista') == 'aprobadas':
            qs = qs.filter(estado='APROBADA')
        elif p.get('vista') == 'no_concretadas':
            qs = qs.filter(estado='NO_CONCRETADA')
        elif p.get('vista') == 'seguimiento':
            qs = qs.exclude(estado__in=Oportunidad.CERRADOS).filter(proximo_seguimiento__lte=timezone.localdate())
        if p.get('q'):
            qs = qs.filter(Q(titulo__icontains=p['q']) | Q(codigo__icontains=p['q']) | Q(cliente__nombre__icontains=p['q']))
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        puesto = puesto_de(user)
        depto = serializer.validated_data.get('departamento') or (puesto.departamento if puesto else None)
        o = serializer.save(creado_por=user, departamento=depto,
                            responsable=serializer.validated_data.get('responsable') or user,
                            fecha_contacto=serializer.validated_data.get('fecha_contacto') or timezone.localdate())
        servicios.registrar(user, 'CREADA', oportunidad=o, despues=o.estado, texto=o.titulo)
        if o.responsable_id != user.pk:
            servicios.avisar([o.responsable], 'COMERCIAL', f"Oportunidad a tu cargo: {o.cliente}", f"{o.codigo} · {o.titulo}",
                             enlace=f"/oportunidades?oportunidad={o.pk}", excepto=user)

    def update(self, request, *args, **kwargs):
        o = self.get_object()
        s = self.get_serializer(o, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        datos = {k: v for k, v in s.validated_data.items() if k in CAMPOS_OPORTUNIDAD}
        responsable_antes = o.responsable_id
        o, cambios = servicios.guardar_cambios(o, datos, request.user, motivo=(request.data.get('motivo') or datos.get('motivo_no_concretado') or '').strip())
        if 'responsable' in cambios and o.responsable_id and o.responsable_id != responsable_antes:
            servicios.avisar([o.responsable], 'COMERCIAL', f"Oportunidad a tu cargo: {o.cliente}", f"{o.codigo} · {o.titulo}",
                             enlace=f"/oportunidades?oportunidad={o.pk}", excepto=request.user)
        return Response(self.get_serializer(o).data)

    def destroy(self, request, *args, **kwargs):
        o = self.get_object()
        if not es_administrador(request.user):
            raise PermissionDenied("Eliminar oportunidades es de Dirección. Márcala como «No concretado».")
        if o.solicitudes.exists():
            return Response({"detail": "Tiene solicitudes de servicio: márcala como «No concretado»."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        o = self.get_object()
        datos = self.get_serializer(o).data
        datos['solicitudes'] = SolicitudSerializer(o.solicitudes.select_related('cliente', 'departamento', 'responsable', 'creado_por',
                                                                                'proyecto', 'orden', 'oportunidad'),
                                                   many=True, context={'request': request}).data
        datos['historial'] = MovimientoSerializer(o.movimientos.select_related('usuario'), many=True).data
        return Response(datos)

    @action(detail=True, methods=['post'])
    def comentar(self, request, pk=None):
        o = self.get_object()
        texto = (request.data.get('texto') or '').strip()
        if not texto:
            raise ValidationError({'texto': "Escribe el comentario."})
        m = servicios.registrar(request.user, 'COMENTARIO', oportunidad=o, texto=texto[:4000])
        return Response(MovimientoSerializer(m).data, status=status.HTTP_201_CREATED)

    @action(detail=False)
    def resumen(self, request):
        qs = _filtros_comunes(Oportunidad.objects.all(), request.query_params)
        por_estado = dict(qs.values_list('estado').annotate(n=Count('id')))
        return Response({
            'estados': [{'codigo': c, 'nombre': n, 'total': por_estado.get(c, 0)} for c, n in Oportunidad.ESTADOS],
            'pendientes': qs.exclude(estado__in=Oportunidad.CERRADOS).count(),
            'seguimiento_vencido': qs.exclude(estado__in=Oportunidad.CERRADOS).filter(proximo_seguimiento__lte=timezone.localdate()).count(),
            'servicios': SERVICIOS_LISTA,
            'estados_solicitud': [{'codigo': c, 'nombre': n} for c, n in SolicitudServicio.ESTADOS],
        })


class SolicitudViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
                       viewsets.GenericViewSet):
    serializer_class = SolicitudSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = SolicitudServicio.objects.select_related('cliente', 'departamento', 'responsable', 'creado_por', 'proyecto', 'orden',
                                                       'oportunidad')
        f = filtro_solicitudes(self.request.user)
        if f is not None:
            qs = qs.filter(f)
        p = self.request.query_params
        qs = _filtros_comunes(qs, p)
        if p.get('oportunidad'):
            qs = qs.filter(oportunidad_id=p['oportunidad'])
        if p.get('vista') == 'abiertas':
            qs = qs.exclude(estado__in=SolicitudServicio.CERRADOS)
        if p.get('q'):
            qs = qs.filter(Q(codigo__icontains=p['q']) | Q(cliente__nombre__icontains=p['q']) | Q(descripcion__icontains=p['q']))
        return qs

    def create(self, request, *args, **kwargs):
        if not es_comercial(request.user):
            raise PermissionDenied("Las solicitudes de servicio las registra Marketing desde una oportunidad o la ficha del cliente.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        d = serializer.validated_data
        oportunidad = d.get('oportunidad')
        cliente = oportunidad.cliente if oportunidad else None
        if cliente is None:
            from apps.operaciones.models import Cliente
            cliente = get_object_or_404(Cliente, pk=self.request.data.get('cliente'))
        depto = d.get('departamento')
        if depto is None:
            sugerido = SERVICIOS.get(d.get('servicio'), (None, None))[1]
            depto = Departamento.objects.filter(nombre__iexact=sugerido).first() if sugerido else None
            if depto is None:
                raise ValidationError({'departamento': "Elige el departamento responsable."})
        if d.get('servicio') == 'OTRO' and not (d.get('servicio_detalle') or '').strip():
            raise ValidationError({'servicio_detalle': "Escribe qué servicio solicita."})
        s = serializer.save(creado_por=user, cliente=cliente, departamento=depto)
        servicios.registrar(user, 'CREADA', solicitud=s, despues=s.estado, texto=s.servicio_nombre)
        if oportunidad:
            servicios.registrar(user, 'CAMBIO', oportunidad=oportunidad, texto=f"Nueva solicitud {s.codigo}: {s.servicio_nombre} → {depto}")
        servicios.avisar_solicitud_nueva(s, user)

    def update(self, request, *args, **kwargs):
        s = self.get_object()
        if not puede_cambiar_solicitud(request.user, s):
            raise PermissionDenied("Esta solicitud la gestiona su departamento (su responsable o quien lo gestiona).")
        ser = self.get_serializer(s, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        datos = {k: v for k, v in ser.validated_data.items() if k in CAMPOS_SOLICITUD}
        if datos.get('estado') == 'EN_EJECUCION':
            raise ValidationError({'estado': "Pasa a «En proyecto / orden» al convertirla."})
        if 'departamento' in datos and datos['departamento'] != s.departamento and not (
                es_comercial(request.user) or es_administrador(request.user)):
            raise PermissionDenied("Solo Marketing o Dirección cambian el departamento de una solicitud.")
        responsable_antes = s.responsable_id
        s, cambios = servicios.guardar_cambios(s, datos, request.user, motivo=(request.data.get('motivo') or '').strip())
        if 'responsable' in cambios and s.responsable_id and s.responsable_id != responsable_antes:
            servicios.avisar([s.responsable], 'COMERCIAL', f"Solicitud a tu cargo {s.codigo}: {s.servicio_nombre}",
                             f"Cliente: {s.cliente}.", enlace=f"/oportunidades?solicitud={s.pk}", excepto=request.user)
        return Response(self.get_serializer(s).data)

    def retrieve(self, request, *args, **kwargs):
        s = self.get_object()
        datos = self.get_serializer(s).data
        datos['historial'] = MovimientoSerializer(s.movimientos.select_related('usuario'), many=True).data
        return Response(datos)

    @action(detail=True, methods=['post'])
    def comentar(self, request, pk=None):
        s = self.get_object()
        texto = (request.data.get('texto') or '').strip()
        if not texto:
            raise ValidationError({'texto': "Escribe el comentario."})
        m = servicios.registrar(request.user, 'COMENTARIO', solicitud=s, texto=texto[:4000])
        return Response(MovimientoSerializer(m).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def convertir(self, request, pk=None):
        s = self.get_object()
        if not puede_cambiar_solicitud(request.user, s):
            raise PermissionDenied("La convierte su departamento (su responsable o quien lo gestiona).")
        if s.estado != 'APROBADA':
            raise ValidationError({'estado': "Solo una solicitud aprobada por el cliente se convierte en proyecto u orden."})
        if request.data.get('orden'):
            from apps.operaciones.models import OrdenTrabajo
            orden = get_object_or_404(OrdenTrabajo, pk=request.data['orden'])
            if orden.cliente_id != s.cliente_id:
                raise ValidationError({'orden': "La orden es de otro cliente."})
            servicios.enlazar_orden(s, orden, request.user)
        else:
            servicios.convertir_en_proyecto(s, request.user)
        s.refresh_from_db()
        return Response(self.get_serializer(s).data)
