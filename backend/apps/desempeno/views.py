import csv
import mimetypes
import os
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.models import Departamento
from apps.kpis.models import KPIAsignado
from . import servicios
from .models import (
    ConfiguracionDesempeno, EmpleadoDelMes, EvidenciaArchivo, Notificacion, ResultadoKPI, Tarea, TareaRecurrente,
)
from .permisos import (
    EsAdministrador, equipo_gestionable, es_administrador, puede_gestionar, puede_revisar,
    puede_validar, puesto_de, subordinados,
)
from .puntaje import calcular_ranking, rango_del_mes
from .serializers import (
    ConfiguracionSerializer, EmpleadoDelMesSerializer, EntregaSerializer, HistorialSerializer, NotificacionSerializer,
    ReaperturaSerializer, RechazoSerializer, ResultadoKPISerializer, TareaRecurrenteSerializer, TareaSerializer,
    ValidacionSerializer,
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
            'kpi_asignado__plantilla_kpi', 'proyecto', 'orden',
        ).prefetch_related('evidencias', 'pasos', 'companeros')
        if not es_administrador(user):
            subs = subordinados(user)
            queryset = queryset.filter(Q(colaborador=user) | Q(companeros=user) | Q(colaborador__in=subs)).distinct()

        params = self.request.query_params
        ambito = params.get('ambito')
        if ambito == 'mias':
            queryset = queryset.filter(Q(colaborador=user) | Q(companeros=user)).distinct()
        elif ambito == 'equipo':
            queryset = queryset.filter(colaborador__in=equipo_gestionable(user)).exclude(colaborador=user)
        elif ambito == 'por_validar':
            queryset = (queryset.filter(estado='EN_REVISION', colaborador__in=equipo_gestionable(user))
                        .exclude(colaborador=user).exclude(companeros=user))

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

    def _exigir_gestion(self, colaborador):
        if not puede_gestionar(self.request.user, colaborador):
            raise PermissionDenied("Solo el supervisor directo o un administrador puede gestionar esta tarea.")

    def _exigir_participante(self, tarea, que="trabajar"):
        if self.request.user.pk not in tarea.participantes_ids():
            raise PermissionDenied(f"Solo quien tiene asignada la tarea puede {que}la.")

    def _exigir_revision(self, tarea):
        if self.request.user.pk in tarea.participantes_ids():
            raise PermissionDenied("Nadie puede validar, devolver ni reabrir su propia tarea.")
        if not puede_revisar(self.request.user, tarea.colaborador):
            raise PermissionDenied("Solo el supervisor directo o un administrador puede revisar esta tarea.")

    def perform_create(self, serializer):
        self._exigir_gestion(serializer.validated_data['colaborador'])
        for companero in serializer.validated_data.get('companeros', []):
            self._exigir_gestion(companero)
        tarea = serializer.save(asignada_por=self.request.user)
        servicios.al_asignar(tarea, self.request.user)

    def perform_update(self, serializer):
        self._exigir_gestion(serializer.instance.colaborador)
        nuevo = serializer.validated_data.get('colaborador')
        if nuevo:
            self._exigir_gestion(nuevo)
        if serializer.instance.estado == 'COMPLETADA':
            raise PermissionDenied("Una tarea validada no se edita: primero hay que reabrirla.")
        for companero in serializer.validated_data.get('companeros', []):
            self._exigir_gestion(companero)
        anterior = serializer.instance.colaborador
        antes = set(serializer.instance.companeros.values_list('pk', flat=True))
        tarea = serializer.save()
        nuevos = [u for u in tarea.companeros.all() if u.pk not in antes]
        if nuevos:
            servicios.avisar(nuevos, 'ASIGNADA', f"Te sumaron a una tarea: {tarea.titulo}",
                             f"Responsable: {_nombre(tarea.colaborador)}.", tarea=tarea, enlace='/mis-tareas',
                             excepto=self.request.user)
        cambios = ', '.join(sorted(serializer.validated_data.keys()))
        servicios.registrar(tarea, self.request.user, 'EDITADA', f"Cambió: {cambios}")
        if nuevo and nuevo.pk != anterior.pk:
            servicios.avisar([nuevo], 'ASIGNADA', f"Nueva tarea: {tarea.titulo}",
                             f"{_nombre(self.request.user)} te la asignó.", tarea=tarea, enlace='/mis-tareas',
                             excepto=self.request.user)

    def perform_destroy(self, instance):
        self._exigir_gestion(instance.colaborador)
        if instance.estado == 'COMPLETADA':
            raise PermissionDenied("Una tarea validada no se borra: ya cuenta en el historial. Puedes reabrirla o cancelarla.")
        instance.delete()

    def _respuesta(self, tarea):
        tarea = self.get_queryset().get(pk=tarea.pk)
        return Response(self.get_serializer(tarea).data)

    @action(detail=True, methods=['get'])
    def historial(self, request, pk=None):
        tarea = self.get_object()
        return Response(HistorialSerializer(tarea.historial.select_related('usuario'), many=True).data)

    @action(detail=True, methods=['post'])
    def iniciar(self, request, pk=None):
        tarea = self.get_object()
        self._exigir_participante(tarea, "inicia")
        if tarea.estado != 'PENDIENTE':
            return Response({"detail": "La tarea ya fue iniciada."}, status=status.HTTP_400_BAD_REQUEST)
        tarea.estado = 'EN_PROGRESO'
        tarea.save()
        servicios.registrar(tarea, request.user, 'INICIADA')
        servicios.tras_cambio(tarea, request.user)
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
            tarea.comentario_revision = ''
            tarea.save()
            for archivo in datos.get('archivos', []):
                EvidenciaArchivo.objects.create(
                    tarea=tarea, archivo=archivo, nombre_original=archivo.name[:255],
                    tipo=(getattr(archivo, 'content_type', '') or mimetypes.guess_type(archivo.name)[0] or '')[:100],
                    tamano=archivo.size, ronda=tarea.rondas_revision, subido_por=request.user,
                )
            servicios.al_entregar(tarea, request.user)
        return self._respuesta(tarea)

    @action(detail=True, methods=['post'])
    def validar(self, request, pk=None):
        tarea = self.get_object()
        self._exigir_revision(tarea)
        if tarea.estado != 'EN_REVISION':
            return Response({"detail": "Solo se pueden validar tareas entregadas."},
                            status=status.HTTP_400_BAD_REQUEST)
        validacion = ValidacionSerializer(data=request.data)
        validacion.is_valid(raise_exception=True)
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
        tarea.comentario_revision = rechazo.validated_data['comentario_revision']
        tarea.estado = 'EN_PROGRESO'
        tarea.fecha_completada = None
        tarea.rondas_revision += 1
        tarea.save()
        servicios.al_devolver(tarea, request.user)
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
        return Response({"message": f"Le llegó el recordatorio a {_nombre(tarea.colaborador)}."})

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
def evidencia_archivo_view(request, pk):
    """Entrega una foto o PDF solo a quien tiene que ver con la tarea."""
    try:
        evidencia = EvidenciaArchivo.objects.select_related('tarea__colaborador').get(pk=pk)
    except EvidenciaArchivo.DoesNotExist:
        raise Http404
    tarea = evidencia.tarea
    if not (tarea.colaborador_id == request.user.pk or puede_gestionar(request.user, tarea.colaborador)):
        raise Http404
    try:
        archivo = evidencia.archivo.open('rb')
    except (FileNotFoundError, ValueError):
        raise Http404
    tipo = mimetypes.guess_type(evidencia.archivo.name)[0] or 'application/octet-stream'
    inline = tipo.startswith('image/') or tipo == 'application/pdf'
    respuesta = FileResponse(archivo, content_type=tipo, as_attachment=not inline,
                             filename=evidencia.nombre_original or os.path.basename(evidencia.archivo.name))
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
        return qs.filter(colaborador__in=subordinados(user))

    def _exigir(self, colaborador):
        if not puede_gestionar(self.request.user, colaborador):
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
def _ranking_con_candidatos(periodo):
    ranking = calcular_ranking(periodo)
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
    ranking, general, por_depto = _ranking_con_candidatos(periodo)
    config = ConfiguracionDesempeno.actual()
    return Response({
        'periodo': periodo.isoformat(),
        'mes_en_curso': periodo == timezone.localdate().replace(day=1),
        'ranking': ranking,
        'candidato_general': general,
        'candidatos_departamento': por_depto,
        'minimo_tareas': config.minimo_tareas_empleado_mes,
        'pendientes_validar': Tarea.objects.filter(estado='EN_REVISION', fecha_limite__range=rango_del_mes(periodo)).count(),
    })


