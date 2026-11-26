from django.db.models import Count, Q, Sum
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
from .models import SERVICIOS, InteraccionComercial, Oportunidad, SolicitudServicio
from .permisos import es_comercial, filtro_solicitudes, puede_cambiar_oportunidad, puede_cambiar_solicitud
from .serializers import SERVICIOS_LISTA, InteraccionSerializer, MovimientoSerializer, OportunidadSerializer, SolicitudSerializer

CAMPOS_OPORTUNIDAD = ['titulo', 'necesidades', 'departamento', 'responsable', 'estado', 'fecha_contacto', 'proximo_seguimiento',
                      'motivo_no_concretado', 'cliente', 'prospecto_nombre', 'prospecto_contacto', 'prospecto_telefono',
                      'prospecto_correo', 'prospecto_rnc', 'servicios_interes', 'valor_estimado']
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


def _fila_cliente(c):
    return {'id': c.id, 'nombre': c.nombre, 'rnc': c.rnc, 'contacto': c.contacto, 'telefono': c.telefono, 'correo': c.correo,
            'activo': c.activo}


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
        elif p.get('vista') in ('aprobadas', 'ganadas'):
            qs = qs.filter(estado='APROBADA')
        elif p.get('vista') in ('no_concretadas', 'perdidas'):
            qs = qs.filter(estado='NO_CONCRETADA')
        elif p.get('vista') == 'seguimiento':
            qs = qs.exclude(estado__in=Oportunidad.CERRADOS).filter(proximo_seguimiento__lte=timezone.localdate())
        if p.get('tipo') == 'prospecto':
            qs = qs.filter(cliente__isnull=True)
        elif p.get('tipo') == 'cliente':
            qs = qs.filter(cliente__isnull=False)
        if p.get('q'):
            qs = qs.filter(Q(titulo__icontains=p['q']) | Q(codigo__icontains=p['q']) | Q(cliente__nombre__icontains=p['q'])
                           | Q(prospecto_nombre__icontains=p['q']))
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
            servicios.avisar([o.responsable], 'COMERCIAL', f"Oportunidad a tu cargo: {o.nombre_cliente}", f"{o.codigo} · {o.titulo}",
                             enlace=f"/oportunidades?oportunidad={o.pk}", excepto=user)

    def update(self, request, *args, **kwargs):
        o = self.get_object()
        s = self.get_serializer(o, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        datos = {k: v for k, v in s.validated_data.items() if k in CAMPOS_OPORTUNIDAD}
        responsable_antes = o.responsable_id
        o, cambios = servicios.guardar_cambios(o, datos, request.user, motivo=(request.data.get('motivo') or datos.get('motivo_no_concretado') or '').strip())
        if 'responsable' in cambios and o.responsable_id and o.responsable_id != responsable_antes:
            servicios.avisar([o.responsable], 'COMERCIAL', f"Oportunidad a tu cargo: {o.nombre_cliente}", f"{o.codigo} · {o.titulo}",
                             enlace=f"/oportunidades?oportunidad={o.pk}", excepto=request.user)
        return Response(self.get_serializer(o).data)

    def destroy(self, request, *args, **kwargs):
        o = self.get_object()
        if not es_administrador(request.user):
            raise PermissionDenied("Eliminar oportunidades es de Dirección. Márcala como «Perdida».")
        if o.solicitudes.exists():
            return Response({"detail": "Tiene solicitudes de servicio: márcala como «Perdida»."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        o = self.get_object()
        datos = self.get_serializer(o).data
        datos['solicitudes'] = SolicitudSerializer(o.solicitudes.select_related('cliente', 'departamento', 'responsable', 'creado_por',
                                                                                'proyecto', 'orden', 'oportunidad'),
                                                   many=True, context={'request': request}).data
        datos['historial'] = MovimientoSerializer(o.movimientos.select_related('usuario'), many=True).data
        datos['interacciones'] = InteraccionSerializer(o.interacciones.select_related('usuario', 'registrado_por'), many=True).data
        return Response(datos)

    @action(detail=True, methods=['get', 'post'])
    def interacciones(self, request, pk=None):
        """Llamadas, reuniones, correos, WhatsApp y propuestas con el posible cliente. POST registra una nueva."""
        o = self.get_object()
        if request.method == 'GET':
            return Response(InteraccionSerializer(o.interacciones.select_related('usuario', 'registrado_por'), many=True).data)
        if not puede_cambiar_oportunidad(request.user, o):
            raise PermissionDenied("No puedes registrar seguimientos en esta oportunidad.")
        ser = InteraccionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        datos = dict(ser.validated_data)
        if datos.get('usuario') is None:
            datos['usuario'] = request.user
        proximo = None
        if request.data.get('proximo_seguimiento'):
            s = self.get_serializer(o, data={'proximo_seguimiento': request.data['proximo_seguimiento']}, partial=True)
            s.is_valid(raise_exception=True)
            proximo = s.validated_data.get('proximo_seguimiento')
        i = servicios.registrar_interaccion(o, request.user, datos)
        if proximo:  # el próximo seguimiento queda agendado en la misma acción
            servicios.guardar_cambios(o, {'proximo_seguimiento': proximo}, request.user)
        return Response(InteraccionSerializer(i).data, status=status.HTTP_201_CREATED)

    @action(detail=True)
    def coincidencias(self, request, pk=None):
        """Antes de convertir un prospecto: clientes ya registrados con el mismo nombre o RNC (iguales) o parecidos."""
        o = self.get_object()
        iguales, parecidos = servicios.coincidencias_cliente(o.prospecto_nombre, o.prospecto_rnc)
        return Response({'iguales': [_fila_cliente(c) for c in iguales], 'parecidos': [_fila_cliente(c) for c in parecidos]})

    @action(detail=True, methods=['post'])
    def convertir_cliente(self, request, pk=None):
        """Convierte el posible cliente en cliente registrado: enlaza uno existente (`cliente`) o lo crea con los datos del prospecto."""
        from apps.operaciones.models import Cliente
        o = self.get_object()
        if not puede_cambiar_oportunidad(request.user, o):
            raise PermissionDenied("No puedes cambiar esta oportunidad.")
        if not o.es_prospecto:
            raise ValidationError({'cliente': f"Esta oportunidad ya está enlazada al cliente {o.cliente.nombre}."})
        if o.estado == 'NO_CONCRETADA':
            raise ValidationError({'estado': "La oportunidad está perdida: no se convierte en cliente."})
        existente = get_object_or_404(Cliente, pk=request.data['cliente']) if request.data.get('cliente') else None
        try:
            _, nuevo = servicios.convertir_en_cliente(o, request.user, existente)
        except ValueError as e:
            iguales = e.args[0]
            if not iguales:
                raise ValidationError({'prospecto_nombre': "Escribe el nombre del posible cliente antes de registrarlo."})
            return Response({'detail': "Ya hay un cliente registrado con ese nombre o RNC. Enlázalo en vez de crear uno repetido.",
                             'iguales': [_fila_cliente(c) for c in iguales]}, status=status.HTTP_409_CONFLICT)
        o.refresh_from_db()
        datos = self.get_serializer(o).data
        datos['cliente_nuevo'] = nuevo
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
        # Los 6 estados del flujo; el estado anterior («Evaluación») solo aparece si todavía queda alguna oportunidad en él
        estados = [{'codigo': c, 'nombre': n, 'total': por_estado.get(c, 0)} for c, n in Oportunidad.ESTADOS
                   if c in Oportunidad.ESTADOS_VIGENTES or por_estado.get(c)]
        abiertas = qs.exclude(estado__in=Oportunidad.CERRADOS)
        return Response({
            'estados': estados,
            'pendientes': abiertas.count(),
            'ganadas': por_estado.get('APROBADA', 0),
            'perdidas': por_estado.get('NO_CONCRETADA', 0),
            'prospectos': abiertas.filter(cliente__isnull=True).count(),
            'valor_abierto': abiertas.aggregate(t=Sum('valor_estimado'))['t'] or 0,
            'valor_ganado': qs.filter(estado='APROBADA').aggregate(t=Sum('valor_estimado'))['t'] or 0,
            'tipos_interaccion': [{'codigo': c, 'nombre': n} for c, n in InteraccionComercial.TIPOS],
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
        if oportunidad and cliente is None:
            raise ValidationError({'oportunidad': "Todavía es un posible cliente: primero conviértelo en cliente. Mientras tanto, anota "
                                                  "en la oportunidad los servicios que le interesan."})
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
