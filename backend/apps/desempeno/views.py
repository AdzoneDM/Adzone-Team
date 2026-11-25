import csv
import mimetypes
import os
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.models import Departamento
from apps.kpis.models import KPIAsignado
from apps.tiempo import servicios as cronometro
from . import servicios
from .models import (
    ConfiguracionDesempeno, EmpleadoDelMes, EsperaAsignacion, EvidenciaArchivo, HistorialTarea, Notificacion, ReferenciaArchivo, ResultadoKPI,
    Tarea, TareaRecurrente,
)
from .permisos import (
    EsAdministrador, tiene_otras_areas, tiene_propias, asignables, equipo_gestionable, es_administrador, por_validar, puede_asignar_a, puede_autovalidar, puede_gestionar,
    puede_eliminar_tarea, puede_gestionar_tarea, puede_revisar, puede_revisar_tarea, puede_validar, puesto_de, revisables, revisores_posibles,
    revisores_propias_ids, subordinados,
)
from .puntaje import calcular_ranking, filtrar_grupo, rango_del_mes, sin_evaluar
from .serializers import (
    ConfiguracionSerializer, EmpleadoDelMesSerializer, EntregaSerializer, HistorialSerializer, NotificacionSerializer,
    MAX_REFERENCIAS_POR_TAREA, ReaperturaSerializer, RechazoSerializer, ReferenciasSerializer, ResultadoKPISerializer,
    validar_archivos_referencia, TareaRecurrenteSerializer, TareaSerializer,
    ValidacionSerializer,
    ComentarioTareaSerializer, NuevoComentarioSerializer,
)


def periodo_desde_mes(mes):
    """Convierte 'AAAA-MM' en el primer día de ese mes. Sin valor, usa el mes actual."""
    if not mes:
        return timezone.localdate().replace(day=1)
    try:
        return datetime.strptime(mes, '%Y-%m').date()
    except ValueError:
        raise serializers.ValidationError({"mes": "Formato esperado: AAAA-MM."})


def _nombre(usuario):
    return usuario.get_full_name() or usuario.username