@api_view(['GET'])
@permission_classes([EsAdministrador])
def ranking_exportar_view(request):
    """El ranking del mes en CSV (se abre en Excel) para nómina y reconocimientos."""
    periodo = periodo_desde_mes(request.query_params.get('mes'))
    respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
    respuesta['Content-Disposition'] = f'attachment; filename="ranking-{periodo:%Y-%m}.csv"'
    respuesta.write('﻿')
    escritor = csv.writer(respuesta)
    escritor.writerow(['Posición', 'Colaborador', 'Puesto', 'Departamento', 'Puntaje total', 'Puntaje tareas',
                       'Puntaje KPIs', 'Tareas validadas', 'A tiempo', 'A la primera', 'Vencidas sin entregar',
                       'Calidad promedio', 'Bono sugerido (%)'])
    for f in calcular_ranking(periodo):
        t = f['tareas']
        escritor.writerow([f['posicion'], f['nombre'], f['puesto'] or '', f['departamento'] or '', f['puntaje_total'],
                           '' if f['puntaje_tareas'] is None else f['puntaje_tareas'],
                           '' if f['puntaje_kpis'] is None else f['puntaje_kpis'],
                           t['completadas'], t['a_tiempo'], t['a_la_primera'], t['vencidas'],
                           '' if t['calidad_promedio'] is None else t['calidad_promedio'], f['bono_sugerido']])
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
    ranking = calcular_ranking(periodo)
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
            Tarea.objects.filter(estado='EN_REVISION', colaborador__in=equipo_gestionable(user)).exclude(colaborador=user).exclude(companeros=user).count()
            if puede_validar(user) else 0
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
    equipo = equipo_gestionable(request.user).select_related('perfil__puesto_trabajo__departamento').order_by(
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


@api_view(['GET'])
def notificaciones_view(request):
    qs = Notificacion.objects.filter(destinatario=request.user)
    user = request.user
    return Response({
        'no_leidas': qs.filter(leida=False).count(),
        'avisos': NotificacionSerializer(qs[:30], many=True).data,
        # Para el número junto a «Por validar» en el menú (se consulta cada minuto)
        'por_validar': (Tarea.objects.filter(estado='EN_REVISION', colaborador__in=equipo_gestionable(user))
                        .exclude(colaborador=user).exclude(companeros=user).count() if puede_validar(user) else 0),
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


ORDEN_ESTADO_PERSONA = {'vencida': 0, 'pide_trabajo': 1, 'libre': 2, 'en_revision': 3, 'por_empezar': 4, 'trabajando': 5}


@api_view(['GET'])
def carga_equipo_view(request):
    """
    Tablero del equipo (lo que era el TeamBoard de Adzone Team): en qué está cada persona ahora.
    Estado: vencida, trabajando, por_empezar, en_revision o libre; y si pidió más trabajo hoy.
    """
    user = request.user
    if not puede_validar(user):
        raise PermissionDenied("Solo para quien supervisa un equipo.")
    hoy = timezone.localdate()
    equipo = list(equipo_gestionable(user).exclude(pk=user.pk)
                  .select_related('perfil__puesto_trabajo__departamento').order_by('first_name', 'username'))
    ids = {u.pk for u in equipo}
    abiertas = (Tarea.objects.filter(Q(colaborador__in=ids) | Q(companeros__in=ids),
                                     estado__in=['PENDIENTE', 'EN_PROGRESO', 'EN_REVISION'])
                .distinct().prefetch_related('companeros', 'pasos').order_by('fecha_limite'))
    por_persona = {}
    for tarea in abiertas:
        for pid in tarea.participantes_ids():
            if pid in ids:
                por_persona.setdefault(pid, []).append(tarea)
    inicio_hoy = timezone.make_aware(datetime.combine(hoy, datetime.min.time()))
    piden = set(Notificacion.objects.filter(tipo='PIDE_TRABAJO', fecha__gte=inicio_hoy, remitente__in=ids)
                .values_list('remitente_id', flat=True))

    def resumen(t):
        pasos = list(t.pasos.all())
        return {'id': t.id, 'titulo': t.titulo, 'cliente': t.cliente, 'estado': t.estado,
                'fecha_limite': t.fecha_limite, 'vencida': t.fecha_limite < hoy and t.estado != 'EN_REVISION',
                'progreso': {'hechos': sum(p.hecho for p in pasos), 'total': len(pasos)} if pasos else None}

    personas = []
    for u in equipo:
        tareas = por_persona.get(u.pk, [])
        por_hacer = [t for t in tareas if t.estado in ('PENDIENTE', 'EN_PROGRESO')]
        vencidas = [t for t in por_hacer if t.fecha_limite < hoy]
        en_curso = [t for t in por_hacer if t.estado == 'EN_PROGRESO']
        if vencidas:
            estado = 'vencida'
        elif en_curso:
            estado = 'trabajando'
        elif por_hacer:
            estado = 'por_empezar'
        elif tareas:
            estado = 'en_revision'
        else:
            estado = 'pide_trabajo' if u.pk in piden else 'libre'
        actual = (vencidas or en_curso or por_hacer or tareas or [None])[0]
        puesto = puesto_de(u)
        depto = puesto.departamento if puesto else None
        personas.append({
            'id': u.pk, 'nombre': _nombre(u),
            'puesto': puesto.nombre if puesto else None,
            'departamento': depto.nombre if depto else None,
            'color': depto.color if depto else None, 'color_fondo': depto.color_fondo if depto else None,
            'estado': estado, 'pide_trabajo': u.pk in piden,
            'abiertas': len(por_hacer), 'vencidas': len(vencidas),
            'en_revision': sum(1 for t in tareas if t.estado == 'EN_REVISION'),
            'actual': resumen(actual) if actual else None,
        })
    personas.sort(key=lambda p: (ORDEN_ESTADO_PERSONA[p['estado']], p['nombre']))
    conteo = {}
    for p in personas:
        conteo[p['estado']] = conteo.get(p['estado'], 0) + 1
    return Response({'fecha': hoy, 'conteo': conteo, 'personas': personas})
