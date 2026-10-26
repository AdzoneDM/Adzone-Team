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
from .formularios import catalogo
from .models import ArchivoOrden, Cliente, OrdenTrabajo, Proyecto
from .permisos import (
    departamentos_a_cargo, es_finanzas, filtro_ordenes, filtro_proyectos, gestiona_algo, puede_gestionar_orden,
    puede_gestionar_proyecto,
)
from .serializers import (
    AprobarSerializer, ArchivoSerializer, ClienteSerializer, ComentarioSerializer, EventoSerializer, OrdenSerializer,
    ProyectoSerializer,
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
            'ordenes': OrdenSerializer(ordenes.prefetch_related('equipo', 'tareas__pasos', 'facturas')[:50], many=True,
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
            'equipo', 'tareas__pasos', 'facturas')
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


# ------------------------------------------------------------------ Órdenes de trabajo
class OrdenViewSet(viewsets.ModelViewSet):
    serializer_class = OrdenSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        qs = OrdenTrabajo.objects.select_related('cliente', 'proyecto', 'departamento', 'solicitada_por', 'responsable',
                                                 'aprobada_por')
        qs = _filtrar(qs, filtro_ordenes(user)).prefetch_related('equipo', 'tareas__pasos', 'facturas')
        p = self.request.query_params
        for campo in ('departamento', 'responsable', 'cliente', 'proyecto'):
            if p.get(campo):
                qs = qs.filter(**{f"{campo}_id": p[campo]})
        if p.get('tipo'):
            qs = qs.filter(tipo__in=p['tipo'].split(','))
        if p.get('estado'):
            qs = qs.filter(estado__in=p['estado'].split(','))
        if p.get('abiertas') == '1':
            qs = qs.filter(estado__in=OrdenTrabajo.ABIERTAS)
        if p.get('mias') == '1':
            qs = qs.filter(Q(responsable=user) | Q(equipo=user) | Q(solicitada_por=user)).distinct()
        if p.get('vencidas') == '1':
            qs = qs.filter(estado__in=['APROBADA', 'EN_PRODUCCION', 'CONTROL_CALIDAD', 'EN_PAUSA'],
                           fecha_compromiso__lt=timezone.localdate())
        if p.get('desde') and p.get('hasta'):
            qs = qs.filter(Q(fecha_compromiso__range=(p['desde'], p['hasta'])) |
                           Q(fecha_compromiso__isnull=True, fecha_requerida__range=(p['desde'], p['hasta'])))
        if p.get('q'):
            q = p['q']
            qs = qs.filter(Q(numero__icontains=q) | Q(titulo__icontains=q) | Q(cliente__nombre__icontains=q))
        return qs

    def perform_create(self, serializer):
        orden = serializer.save(solicitada_por=self.request.user)
        servicios.al_crear(orden, self.request.user)

    def perform_update(self, serializer):
        orden = serializer.instance
        if not self.get_serializer().get_puedo_editar(orden):
            raise PermissionDenied("Esta orden ya la gestiona su departamento; pide los cambios en los comentarios.")
        cambios = [c for c in ('titulo', 'descripcion', 'detalles', 'prioridad', 'fecha_requerida', 'monto', 'cliente', 'proyecto')
                   if c in serializer.validated_data and serializer.validated_data[c] != getattr(orden, c)]
        orden = serializer.save()
        if cambios:
            servicios.registrar(orden, self.request.user, "Orden editada", ", ".join(cambios))

    def destroy(self, request, *args, **kwargs):
        orden = self.get_object()
        if orden.estado != 'SOLICITADA' or not (puede_gestionar_orden(request.user, orden) or orden.solicitada_por_id == request.user.pk):
            return Response({"detail": "Solo se borra una orden recién pedida. Si ya avanzó, cancélala."},
                            status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    def _gestionar(self, orden):
        if not puede_gestionar_orden(self.request.user, orden):
            raise PermissionDenied(f"Esto lo hace quien gestiona {orden.departamento}.")

    def _respuesta(self, orden):
        orden.refresh_from_db()
        return Response(self.get_serializer(self.get_queryset().get(pk=orden.pk)).data)

    @action(detail=False)
    def catalogo(self, request):
        return Response(catalogo())

    @action(detail=False)
    def resumen(self, request):
        """Números del tablero: abiertas, vencidas, para hoy y cumplimiento del mes."""
        qs = self.get_queryset()
        hoy = timezone.localdate()
        inicio_mes = hoy.replace(day=1)
        abiertas = [o for o in qs if o.estado in OrdenTrabajo.ABIERTAS]
        entregadas = [o for o in qs if o.estado == 'ENTREGADA' and o.fecha_entrega and o.fecha_entrega >= inicio_mes]
        a_tiempo = [o for o in entregadas if o.a_tiempo]
        ciclos = [(o.fecha_entrega - o.fecha_creacion.date()).days for o in entregadas]
        por_estado, por_tipo = {}, {}
        for o in abiertas:
            por_estado[o.estado] = por_estado.get(o.estado, 0) + 1
            por_tipo[o.tipo] = por_tipo.get(o.tipo, 0) + 1
        return Response({
            'abiertas': len(abiertas),
            'por_aprobar': por_estado.get('SOLICITADA', 0),
            'vencidas': sum(o.vencida for o in abiertas),
            'para_hoy': sum((o.fecha_compromiso == hoy) for o in abiertas),
            'entregadas_mes': len(entregadas),
            'a_tiempo_pct': round(100 * len(a_tiempo) / len(entregadas)) if entregadas else None,
            'ciclo_promedio_dias': round(sum(ciclos) / len(ciclos), 1) if ciclos else None,
            'por_estado': por_estado,
            'por_tipo': por_tipo,
        })

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        orden = self.get_object()
        self._gestionar(orden)
        if orden.estado != 'SOLICITADA':
            return Response({"detail": "Solo se aprueban órdenes solicitadas."}, status=status.HTTP_400_BAD_REQUEST)
        s = AprobarSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        servicios.aprobar(orden, request.user, v['responsable'], v.get('equipo', []), v['fecha_compromiso'],
                          v.get('pasos'), v['crear_tarea'])
        return self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def mover(self, request, pk=None):
        orden = self.get_object()
        nuevo = request.data.get('estado')
        if nuevo not in dict(OrdenTrabajo.ESTADOS):
            return Response({"detail": "Estado desconocido."}, status=status.HTTP_400_BAD_REQUEST)
        es_responsable = request.user.pk in orden.participantes_ids()
        # El responsable puede pasar su orden a producción o a calidad; lo demás es de quien gestiona.
        if not (puede_gestionar_orden(request.user, orden) or (es_responsable and nuevo in ('EN_PRODUCCION', 'CONTROL_CALIDAD'))):
            raise PermissionDenied(f"Esto lo hace quien gestiona {orden.departamento}.")
        if nuevo == 'APROBADA' and orden.estado == 'SOLICITADA':
            return Response({"detail": "Para aprobar, usa «Aprobar»: hay que elegir responsable y fecha."},
                            status=status.HTTP_400_BAD_REQUEST)
        if nuevo == 'ENTREGADA':
            return Response({"detail": "Para entregar, usa «Entregar» y anota quién recibe."}, status=status.HTTP_400_BAD_REQUEST)
        if nuevo == 'CANCELADA':
            return Response({"detail": "Para cancelar, usa «Cancelar» y escribe el motivo."}, status=status.HTTP_400_BAD_REQUEST)
        error = servicios.cambiar_estado(orden, nuevo, request.user, request.data.get('detalle', ''))
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        return self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def reanudar(self, request, pk=None):
        orden = self.get_object()
        self._gestionar(orden)
        if orden.estado != 'EN_PAUSA':
            return Response({"detail": "La orden no está en pausa."}, status=status.HTTP_400_BAD_REQUEST)
        destino = orden.estado_antes_pausa if orden.estado_antes_pausa in ('APROBADA', 'EN_PRODUCCION') else 'EN_PRODUCCION'
        servicios.cambiar_estado(orden, destino, request.user, "Reanudada", forzar=True)
        return self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def entregar(self, request, pk=None):
        orden = self.get_object()
        if not (puede_gestionar_orden(request.user, orden) or request.user.pk in orden.participantes_ids()):
            raise PermissionDenied("Entrega quien tiene la orden a cargo o quien gestiona el departamento.")
        recibido = (request.data.get('recibido_por') or '').strip()
        if len(recibido) < 2:
            return Response({"recibido_por": ["Anota quién recibe el trabajo."]}, status=status.HTTP_400_BAD_REQUEST)
        if orden.estado != 'LISTA':
            return Response({"detail": "Primero tiene que estar «Lista para entregar»."}, status=status.HTTP_400_BAD_REQUEST)
        error = servicios.entregar(orden, request.user, recibido, request.data.get('nota', ''))
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        return self._respuesta(orden)

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        orden = self.get_object()
        puede = puede_gestionar_orden(request.user, orden) or (orden.estado == 'SOLICITADA' and orden.solicitada_por_id == request.user.pk)
        if not puede:
            raise PermissionDenied("No puedes cancelar esta orden.")
        motivo = (request.data.get('motivo') or '').strip()
        if len(motivo) < 3:
            return Response({"motivo": ["Escribe por qué se cancela."]}, status=status.HTTP_400_BAD_REQUEST)
        orden.motivo_cancelacion = motivo
        orden.save(update_fields=['motivo_cancelacion'])
        error = servicios.cambiar_estado(orden, 'CANCELADA', request.user, motivo)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        orden.tareas.filter(estado__in=['PENDIENTE', 'EN_PROGRESO']).update(estado='CANCELADA')
        return self._respuesta(orden)

    @action(detail=True)
    def historial(self, request, pk=None):
        orden = self.get_object()
        return Response(EventoSerializer(orden.eventos.select_related('usuario'), many=True).data)

    @action(detail=True)
    def completo(self, request, pk=None):
        """Todo lo de la orden de una vez: datos, tareas, archivos, comentarios e historial."""
        from apps.desempeno.serializers import TareaSerializer
        orden = self.get_object()
        tareas = orden.tareas.select_related('colaborador', 'asignada_por').prefetch_related('companeros', 'pasos', 'evidencias')
        datos = {
            'orden': self.get_serializer(orden).data,
            'formulario': next((t for t in catalogo() if t['tipo'] == orden.tipo), None),
            'tareas': TareaSerializer(tareas, many=True, context={'request': request}).data,
            'archivos': ArchivoSerializer(orden.archivos.select_related('subido_por'), many=True).data,
            'comentarios': ComentarioSerializer(orden.comentarios.select_related('autor'), many=True,
                                                context={'request': request}).data,
            'historial': EventoSerializer(orden.eventos.select_related('usuario'), many=True).data,
        }
        if es_finanzas(request.user):
            datos['facturas'] = [{'id': f.id, 'numero': f.numero, 'estado': f.estado, 'total': f.total, 'saldo': f.saldo}
                                 for f in orden.facturas.all()]
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
            return Response({"detail": "Elige al menos un archivo."}, status=status.HTTP_400_BAD_REQUEST)
        if len(archivos) > 10:
            return Response({"detail": "Como máximo 10 archivos a la vez."}, status=status.HTTP_400_BAD_REQUEST)
        for f in archivos:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in EXTENSIONES:
                return Response({"detail": f"«{f.name}»: ese tipo de archivo no se acepta."}, status=status.HTTP_400_BAD_REQUEST)
            if f.size > MAX_MB * 1024 * 1024:
                return Response({"detail": f"«{f.name}» pesa más de {MAX_MB} MB. Compártelo por enlace en un comentario."},
                                status=status.HTTP_400_BAD_REQUEST)
        nuevos = [ArchivoOrden.objects.create(orden=orden, archivo=f, nombre_original=f.name[:255],
                                              tipo=(f.content_type or mimetypes.guess_type(f.name)[0] or '')[:100],
                                              tamano=f.size, subido_por=request.user) for f in archivos]
        servicios.registrar(orden, request.user, f"Subió {len(nuevos)} archivo(s)", ", ".join(a.nombre_original for a in nuevos))
        return Response(ArchivoSerializer(nuevos, many=True).data, status=status.HTTP_201_CREATED)


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
            Q(numero__icontains=q) | Q(titulo__icontains=q) | Q(cliente__nombre__icontains=q))[:6]:
        res.append({'tipo': 'orden', 'id': o.pk, 'titulo': f"{o.numero} · {o.titulo}", 'sub': f"{o.cliente} · {o.get_estado_display()}",
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