# ===========================================================================
# Tareas
# ===========================================================================
class TareaViewSet(viewsets.ModelViewSet):
    """
    - El colaborador ve sus tareas, las inicia y las entrega con evidencia (nota, enlace, fotos).
    - El supervisor directo (o el administrador) asigna, valida, devuelve, reabre o cancela.
    - Nadie valida su propio trabajo. Solo las tareas validadas cuentan para el puntaje y los KPIs.
    """
    serializer_class = TareaSerializer
    filterset_fields = ['colaborador', 'estado', 'prioridad', 'kpi_asignado']
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        queryset = Tarea.objects.select_related(
            'colaborador__perfil__puesto_trabajo__departamento', 'asignada_por', 'validada_por',
            'kpi_asignado__plantilla_kpi', 'proyecto', 'orden', 'oa',
        ).prefetch_related('evidencias', 'referencias', 'pasos', 'companeros')
        if not es_administrador(user):
            subs = equipo_gestionable(user, 'equipo.ver')
            queryset = queryset.filter(Q(colaborador=user) | Q(companeros=user) | Q(colaborador__in=subs) | Q(asignada_por=user)).distinct()

        params = self.request.query_params
        ambito = params.get('ambito')
        if ambito == 'mias':
            queryset = queryset.filter(Q(colaborador=user) | Q(companeros=user)).distinct()
        elif ambito == 'equipo':
            # «Mi equipo»: las tareas de toda su gente (directa o más abajo en el organigrama) y también las suyas, todo en un solo lugar
            queryset = queryset.filter(Q(colaborador__in=equipo_gestionable(user)) | Q(colaborador=user) | Q(companeros=user) | Q(asignada_por=user)).distinct()
        elif ambito == 'por_validar':
            queryset = por_validar(queryset, user)

        if params.get('asignadas') == '1':   # solo las que yo asigné a otras personas (para darles seguimiento)
            queryset = queryset.filter(asignada_por=user).exclude(colaborador=user)

        if params.get('mes'):
            queryset = queryset.filter(fecha_limite__range=rango_del_mes(periodo_desde_mes(params['mes'])))
        if params.get('departamento'):
            queryset = queryset.filter(colaborador__perfil__puesto_trabajo__departamento_id=params['departamento'])
        if params.get('buscar'):
            queryset = queryset.filter(titulo__icontains=params['buscar'][:100])
        if params.get('vencidas') == '1':
            queryset = queryset.filter(estado__in=['PENDIENTE', 'EN_PROGRESO'], fecha_limite__lt=timezone.localdate())
        if params.get('proyecto'):
            queryset = queryset.filter(proyecto_id=params['proyecto'])
        if params.get('orden'):
            queryset = queryset.filter(orden_id=params['orden'])
        if params.get('desde') and params.get('hasta'):
            queryset = queryset.filter(fecha_limite__range=(params['desde'], params['hasta']))
        return queryset

    def list(self, request, *args, **kwargs):
        servicios.generar_recurrentes_si_toca()
        return super().list(request, *args, **kwargs)

    def _exigir_gestion(self, colaborador, tarea=None):
        """Asignar a su equipo; o, con «Asignar tareas a otras áreas», a cualquier otra área (menos Call Center y Dirección).
        Sobre una tarea ya creada: su supervisor, o quien la asignó entre áreas."""
        u = self.request.user
        if puede_gestionar(u, colaborador, 'tareas.asignar') or (puede_asignar_a(u, colaborador) and (tarea is None or tarea.asignada_por_id == u.pk)):
            return
        raise PermissionDenied("No puedes asignarle tareas a esta persona (Call Center y Dirección no reciben tareas de otras áreas)."
                               if tiene_otras_areas(u) else "Solo quien tiene permiso para asignar tareas a esta persona puede hacerlo.")

    def _exigir_participante(self, tarea, que="trabajar"):
        if self.request.user.pk not in tarea.participantes_ids():
            raise PermissionDenied(f"Solo quien tiene asignada la tarea puede {que}la.")

    def _guardar_referencias(self, tarea, archivos, momento, nota=''):
        """Adjunta archivos de referencia a la tarea. Devuelve cuántos se guardaron."""
        if tarea.referencias.count() + len(archivos) > MAX_REFERENCIAS_POR_TAREA:
            raise serializers.ValidationError({"archivos": f"Una tarea admite hasta {MAX_REFERENCIAS_POR_TAREA} archivos de referencia."})
        for archivo in archivos:
            ReferenciaArchivo.objects.create(
                tarea=tarea, archivo=archivo, nombre_original=archivo.name[:255], nota=nota[:200], momento=momento,
                tipo=(getattr(archivo, 'content_type', '') or mimetypes.guess_type(archivo.name)[0] or '')[:100],
                tamano=archivo.size, ronda=tarea.rondas_revision, subido_por=self.request.user)
        return len(archivos)

    @action(detail=True, methods=['post'])
    def referencias(self, request, pk=None):
        """Quien asigna o supervisa adjunta un boceto, una imagen o un PDF de referencia (al asignar o al corregir)."""
        tarea = self.get_object()
        self._exigir_gestion(tarea.colaborador, tarea)
        if tarea.estado in ('COMPLETADA', 'CANCELADA'):
            return Response({"detail": "Esta tarea ya terminó: no se le agregan referencias."}, status=status.HTTP_400_BAD_REQUEST)
        datos = ReferenciasSerializer(data={'archivos': request.FILES.getlist('archivos'), 'nota': request.data.get('nota', ''),
                                            'momento': request.data.get('momento') or 'ASIGNACION'})
        datos.is_valid(raise_exception=True)
        n = self._guardar_referencias(tarea, datos.validated_data['archivos'], datos.validated_data['momento'], datos.validated_data.get('nota', ''))
        servicios.al_referenciar(tarea, request.user, n)
        return self._respuesta(tarea)

    def _exigir_revision(self, tarea, validando=False):
        # Una tarea que la persona se asignó a sí misma la puede validar ella (autovalidación); devolverla o reabrirla no.
        if self.request.user.pk in tarea.participantes_ids() and not (validando and puede_autovalidar(self.request.user, tarea)):
            raise PermissionDenied("Nadie puede devolver ni reabrir su propia tarea; validar solo las que tú mismo te asignaste.")
        if not puede_revisar_tarea(self.request.user, tarea):
            raise PermissionDenied(f"Esta tarea la revisa {_nombre(tarea.revisor)}." if tarea.revisor_id
                                   else "Solo el supervisor directo o un administrador puede revisar esta tarea.")

    def _revisor_de(self, colaborador, revisor):
        """Una tarea que la persona se asigna a sí misma la valida quien ella elige entre los revisores configurados
        (por defecto Dirección). Si la asigna otra persona, la valida su supervisor como siempre."""
        if colaborador.pk != self.request.user.pk:
            return None
        if revisor is None:
            return None  # se valida ella misma (si tiene «Asignarse tareas») o su supervisor; el historial lo deja claro
        if revisor.pk == self.request.user.pk or revisor.pk not in revisores_propias_ids():
            raise serializers.ValidationError({"revisor": "Esa persona no puede validar tareas propias. Elige a otra."})
        return revisor

    def perform_create(self, serializer):
        self._exigir_gestion(serializer.validated_data['colaborador'])
        for companero in serializer.validated_data.get('companeros', []):
            self._exigir_gestion(companero)
        revisor = self._revisor_de(serializer.validated_data['colaborador'], serializer.validated_data.get('revisor'))
        serializer.validated_data['revisor'] = revisor
        puesto = puesto_de(self.request.user)
        tarea = serializer.save(asignada_por=self.request.user, departamento_origen=puesto.departamento if puesto else None)
        servicios.al_asignar(tarea, self.request.user)

    def perform_update(self, serializer):
        serializer.validated_data.pop('revisor', None)  # el revisor se elige al crear la tarea propia y no cambia
        self._exigir_gestion(serializer.instance.colaborador, serializer.instance)
        nuevo = serializer.validated_data.get('colaborador')
        if nuevo:
            self._exigir_gestion(nuevo)
        if serializer.instance.estado == 'COMPLETADA':
            raise PermissionDenied("Una tarea validada no se edita: primero hay que reabrirla.")
        for companero in serializer.validated_data.get('companeros', []):
            self._exigir_gestion(companero)
        # Cambiar fechas, prioridad o responsable exige decir por qué: queda en el historial junto con el antes y el después
        previos_criticos = [c for c in servicios.CAMPOS_CON_MOTIVO if c in serializer.validated_data and getattr(serializer.instance, c, None) != serializer.validated_data[c]]
        motivo = str(self.request.data.get('motivo') or '').strip()
        if previos_criticos and len(motivo) < 5:
            etiquetas = ', '.join(servicios.CAMPOS_CON_MOTIVO[c].lower() for c in previos_criticos)
            raise ValidationError({'motivo': [f"Cuéntanos por qué cambias {etiquetas} (mínimo 5 letras): le llega a quienes participan y queda en el historial."]})
        anterior = serializer.instance.colaborador
        antes = set(serializer.instance.companeros.values_list('pk', flat=True))
        previos = {c: getattr(serializer.instance, c, None) for c in {*servicios.CAMPOS_AVISO, *servicios.CAMPOS_CON_MOTIVO}}
        pasos_antes = list(serializer.instance.pasos.order_by('orden', 'id').values_list('texto', flat=True))
        tarea = serializer.save()
        pasos_despues = list(tarea.pasos.order_by('orden', 'id').values_list('texto', flat=True))
        cambiados = [c for c, v in previos.items() if c in serializer.validated_data and getattr(tarea, c, None) != v]
        nuevos = [u for u in tarea.companeros.all() if u.pk not in antes]
        if nuevos:
            servicios.avisar(nuevos, 'ASIGNADA', f"Te sumaron a una tarea: {tarea.titulo}",
                             f"Responsable: {_nombre(tarea.colaborador)}.", tarea=tarea, enlace='/mis-tareas',
                             excepto=self.request.user)
        detalle = servicios.detalle_de_cambios(previos, tarea, [c for c in serializer.validated_data if c in {*servicios.CAMPOS_DETALLE, *servicios.CAMPOS_LARGOS}], motivo if previos_criticos else '', pasos_antes, pasos_despues)
        servicios.registrar(tarea, self.request.user, 'EDITADA', detalle or f"Cambió: {', '.join(sorted(serializer.validated_data.keys()))}")
        if nuevo and nuevo.pk != anterior.pk:
            servicios.avisar([nuevo], 'ASIGNADA', f"Nueva tarea: {tarea.titulo}",
                             f"{_nombre(self.request.user)} te la asignó.", tarea=tarea, enlace='/mis-tareas',
                             excepto=self.request.user)
            servicios.cerrar_esperas([nuevo], tarea)
        else:
            servicios.al_modificar(tarea, self.request.user, cambiados, motivo if previos_criticos else '')
        if nuevos:
            servicios.cerrar_esperas(nuevos, tarea)

    def perform_destroy(self, instance):
        if instance.estado == 'COMPLETADA':
            raise PermissionDenied("Una tarea validada no se borra: ya cuenta en el historial. Puedes reabrirla o cancelarla.")
        if not puede_eliminar_tarea(self.request.user, instance):
            raise PermissionDenied("Para borrar tareas hace falta el permiso «Eliminar tareas». Puedes cancelarla: queda registrada.")
        instance.delete()

    def _respuesta(self, tarea):
        tarea = self.get_queryset().get(pk=tarea.pk)
        return Response(self.get_serializer(tarea).data)

    @action(detail=True, methods=['get'])
    def historial(self, request, pk=None):
        tarea = self.get_object()
        return Response(HistorialSerializer(tarea.historial.select_related('usuario'), many=True).data)

    @action(detail=True, methods=['get', 'post'])
    def comentarios(self, request, pk=None):
        """Conversación de la tarea: GET la lista; POST {texto, responde_a?} agrega un comentario. La ven y escriben solo quienes ven la tarea
        (el resto recibe «no encontrada»). Los comentarios no se editan ni se borran."""
        tarea = self.get_object()
        if request.method == 'POST':
            datos = NuevoComentarioSerializer(data=request.data)
            datos.is_valid(raise_exception=True)
            responde = None
            if datos.validated_data.get('responde_a'):
                responde = tarea.comentarios.filter(pk=datos.validated_data['responde_a']).first()
                if responde is None:
                    return Response({"responde_a": ["Ese comentario no es de esta tarea."]}, status=status.HTTP_400_BAD_REQUEST)
            c = servicios.comentar_tarea(tarea, request.user, datos.validated_data['texto'], responde)
            return Response(ComentarioTareaSerializer(c, context={'request': request}).data, status=status.HTTP_201_CREATED)
        lista = tarea.comentarios.select_related('autor', 'responde_a__autor')
        return Response(ComentarioTareaSerializer(lista, many=True, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def iniciar(self, request, pk=None):
        tarea = self.get_object()
        self._exigir_participante(tarea, "inicia")
        if tarea.estado != 'PENDIENTE':
            return Response({"detail": "La tarea ya fue iniciada."}, status=status.HTTP_400_BAD_REQUEST)
        tarea.estado = 'EN_PROGRESO'
        tarea.fecha_inicio_trabajo = tarea.fecha_inicio_trabajo or timezone.now()
        tarea.save()
        servicios.registrar(tarea, request.user, 'INICIADA')
        servicios.tras_cambio(tarea, request.user)
        # Empezar es poner el cronómetro en esta tarea (si corría en otra cosa, se guarda lo anterior).
        cronometro.iniciar(request.user, tarea=tarea)
        return self._respuesta(tarea)

    @action(detail=True, methods=['post'])
    def entregar(self, request, pk=None):
        tarea = self.get_object()
        self._exigir_participante(tarea, "entrega")
        if tarea.estado not in ('PENDIENTE', 'EN_PROGRESO'):
            return Response({"detail": "Esta tarea no se puede entregar en su estado actual."},
                            status=status.HTTP_400_BAD_REQUEST)
        datos = {
            'evidencia_nota': request.data.get('evidencia_nota', ''),
            'evidencia_enlace': request.data.get('evidencia_enlace', ''),
            'archivos': request.FILES.getlist('archivos') or request.FILES.getlist('evidencia_archivo'),
        }
        entrega = EntregaSerializer(data=datos)
        entrega.is_valid(raise_exception=True)
        datos = entrega.validated_data

        with transaction.atomic():
            tarea.evidencia_nota = datos.get('evidencia_nota', '').strip()
            tarea.evidencia_enlace = datos.get('evidencia_enlace', '')
            tarea.estado = 'EN_REVISION'
            tarea.fecha_completada = timezone.localdate()
            tarea.fecha_entrega_real = timezone.now()
            tarea.fecha_inicio_trabajo = tarea.fecha_inicio_trabajo or tarea.fecha_entrega_real
            tarea.comentario_revision = ''
            tarea.save()
            for archivo in datos.get('archivos', []):
                EvidenciaArchivo.objects.create(
                    tarea=tarea, archivo=archivo, nombre_original=archivo.name[:255],
                    tipo=(getattr(archivo, 'content_type', '') or mimetypes.guess_type(archivo.name)[0] or '')[:100],
                    tamano=archivo.size, ronda=tarea.rondas_revision, subido_por=request.user,
                )
            servicios.al_entregar(tarea, request.user)
            # Al entregar se detiene el cronómetro si corría en esta tarea.
            corriendo = cronometro.activo(request.user)
            if corriendo and corriendo.tarea_id == tarea.pk:
                cronometro.detener(corriendo)
        return self._respuesta(tarea)

    @action(detail=True, methods=['post'])
    def validar(self, request, pk=None):
        tarea = self.get_object()
        self._exigir_revision(tarea, validando=True)
        if tarea.estado != 'EN_REVISION':
            return Response({"detail": "Solo se pueden validar tareas entregadas."},
                            status=status.HTTP_400_BAD_REQUEST)
        validacion = ValidacionSerializer(data=request.data)
        validacion.is_valid(raise_exception=True)
        if tarea.oa_id:  # Orden de Área: validar es firmar el control de calidad (G3)
            from apps.operaciones.servicios_ot import ErrorFlujo, validar_g3
            try:
                validar_g3(tarea.oa, request.user, request.data.get('g3') or {},
                           validacion.validated_data.get('comentario_evaluacion', ''))
            except ErrorFlujo as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        tarea.calificacion_calidad = validacion.validated_data['calificacion_calidad']
        tarea.comentario_evaluacion = validacion.validated_data.get('comentario_evaluacion', '')
        tarea.estado = 'COMPLETADA'
        tarea.validada_por = request.user
        tarea.fecha_validacion = timezone.now()
        tarea.save()
        servicios.al_validar(tarea, request.user)
        return self._respuesta(tarea)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        tarea = self.get_object()
        self._exigir_revision(tarea)
        if tarea.estado != 'EN_REVISION':
            return Response({"detail": "Solo se pueden devolver tareas entregadas."},
                            status=status.HTTP_400_BAD_REQUEST)
        rechazo = RechazoSerializer(data=request.data)
        rechazo.is_valid(raise_exception=True)
        # Al devolverla se pueden adjuntar bocetos o imágenes de referencia para la corrección
        archivos = validar_archivos_referencia(request.FILES.getlist('archivos'))
        tarea.comentario_revision = rechazo.validated_data['comentario_revision']
        g3 = request.data.get('g3') or {}
        if isinstance(g3, str):  # con archivos la petición viaja como formulario: el G3 llega como texto JSON
            import json
            try:
                g3 = json.loads(g3)
            except ValueError:
                g3 = {}
        with transaction.atomic():
            if tarea.oa_id:
                from apps.operaciones.servicios_ot import rechazar_g3
                rechazar_g3(tarea.oa, request.user, g3, tarea.comentario_revision, request.data.get('causa_retrabajo') or None)
            tarea.estado = 'EN_PROGRESO'
            tarea.fecha_completada = None
            tarea.rondas_revision += 1
            tarea.save()
            n = self._guardar_referencias(tarea, archivos, 'CORRECCION') if archivos else 0
        servicios.al_devolver(tarea, request.user, referencias=n)
        return self._respuesta(tarea)

    @action(detail=True, methods=['post'])
    def reabrir(self, request, pk=None):
        """Corrige una validación hecha por error: la tarea vuelve a «En revisión» y deja de contar."""
        tarea = self.get_object()
        self._exigir_revision(tarea)
        if tarea.estado != 'COMPLETADA':
            return Response({"detail": "Solo se reabren tareas validadas."}, status=status.HTTP_400_BAD_REQUEST)
        datos = ReaperturaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        tarea.estado = 'EN_REVISION'
        tarea.calificacion_calidad = None
        tarea.validada_por = None
        tarea.fecha_validacion = None
        tarea.save()
        servicios.al_reabrir(tarea, request.user, datos.validated_data['motivo'])
        return self._respuesta(tarea)

    @action(detail=True, methods=['post'], url_path=r'pasos/(?P<paso_id>\d+)')
    def marcar_paso(self, request, pk=None, paso_id=None):
        """Marca o desmarca un paso del checklist. Solo quienes trabajan la tarea, y mientras está abierta."""
        tarea = self.get_object()
        self._exigir_participante(tarea, "marca")
        if tarea.estado not in ('PENDIENTE', 'EN_PROGRESO'):
            return Response({"detail": "Los pasos se marcan mientras la tarea está por hacer."}, status=status.HTTP_400_BAD_REQUEST)
        paso = tarea.pasos.filter(pk=paso_id).first()
        if paso is None:
            raise Http404
        paso.hecho = bool(request.data.get('hecho', not paso.hecho))
        paso.hecho_por = request.user if paso.hecho else None
        paso.fecha_hecho = timezone.now() if paso.hecho else None
        paso.save()
        if tarea.estado == 'PENDIENTE' and paso.hecho:
            tarea.estado = 'EN_PROGRESO'   # marcar un paso es empezar
            tarea.save(update_fields=['estado', 'fecha_modificacion'])
            servicios.registrar(tarea, request.user, 'INICIADA')
            servicios.tras_cambio(tarea, request.user)
        return self._respuesta(tarea)

    @action(detail=True, methods=['post'])
    def recordar(self, request, pk=None):
        """Recordatorio del supervisor al colaborador sobre una tarea abierta (llega a su campanita)."""
        tarea = self.get_object()
        self._exigir_revision(tarea)
        if tarea.estado not in ('PENDIENTE', 'EN_PROGRESO'):
            return Response({"detail": "Solo se recuerdan tareas por hacer."}, status=status.HTTP_400_BAD_REQUEST)
        motivo = servicios.recordar(tarea, request.user, (request.data.get('mensaje') or '').strip()[:500])
        if motivo:
            return Response({"detail": motivo}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        maximo = ConfiguracionDesempeno.actual().max_recordatorios
        enviados = servicios.recordatorios_enviados(tarea)
        return Response({"message": f"Le llegó el recordatorio a {_nombre(tarea.colaborador)}. Van {enviados}{f' de {maximo}' if maximo else ''}.",
                         "enviados": enviados, "maximo": maximo})

    @action(detail=True, methods=['post'])
    def bloquear(self, request, pk=None):
        """Quien la trabaja (o quien la asigna) la marca bloqueada con el motivo; se avisa al supervisor."""
        tarea = self.get_object()
        if request.user.pk not in tarea.participantes_ids():
            self._exigir_gestion(tarea.colaborador)
        if tarea.estado not in ('PENDIENTE', 'EN_PROGRESO'):
            return Response({"detail": "Solo se bloquea una tarea por hacer."}, status=status.HTTP_400_BAD_REQUEST)
        motivo = (request.data.get('motivo') or '').strip()[:1000]
        if len(motivo) < 5:
            return Response({"detail": "Escribe qué impide seguir (por ejemplo, «espero el logo del cliente»)."},
                            status=status.HTTP_400_BAD_REQUEST)
        tarea.estado = 'BLOQUEADA'
        tarea.motivo_bloqueo = motivo
        tarea.bloqueada_desde = timezone.now()
        tarea.save()
        servicios.al_bloquear(tarea, request.user)
        corriendo = cronometro.activo(request.user)
        if corriendo and corriendo.tarea_id == tarea.pk:
            cronometro.detener(corriendo)
        return self._respuesta(tarea)

    @action(detail=True, methods=['post'])
    def desbloquear(self, request, pk=None):
        tarea = self.get_object()
        if request.user.pk not in tarea.participantes_ids():
            self._exigir_gestion(tarea.colaborador)
        if tarea.estado != 'BLOQUEADA':
            return Response({"detail": "La tarea no está bloqueada."}, status=status.HTTP_400_BAD_REQUEST)
        tarea.estado = 'EN_PROGRESO'
        tarea.fecha_inicio_trabajo = tarea.fecha_inicio_trabajo or timezone.now()
        tarea.bloqueada_desde = None
        tarea.save()
        servicios.al_desbloquear(tarea, request.user, (request.data.get('nota') or '').strip()[:500])
        return self._respuesta(tarea)

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        tarea = self.get_object()
        self._exigir_gestion(tarea.colaborador)
        if tarea.estado in ('COMPLETADA', 'CANCELADA'):
            return Response({"detail": "Esta tarea ya está cerrada."}, status=status.HTTP_400_BAD_REQUEST)
        tarea.estado = 'CANCELADA'
        tarea.save()
        servicios.registrar(tarea, request.user, 'CANCELADA', request.data.get('motivo', ''))
        servicios.tras_cambio(tarea, request.user)
        return self._respuesta(tarea)


@api_view(['GET'])
def mis_revisores_view(request):
    """Quién puede validar las tareas que yo me asigno (para elegir al crear una tarea propia)."""
    return Response([{'id': u.pk, 'nombre': _nombre(u), 'puesto': getattr(getattr(getattr(u, 'perfil', None), 'puesto_trabajo', None), 'nombre', '')}
                     for u in revisores_posibles(request.user)])


@api_view(['GET', 'DELETE'])
def referencia_view(request, pk):
    """GET: entrega el archivo solo a quien trabaja la tarea o la supervisa. DELETE: lo quita quien lo subió o quien la asigna."""
    try:
        ref = ReferenciaArchivo.objects.select_related('tarea__colaborador').get(pk=pk)
    except ReferenciaArchivo.DoesNotExist:
        raise Http404
    tarea = ref.tarea
    es_participante = request.user.pk in tarea.participantes_ids()
    gestiona = puede_gestionar(request.user, tarea.colaborador, 'tareas.asignar') or puede_gestionar(request.user, tarea.colaborador)
    if not (es_participante or gestiona):
        raise Http404
    if request.method == 'DELETE':
        if not (ref.subido_por_id == request.user.pk or puede_gestionar(request.user, tarea.colaborador, 'tareas.asignar')):
            raise PermissionDenied("Solo quien la subió o quien asigna la tarea puede quitar esta referencia.")
        ref.archivo.delete(save=False)
        ref.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    if ref.purgado:
        return Response({'detail': 'Este video se borró solo para liberar espacio (pasaron los días de conservación después de validada la tarea).'}, status=status.HTTP_410_GONE)
    try:
        archivo = ref.archivo.open('rb')
    except (FileNotFoundError, ValueError):
        raise Http404
    tipo = mimetypes.guess_type(ref.archivo.name)[0] or 'application/octet-stream'
    from apps.core.archivos import entregar
    respuesta = entregar(archivo, ref.nombre_original or os.path.basename(ref.archivo.name), tipo, request)
    _pdf_incrustable(respuesta, tipo)
    respuesta['Cache-Control'] = 'private, max-age=3600'
    return respuesta


ACCIONES_QUE_REFRESCAN = ('ENTREGADA', 'VALIDADA', 'DEVUELTA', 'REABIERTA', 'CANCELADA')


def _pdf_incrustable(respuesta, tipo):
    """Un PDF de evidencia se puede ver dentro de la propia plataforma (vista previa): el `sandbox` general del resto de archivos impide que el visor de PDF del
    navegador funcione, y la cabecera «no incrustar» bloquearía el marco. Sigue sin ejecutar nada propio y solo se deja incrustar desde este mismo sitio."""
    if (tipo or '').lower().split(';')[0].strip() == 'application/pdf':
        respuesta['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:"
        respuesta['X-Frame-Options'] = 'SAMEORIGIN'


@api_view(['GET'])
def evidencia_archivo_view(request, pk):
    """Entrega una foto o PDF solo a quien tiene que ver con la tarea."""
    try:
        evidencia = EvidenciaArchivo.objects.select_related('tarea__colaborador').get(pk=pk)
    except EvidenciaArchivo.DoesNotExist:
        raise Http404
    tarea = evidencia.tarea
    if not (tarea.colaborador_id == request.user.pk or puede_gestionar(request.user, tarea.colaborador)):
        raise Http404
    if evidencia.purgado:
        return Response({'detail': 'Este video se borró solo para liberar espacio (pasaron los días de conservación después de validada la tarea).'}, status=status.HTTP_410_GONE)
    try:
        archivo = evidencia.archivo.open('rb')
    except (FileNotFoundError, ValueError):
        raise Http404
    tipo = mimetypes.guess_type(evidencia.archivo.name)[0] or 'application/octet-stream'
    from apps.core.archivos import entregar
    respuesta = entregar(archivo, evidencia.nombre_original or os.path.basename(evidencia.archivo.name), tipo, request)
    _pdf_incrustable(respuesta, tipo)
    respuesta['Cache-Control'] = 'private, max-age=3600'
    respuesta['X-Content-Type-Options'] = 'nosniff'
    return respuesta


# ===========================================================================
# Tareas recurrentes
# ===========================================================================
class TareaRecurrenteViewSet(viewsets.ModelViewSet):
    serializer_class = TareaRecurrenteSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = TareaRecurrente.objects.select_related('colaborador', 'kpi_asignado__plantilla_kpi')
        if es_administrador(user):
            return qs
        return qs.filter(colaborador__in=equipo_gestionable(user, 'tareas.asignar'))

    def _exigir(self, colaborador):
        if not puede_gestionar(self.request.user, colaborador, 'tareas.asignar'):
            raise PermissionDenied("Solo el supervisor directo o un administrador puede programar tareas para esta persona.")

    def perform_create(self, serializer):
        self._exigir(serializer.validated_data['colaborador'])
        serializer.save(creada_por=self.request.user)
        servicios.generar_recurrentes()

    def perform_update(self, serializer):
        self._exigir(serializer.instance.colaborador)
        if 'colaborador' in serializer.validated_data:
            self._exigir(serializer.validated_data['colaborador'])
        serializer.save()
        servicios.generar_recurrentes()

    def perform_destroy(self, instance):
        self._exigir(instance.colaborador)
        # Las tareas ya creadas se quedan; solo deja de generar nuevas.
        instance.delete()


# ===========================================================================
# Resultados de KPIs manuales
# ===========================================================================
class ResultadoKPIViewSet(viewsets.ModelViewSet):
    """El administrador registra los KPIs de entrada manual; cada colaborador consulta los suyos."""
    serializer_class = ResultadoKPISerializer
    filterset_fields = ['colaborador', 'kpi_asignado']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'lote']:
            return [EsAdministrador()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = ResultadoKPI.objects.select_related('colaborador', 'kpi_asignado__plantilla_kpi')
        mes = self.request.query_params.get('mes')
        if mes:
            queryset = queryset.filter(periodo=periodo_desde_mes(mes))
        if es_administrador(self.request.user):
            return queryset
        return queryset.filter(colaborador=self.request.user)

    @action(detail=False, methods=['get'])
    def planilla(self, request):
        """Todos los KPIs manuales del mes en una tabla: una fila por persona, una columna por KPI."""
        if not es_administrador(request.user):
            raise PermissionDenied("Solo un administrador anota los KPIs manuales.")
        periodo = periodo_desde_mes(request.query_params.get('mes'))
        departamento = request.query_params.get('departamento')
        personas = User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=False).select_related(
            'perfil__puesto_trabajo__departamento').order_by('first_name', 'username')
        if departamento:
            personas = personas.filter(perfil__puesto_trabajo__departamento_id=departamento)
        kpis = {}
        for kpi in KPIAsignado.objects.filter(activo=True, es_entrada_manual=True).select_related('plantilla_kpi'):
            kpis.setdefault(kpi.puesto_trabajo_id, []).append(kpi)
        existentes = {(r.colaborador_id, r.kpi_asignado_id): r
                      for r in ResultadoKPI.objects.filter(periodo=periodo)}
        filas = []
        for persona in personas:
            puesto = persona.perfil.puesto_trabajo
            celdas = []
            for kpi in kpis.get(puesto.id, []):
                r = existentes.get((persona.id, kpi.id))
                meta_defecto = kpi.meta_numerica if kpi.meta_numerica is not None else _numero(kpi.objetivo_meta)
                celdas.append({
                    'kpi_asignado': kpi.id, 'nombre': kpi.plantilla_kpi.nombre,
                    'unidad_medida': kpi.plantilla_kpi.unidad_medida, 'menor_es_mejor': kpi.plantilla_kpi.menor_es_mejor,
                    'ponderacion': float(kpi.ponderacion), 'objetivo': kpi.objetivo_meta,
                    'resultado_id': r.id if r else None,
                    'valor_meta': float(r.valor_meta) if r else (float(meta_defecto) if meta_defecto is not None else None),
                    'valor_real': float(r.valor_real) if r else None,
                    'cumplimiento': round(r.cumplimiento, 1) if r else None,
                })
            if celdas:
                filas.append({'colaborador': persona.id, 'nombre': _nombre(persona), 'puesto': puesto.nombre,
                              'departamento': puesto.departamento.nombre, 'kpis': celdas})
        return Response({'periodo': periodo.isoformat(), 'filas': filas})

    @action(detail=False, methods=['post'])
    def lote(self, request):
        """Guarda de una vez lo anotado en la planilla. Vacío = borrar el valor de ese mes."""
        periodo = periodo_desde_mes(request.data.get('mes'))
        guardados, borrados, errores = 0, 0, []
        with transaction.atomic():
            for item in request.data.get('resultados', []):
                try:
                    colaborador = User.objects.get(pk=item.get('colaborador'))
                    kpi = KPIAsignado.objects.select_related('plantilla_kpi').get(pk=item.get('kpi_asignado'))
                except (User.DoesNotExist, KPIAsignado.DoesNotExist, ValueError, TypeError):
                    errores.append("Persona o KPI inexistente.")
                    continue
                if colaborador.pk == request.user.pk:
                    errores.append(f"{_nombre(colaborador)}: nadie anota sus propios resultados.")
                    continue
                if puesto_de(colaborador) is None or kpi.puesto_trabajo_id != puesto_de(colaborador).id or not kpi.es_entrada_manual:
                    errores.append(f"{_nombre(colaborador)}: «{kpi.plantilla_kpi.nombre}» no es un KPI manual de su puesto.")
                    continue
                real, meta = item.get('valor_real'), item.get('valor_meta')
                existente = ResultadoKPI.objects.filter(kpi_asignado=kpi, colaborador=colaborador, periodo=periodo).first()
                if real in (None, ''):
                    if existente:
                        existente.delete()
                        borrados += 1
                    continue
                try:
                    real, meta = float(real), float(meta)
                except (TypeError, ValueError):
                    errores.append(f"{_nombre(colaborador)} · {kpi.plantilla_kpi.nombre}: escribe la meta y el valor como números.")
                    continue
                if real < 0 or meta < 0:
                    errores.append(f"{_nombre(colaborador)} · {kpi.plantilla_kpi.nombre}: no puede ser negativo.")
                    continue
                if existente:
                    existente.valor_real, existente.valor_meta = real, meta
                    existente.save()
                else:
                    ResultadoKPI.objects.create(kpi_asignado=kpi, colaborador=colaborador, periodo=periodo,
                                                valor_real=real, valor_meta=meta)
                guardados += 1
        return Response({'guardados': guardados, 'borrados': borrados, 'errores': errores},
                        status=status.HTTP_200_OK if not errores or guardados or borrados else status.HTTP_400_BAD_REQUEST)


def _numero(texto):
    try:
        return float(str(texto).replace(',', '.').strip().lstrip('<>=≤≥ '))
    except (TypeError, ValueError):
        return None


# ===========================================================================
# Empleado del Mes
# ===========================================================================
class EmpleadoDelMesViewSet(viewsets.ModelViewSet):
    """Muro de honor: todos pueden verlo; solo el administrador declara ganadores."""
    serializer_class = EmpleadoDelMesSerializer
    queryset = EmpleadoDelMes.objects.select_related('colaborador__perfil__puesto_trabajo', 'departamento')
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [EsAdministrador()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        mes = self.request.query_params.get('mes')
        if mes:
            queryset = queryset.filter(periodo=periodo_desde_mes(mes))
        return queryset

    def perform_create(self, serializer):
        periodo = serializer.validated_data['periodo']
        colaborador = serializer.validated_data['colaborador']
        departamento = serializer.validated_data.get('departamento')

        if EmpleadoDelMes.objects.filter(periodo=periodo, departamento=departamento).exists():
            ambito = f"el departamento {departamento.nombre}" if departamento else "toda la empresa"
            raise serializers.ValidationError(
                {"detail": f"Ya se declaró el Empleado del Mes de {ambito} para este periodo. Anúlalo primero si quieres cambiarlo."}
            )
        if periodo > timezone.localdate().replace(day=1):
            raise serializers.ValidationError({"detail": "Ese mes todavía no ha empezado."})

        fila = next((f for f in calcular_ranking(periodo) if f['colaborador_id'] == colaborador.id), None)
        if fila is None:
            raise serializers.ValidationError(
                {"detail": "Este colaborador no tiene evaluación (tareas o KPIs) en el periodo."}
            )
        if departamento and fila['departamento_id'] != departamento.id:
            raise serializers.ValidationError({"detail": "El colaborador no pertenece a ese departamento."})

        reconocimiento = serializer.save(puntaje=fila['puntaje_total'], declarado_por=self.request.user)
        ambito = f" de {departamento.nombre}" if departamento else ""
        mes = periodo.strftime('%m/%Y')
        servicios.avisar([colaborador], 'EMPLEADO_MES', f"¡Eres el Empleado del Mes{ambito}!",
                         f"{mes}. {reconocimiento.beneficio}".strip(), enlace='/')
        if not departamento:
            servicios.avisar(User.objects.filter(is_active=True).exclude(pk=colaborador.pk), 'EMPLEADO_MES',
                             f"Empleado del Mes: {_nombre(colaborador)}", f"Reconocimiento de {mes}.", enlace='/',
                             excepto=self.request.user)


# ===========================================================================
# Ranking, tablero, equipo, avisos y configuración
# ===========================================================================
def _grupo(request):
    """Los agentes de call center tienen su propio ranking: ?grupo=agentes. Por defecto, el resto del equipo."""
    return 'agentes' if request.query_params.get('grupo') == 'agentes' else 'empleados'


def _ranking_con_candidatos(periodo, grupo='empleados'):
    ranking = calcular_ranking(periodo, grupo=grupo)
    por_departamento = {}
    for fila in ranking:  # Ya viene ordenado: el primero elegible de cada departamento es su candidato
        if fila['departamento_id'] and fila['elegible'] and fila['departamento_id'] not in por_departamento:
            por_departamento[fila['departamento_id']] = {
                'departamento_id': fila['departamento_id'],
                'departamento': fila['departamento'],
                'candidato': fila,
            }
    general = next((f for f in ranking if f['elegible']), None)
    return ranking, general, sorted(por_departamento.values(), key=lambda d: d['departamento'])


@api_view(['GET'])
@permission_classes([EsAdministrador])
def ranking_view(request):
    """Ranking del mes con los candidatos sugeridos a Empleado del Mes (general y por departamento)."""
    periodo = periodo_desde_mes(request.query_params.get('mes'))
    grupo = _grupo(request)
    ranking, general, por_depto = _ranking_con_candidatos(periodo, grupo)
    config = ConfiguracionDesempeno.actual()
    return Response({
        'periodo': periodo.isoformat(),
        'mes_en_curso': periodo == timezone.localdate().replace(day=1),
        'ranking': ranking,
        'candidato_general': general,
        'candidatos_departamento': por_depto,
        'minimo_tareas': config.minimo_tareas_empleado_mes,
        'puntaje_minimo': config.puntaje_minimo,
        'minimo_tareas_evaluacion': config.minimo_tareas_evaluacion,
        'grupo': grupo,
        'sin_evaluar': sin_evaluar(periodo, ranking, grupo=grupo),
        'pendientes_validar': Tarea.objects.filter(estado='EN_REVISION', fecha_limite__range=rango_del_mes(periodo),
                                                   colaborador__in=filtrar_grupo(User.objects.all(), grupo)).count(),
    })


@api_view(['GET'])
@permission_classes([EsAdministrador])
def ranking_exportar_view(request):
    """El ranking del mes en CSV (se abre en Excel) para nómina y reconocimientos."""
    periodo = periodo_desde_mes(request.query_params.get('mes'))
    respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
    grupo = _grupo(request)
    respuesta['Content-Disposition'] = f'attachment; filename="ranking-{"call-center-" if grupo == "agentes" else ""}{periodo:%Y-%m}.csv"'
    respuesta.write('﻿')
    escritor = csv.writer(respuesta)
    config = ConfiguracionDesempeno.actual()
    evaluacion = {'CUMPLE': 'Cumple', 'BAJO_MINIMO': f'Bajo el mínimo ({config.puntaje_minimo})', 'POCOS_DATOS': 'Pocos datos'}
    escritor.writerow(['Posición', 'Colaborador', 'Puesto', 'Departamento', 'Puntaje total', 'Evaluación', 'Motivos',
                       'Puntaje tareas', 'Puntaje KPIs', 'Calidad y satisfacción', 'Asistencia', 'Tareas que cuentan', 'Tareas validadas', 'A tiempo',
                       'A la primera', 'Vencidas sin entregar', 'Calidad promedio', 'Bono sugerido (%)'])
    ranking = calcular_ranking(periodo, config=config, grupo=grupo)
    for f in ranking:
        t = f['tareas']
        escritor.writerow([f['posicion'], f['nombre'], f['puesto'] or '', f['departamento'] or '', f['puntaje_total'],
                           evaluacion[f['evaluacion']], '; '.join(f['motivos']),
                           '' if f['puntaje_tareas'] is None else f['puntaje_tareas'],
                           '' if f['puntaje_kpis'] is None else f['puntaje_kpis'],
                           '' if f.get('puntaje_calidad') is None else f['puntaje_calidad'],
                           '' if f.get('puntaje_asistencia') is None else f['puntaje_asistencia'],
                           t['total'], t['completadas'], t['a_tiempo'], t['a_la_primera'], t['vencidas'],
                           '' if t['calidad_promedio'] is None else t['calidad_promedio'], f['bono_sugerido']])
    for f in sin_evaluar(periodo, ranking, grupo=grupo):
        escritor.writerow(['', f['nombre'], f['puesto'], f['departamento'] or '', '', 'Sin evaluar',
                           f"Sin tareas vencidas ni validadas en el mes ({f['tareas_asignadas']} asignada(s)). "
                           f"Supervisor: {f['supervisor'] or 'sin supervisor'}",
                           '', '', '', '', 0, 0, 0, 0, 0, '', 0])
    return respuesta


@api_view(['GET'])
def mi_resumen_view(request):
    """Avance del mes, puntaje y KPIs del colaborador."""
    user = request.user
    periodo = periodo_desde_mes(request.query_params.get('mes'))
    inicio, fin = rango_del_mes(periodo)
    servicios.generar_recurrentes_si_toca()

    tareas = Tarea.objects.filter(Q(colaborador=user) | Q(companeros=user), fecha_limite__range=(inicio, fin)).exclude(estado='CANCELADA').distinct()
    hoy = timezone.localdate()
    conteo = {
        'total': tareas.count(),
        'validadas': tareas.filter(estado='COMPLETADA').count(),
        'en_revision': tareas.filter(estado='EN_REVISION').count(),
        'por_hacer': tareas.filter(estado__in=['PENDIENTE', 'EN_PROGRESO']).count(),
        'vencidas': tareas.filter(estado__in=['PENDIENTE', 'EN_PROGRESO'], fecha_limite__lt=hoy).count(),
    }
    # Cada quien se compara con su grupo: los agentes con los agentes, el resto con el resto
    ranking = calcular_ranking(periodo, grupo='agentes' if user.groups.filter(name='Agente Call Center').exists() else 'empleados')
    mi_fila = next((f for f in ranking if f['colaborador_id'] == user.id), None)
    puesto = puesto_de(user)

    return Response({
        'periodo': periodo.isoformat(),
        'tareas': conteo,
        'progreso': round(conteo['validadas'] / conteo['total'] * 100) if conteo['total'] else 0,
        'puntaje': mi_fila['puntaje_total'] if mi_fila else None,
        'puntaje_tareas': mi_fila['puntaje_tareas'] if mi_fila else None,
        'puntaje_kpis': mi_fila['puntaje_kpis'] if mi_fila else None,
        'detalle_tareas': mi_fila['tareas'] if mi_fila else None,
        'posicion': mi_fila['posicion'] if mi_fila else None,
        'evaluados': len(ranking),
        'kpis': mi_fila['kpis'] if mi_fila else [],
        'kpis_del_puesto': [
            {'nombre': k.plantilla_kpi.nombre, 'automatico': not k.es_entrada_manual, 'meta': k.objetivo_meta,
             'ponderacion': float(k.ponderacion)}
            for k in KPIAsignado.objects.filter(puesto_trabajo=puesto, activo=True).select_related('plantilla_kpi')
        ] if puesto else [],
        'por_validar': (
            por_validar(Tarea.objects.all(), user).count()
            if (puede_validar(user) or tiene_propias(user)) else 0
        ),
    })


@api_view(['GET'])
def tablero_view(request):
    """Inicio según el rol: el administrador ve la empresa; el supervisor, su equipo; todos, el Muro de Honor."""
    user = request.user
    periodo = periodo_desde_mes(request.query_params.get('mes'))
    inicio, fin = rango_del_mes(periodo)
    hoy = timezone.localdate()
    admin = es_administrador(user)

    ultimo_mes = (periodo.replace(day=1) - timedelta(days=1)).replace(day=1)
    muro = EmpleadoDelMes.objects.filter(periodo__in=[periodo, ultimo_mes]).select_related(
        'colaborador__perfil__puesto_trabajo', 'departamento')
    datos = {
        'periodo': periodo.isoformat(),
        'rol': 'administrador' if admin else ('supervisor' if puede_validar(user) else 'colaborador'),
        'muro': EmpleadoDelMesSerializer(muro, many=True).data,
        'proximas': TareaSerializer(
            Tarea.objects.filter(Q(colaborador=user) | Q(companeros=user), estado__in=['PENDIENTE', 'EN_PROGRESO']).distinct()
            .select_related('colaborador__perfil__puesto_trabajo__departamento', 'kpi_asignado__plantilla_kpi')
            .prefetch_related('evidencias', 'pasos', 'companeros').order_by('fecha_limite')[:5], many=True, context={'request': request}).data,
    }
    if not puede_validar(user):
        return Response(datos)

    equipo = equipo_gestionable(user).exclude(pk=user.pk)
    tareas = Tarea.objects.filter(colaborador__in=equipo, fecha_limite__range=(inicio, fin)).exclude(estado='CANCELADA')
    datos['equipo'] = {
        'personas': equipo.count(),
        'tareas': tareas.count(),
        'validadas': tareas.filter(estado='COMPLETADA').count(),
        'por_validar': Tarea.objects.filter(colaborador__in=equipo, estado='EN_REVISION').count(),
        'vencidas': tareas.filter(estado__in=['PENDIENTE', 'EN_PROGRESO'], fecha_limite__lt=hoy).count(),
        'en_plazo': tareas.filter(estado__in=['PENDIENTE', 'EN_PROGRESO'], fecha_limite__gte=hoy).count(),
    }
    # Quién necesita atención: vencidas sin entregar, de más a menos
    atrasados = (Tarea.objects.filter(colaborador__in=equipo, estado__in=['PENDIENTE', 'EN_PROGRESO'], fecha_limite__lt=hoy)
                 .values('colaborador').annotate(n=Count('id')).order_by('-n')[:6])
    nombres = {u.id: u for u in User.objects.filter(id__in=[a['colaborador'] for a in atrasados]).select_related('perfil__puesto_trabajo')}
    datos['atencion'] = [{'colaborador': a['colaborador'], 'nombre': _nombre(nombres[a['colaborador']]),
                          'puesto': getattr(puesto_de(nombres[a['colaborador']]), 'nombre', None), 'vencidas': a['n']}
                         for a in atrasados]

    ranking = calcular_ranking(periodo)
    ids_equipo = set(equipo.values_list('id', flat=True))
    propio = [f for f in ranking if f['colaborador_id'] in ids_equipo]
    datos['top'] = [{k: f[k] for k in ('colaborador_id', 'nombre', 'puesto', 'departamento', 'puntaje_total', 'posicion')}
                    for f in propio[:5]]

    if admin:
        departamentos = []
        for depto in Departamento.objects.all().order_by('nombre'):
            qs = Tarea.objects.filter(colaborador__perfil__puesto_trabajo__departamento=depto,
                                      fecha_limite__range=(inicio, fin)).exclude(estado='CANCELADA')
            total = qs.count()
            validadas = qs.filter(estado='COMPLETADA').count()
            puntajes = [f['puntaje_total'] for f in ranking if f['departamento_id'] == depto.id]
            departamentos.append({
                'id': depto.id, 'nombre': depto.nombre, 'tareas': total, 'validadas': validadas,
                'cumplimiento': round(validadas / total * 100) if total else None,
                'vencidas': qs.filter(estado__in=['PENDIENTE', 'EN_PROGRESO'], fecha_limite__lt=hoy).count(),
                'puntaje_promedio': round(sum(puntajes) / len(puntajes), 1) if puntajes else None,
                'personas': User.objects.filter(is_active=True, perfil__puesto_trabajo__departamento=depto).count(),
            })
        datos['departamentos'] = departamentos
        datos['sin_puesto'] = User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=True).count()
    return Response(datos)


@api_view(['GET'])
def equipo_view(request):
    """Colaboradores a los que el usuario puede asignar tareas, con los KPIs que se alimentan de tareas."""
    equipo = asignables(request.user).select_related('perfil__puesto_trabajo__departamento').order_by(
        'first_name', 'username'
    )
    kpis_por_puesto = {}
    for kpi in KPIAsignado.objects.filter(activo=True, es_entrada_manual=False).select_related('plantilla_kpi'):
        kpis_por_puesto.setdefault(kpi.puesto_trabajo_id, []).append(
            {'id': kpi.id, 'nombre': kpi.plantilla_kpi.nombre}
        )

    datos = []
    for usuario in equipo:
        puesto = puesto_de(usuario)
        datos.append({
            'id': usuario.id,
            'nombre': _nombre(usuario),
            'puesto': puesto.nombre if puesto else None,
            'departamento': puesto.departamento.nombre if puesto else None,
            'departamento_id': puesto.departamento_id if puesto else None,
            'color': puesto.departamento.color if puesto else None,
            'es_yo': usuario.pk == request.user.pk,
            'kpis_por_tareas': kpis_por_puesto.get(puesto.id, []) if puesto else [],
        })
    return Response(datos)


def _revisar_pausas_si_toca():
    """Cada pantalla abierta pregunta por sus avisos cada minuto: de paso se revisan las pausas largas (como mucho cada 20 s)."""
    from django.core.cache import cache
    if cache.add('asistencia:revisar-pausas', 1, 20):
        from apps.asistencia.servicios import revisar_almuerzos, revisar_pausas
        try:
            revisar_pausas()
            revisar_almuerzos()
        except Exception:  # noqa: BLE001 (una falla aquí nunca debe romper la campanita)
            import logging
            logging.getLogger(__name__).exception('No se pudieron revisar las pausas')


@api_view(['GET'])
def notificaciones_view(request):
    _revisar_pausas_si_toca()
    qs = Notificacion.objects.filter(destinatario=request.user)
    user = request.user
    return Response({
        'no_leidas': qs.filter(leida=False).count(),
        # Cambia cuando alguien entrega, valida, devuelve, reabre o cancela una tarea: las pantallas abiertas de todos se refrescan solas
        'pulso': HistorialTarea.objects.filter(accion__in=ACCIONES_QUE_REFRESCAN).aggregate(m=Max('id'))['m'] or 0,
        'avisos': NotificacionSerializer(qs[:30], many=True).data,
        # Para el número junto a «Por validar» en el menú (se consulta cada minuto)
        'por_validar': (por_validar(Tarea.objects.all(), user).count() if (puede_validar(user) or tiene_propias(user)) else 0),
    })


@api_view(['POST'])
def notificaciones_leer_view(request):
    """Marca como leídas las indicadas en `ids`, o todas si no se indica ninguna."""
    qs = Notificacion.objects.filter(destinatario=request.user, leida=False)
    ids = request.data.get('ids')
    if ids:
        qs = qs.filter(id__in=ids)
    return Response({'marcadas': qs.update(leida=True)})


@api_view(['GET', 'PUT', 'PATCH'])
def configuracion_view(request):
    config = ConfiguracionDesempeno.actual()
    if request.method == 'GET':
        return Response(ConfiguracionSerializer(config).data)
    if not es_administrador(request.user):
        raise PermissionDenied("Solo un administrador cambia las reglas del puntaje.")
    serializer = ConfiguracionSerializer(config, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['POST'])
def pedir_trabajo_view(request):
    """Sin tareas pendientes, el colaborador avisa a su supervisor que puede tomar más."""
    resultado = servicios.pedir_trabajo(request.user)
    if isinstance(resultado, str):
        return Response({"detail": resultado}, status=status.HTTP_400_BAD_REQUEST)
    quienes = " o ".join(resultado) if resultado else "la administración"
    return Response({"message": f"Listo. Le avisamos a {quienes} que puedes tomar más trabajo."})


ORDEN_ESTADO_PERSONA = {'vencida': 0, 'bloqueada': 1, 'en_espera': 2, 'libre': 3, 'en_revision': 4, 'por_empezar': 5, 'trabajando': 6}


@api_view(['GET'])
def carga_equipo_view(request):
    """
    Tablero del equipo (lo que era el TeamBoard de Adzone Team): en qué está cada persona ahora.
    Estado: vencida, bloqueada (solo le quedan tareas bloqueadas), trabajando, por_empezar, en_revision,
    en_espera (terminó y avisó: espera asignación) o libre (sin tareas y sin avisar).
    """
    user = request.user
    if not puede_validar(user):
        raise PermissionDenied("Solo para quien supervisa un equipo.")
    hoy = timezone.localdate()
    equipo = list(equipo_gestionable(user).exclude(pk=user.pk)
                  .select_related('perfil__puesto_trabajo__departamento').order_by('first_name', 'username'))
    ids = {u.pk for u in equipo}
    abiertas = (Tarea.objects.filter(Q(colaborador__in=ids) | Q(companeros__in=ids),
                                     estado__in=['PENDIENTE', 'EN_PROGRESO', 'EN_REVISION', 'BLOQUEADA'])
                .distinct().prefetch_related('companeros', 'pasos').order_by('fecha_limite'))
    por_persona = {}
    for tarea in abiertas:
        for pid in tarea.participantes_ids():
            if pid in ids:
                por_persona.setdefault(pid, []).append(tarea)
    inicio_hoy = timezone.make_aware(datetime.combine(hoy, datetime.min.time()))
    esperas = {e.usuario_id: e for e in EsperaAsignacion.objects.filter(usuario__in=ids, hasta__isnull=True)}
    piden = set(esperas)

    def resumen(t):
        pasos = list(t.pasos.all())
        return {'id': t.id, 'titulo': t.titulo, 'cliente': t.cliente, 'estado': t.estado,
                'motivo_bloqueo': t.motivo_bloqueo if t.estado == 'BLOQUEADA' else '',
                'fecha_limite': t.fecha_limite, 'vencida': t.fecha_limite < hoy and t.estado not in ('EN_REVISION', 'BLOQUEADA'),
                'progreso': {'hechos': sum(p.hecho for p in pasos), 'total': len(pasos)} if pasos else None}

    personas = []
    for u in equipo:
        tareas = por_persona.get(u.pk, [])
        por_hacer = [t for t in tareas if t.estado in ('PENDIENTE', 'EN_PROGRESO')]
        vencidas = [t for t in por_hacer if t.fecha_limite < hoy]
        en_curso = [t for t in por_hacer if t.estado == 'EN_PROGRESO']
        bloqueadas = [t for t in tareas if t.estado == 'BLOQUEADA']
        if vencidas:
            estado = 'vencida'
        elif en_curso:
            estado = 'trabajando'
        elif por_hacer:
            estado = 'por_empezar'
        elif u.pk in piden:
            estado = 'en_espera'
        elif bloqueadas:
            estado = 'bloqueada'
        elif tareas:
            estado = 'en_revision'
        else:
            estado = 'libre'
        actual = (vencidas or en_curso or por_hacer or bloqueadas or tareas or [None])[0]
        puesto = puesto_de(u)
        depto = puesto.departamento if puesto else None
        personas.append({
            'id': u.pk, 'nombre': _nombre(u),
            'puesto': puesto.nombre if puesto else None,
            'departamento': depto.nombre if depto else None,
            'color': depto.color if depto else None, 'color_fondo': depto.color_fondo if depto else None,
            'estado': estado, 'pide_trabajo': u.pk in piden,
            'esperando_desde': esperas[u.pk].desde if u.pk in esperas else None,
            'abiertas': len(por_hacer), 'vencidas': len(vencidas), 'bloqueadas': len(bloqueadas),
            'en_revision': sum(1 for t in tareas if t.estado == 'EN_REVISION'),
            'actual': resumen(actual) if actual else None,
        })
    personas.sort(key=lambda p: (ORDEN_ESTADO_PERSONA[p['estado']], p['nombre']))
    conteo = {}
    for p in personas:
        conteo[p['estado']] = conteo.get(p['estado'], 0) + 1
    return Response({'fecha': hoy, 'conteo': conteo, 'personas': personas})


@api_view(['GET'])
def ficha_view(request):
    """Ficha de productividad del mes: uno mismo, o alguien de su equipo."""
    from .ficha import ficha
    usuario = request.user
    if request.query_params.get('usuario'):
        if not str(request.query_params['usuario']).isdigit():
            return Response({'usuario': 'Debe ser un número.'}, status=400)
        usuario = User.objects.filter(pk=request.query_params['usuario']).first()
        if usuario is None or (usuario.pk != request.user.pk and not puede_gestionar(request.user, usuario)):
            raise PermissionDenied("Solo ves la ficha de tu equipo.")
    meses = 12 if request.query_params.get('meses') == '12' else 6
    return Response(ficha(usuario, periodo_desde_mes(request.query_params.get('mes')), visor=request.user, meses=meses))


@api_view(['GET'])
@permission_classes([EsAdministrador])
def panel_view(request):
    """Panel gerencial de la Dirección."""
    from .panel import panel
    return Response(panel(periodo_desde_mes(request.query_params.get('mes'))))


@api_view(['GET'])
@permission_classes([EsAdministrador])
def panel_exportar_view(request):
    """El panel del mes en CSV (se abre en Excel): indicadores, áreas y alertas."""
    from .panel import panel
    d = panel(periodo_desde_mes(request.query_params.get('mes')))
    r = HttpResponse(content_type='text/csv; charset=utf-8')
    r['Content-Disposition'] = f'attachment; filename="panel-gerencial-{d["mes"]}.csv"'
    r.write('﻿')
    w = csv.writer(r)
    v = lambda x: '' if x is None else x
    w.writerow([f'Panel gerencial {d["mes"]}'])
    for etiqueta, clave in (('Personal activo', 'personal_activo'), ('Evaluados', 'evaluados'), ('Puntaje promedio', 'puntaje_promedio'),
                            ('Asistencia promedio', 'asistencia_promedio'), ('Calidad promedio', 'calidad_promedio'),
                            ('OT completadas', 'ot_completadas'), ('OT a tiempo (%)', 'ot_a_tiempo'), ('OT abiertas', 'ot_abiertas'),
                            ('Tareas validadas', 'tareas_validadas'), ('Tareas a tiempo (%)', 'tareas_a_tiempo'),
                            ('Planes de mejora abiertos', 'planes_abiertos')):
        w.writerow([etiqueta, v(d[clave])])
    w.writerow([])
    w.writerow(['Departamento', 'Personas', 'Evaluados', 'Puntaje', 'Asistencia', 'Calidad', 'KPIs',
                'Tareas validadas', 'Tareas vencidas', 'Horas registradas', 'Bajo el mínimo'])
    for x in d['departamentos']:
        w.writerow([x['nombre'], x['personas'], x['evaluados'], v(x['puntaje']), v(x['asistencia']), v(x['calidad']), v(x['kpis']),
                    x['tareas_validadas'], x['tareas_vencidas'], x['horas'], x['bajo_minimo']])
    w.writerow([])
    w.writerow(['Alerta', 'Nivel', 'Detalle'])
    for a in d['alertas']:
        w.writerow([a['titulo'], a['nivel'], a['detalle']])
    w.writerow([])
    w.writerow(['Mes', 'Puntaje', 'OT completadas', 'OT a tiempo (%)', 'Tareas validadas', 'Tareas a tiempo (%)'])
    for m in d['tendencia']:
        w.writerow([m['mes'], v(m['puntaje']), m['ot_completadas'], v(m['ot_a_tiempo']), m['tareas_validadas'], v(m['tareas_a_tiempo'])])
    return r


# ------------------------------------------------------------------ Inteligencia
@api_view(['GET', 'POST'])
@permission_classes([EsAdministrador])
def resumen_semanal_view(request):
    """GET: el de esta semana (lo genera si falta) y los anteriores. POST: lo vuelve a generar con los datos de ahora."""
    from apps.core import ia
    from .inteligencia import generar_resumen
    from .models import ResumenSemanal
    r = generar_resumen(forzar=request.method == 'POST')
    return Response({'actual': {'semana': r.semana, 'texto': r.texto, 'con_ia': r.con_ia, 'datos': r.datos, 'creado': r.creado},
                     'anteriores': [{'semana': x.semana, 'texto': x.texto, 'con_ia': x.con_ia} for x in ResumenSemanal.objects.exclude(pk=r.pk)[:8]],
                     'ia_configurada': ia.activa()})


@api_view(['POST'])
def sugerir_asignacion_view(request):
    from .inteligencia import sugerir_asignacion
    from .permisos import equipo_gestionable
    if not equipo_gestionable(request.user, 'tareas.asignar').exists():
        raise PermissionDenied("Esta sugerencia es para quien asigna tareas a su equipo.")
    return Response(sugerir_asignacion(request.user, str(request.data.get('titulo') or '')[:255], str(request.data.get('descripcion') or '')[:2000]))
