import os

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import serializers

from .models import (
    ConfiguracionDesempeno, EmpleadoDelMes, EvidenciaArchivo, HistorialTarea, Notificacion,
    PasoTarea, ResultadoKPI, Tarea, TareaRecurrente,
)
from .permisos import puede_gestionar, puede_revisar


def _nombre(usuario):
    return (usuario.get_full_name() or usuario.username) if usuario else None


class EvidenciaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    es_imagen = serializers.BooleanField(read_only=True)

    class Meta:
        model = EvidenciaArchivo
        fields = ['id', 'url', 'nombre_original', 'tipo', 'tamano', 'ronda', 'es_imagen', 'fecha']

    def get_url(self, obj):
        # Siempre por la API: revisa permisos antes de entregar el archivo.
        return f"/api/desempeno/evidencias/{obj.id}/archivo/"


class HistorialSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    accion_texto = serializers.CharField(source='get_accion_display', read_only=True)

    class Meta:
        model = HistorialTarea
        fields = ['id', 'accion', 'accion_texto', 'usuario_nombre', 'comentario', 'fecha']

    def get_usuario_nombre(self, obj):
        return _nombre(obj.usuario) or 'Sistema'


class PasoSerializer(serializers.ModelSerializer):
    hecho_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = PasoTarea
        fields = ['id', 'texto', 'hecho', 'orden', 'hecho_por_nombre', 'fecha_hecho']
        read_only_fields = ['hecho', 'orden', 'fecha_hecho']

    def get_hecho_por_nombre(self, obj):
        return _nombre(obj.hecho_por) if obj.hecho_por_id else None


class TareaSerializer(serializers.ModelSerializer):
    colaborador_nombre = serializers.SerializerMethodField()
    colaborador_puesto = serializers.CharField(source='colaborador.perfil.puesto_trabajo.nombre', read_only=True, default=None)
    colaborador_departamento = serializers.CharField(
        source='colaborador.perfil.puesto_trabajo.departamento.nombre', read_only=True, default=None)
    asignada_por_nombre = serializers.SerializerMethodField()
    validada_por_nombre = serializers.SerializerMethodField()
    kpi_nombre = serializers.CharField(source='kpi_asignado.plantilla_kpi.nombre', read_only=True, default=None)
    a_tiempo = serializers.BooleanField(read_only=True)
    a_la_primera = serializers.BooleanField(read_only=True)
    evidencias = EvidenciaSerializer(many=True, read_only=True)
    es_recurrente = serializers.SerializerMethodField()
    puedo_gestionar = serializers.SerializerMethodField()
    puedo_revisar = serializers.SerializerMethodField()
    soy_participante = serializers.SerializerMethodField()
    companeros = serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=User.objects.filter(is_active=True))
    companeros_nombres = serializers.SerializerMethodField()
    # Los pasos se mandan como lista de textos (o {id, texto}) y se sincronizan al guardar.
    pasos = PasoSerializer(many=True, read_only=True)
    pasos_texto = serializers.ListField(child=serializers.CharField(max_length=255, allow_blank=True),
                                        required=False, write_only=True)
    progreso = serializers.SerializerMethodField()
    proyecto_nombre = serializers.CharField(source='proyecto.nombre', read_only=True, default=None)
    orden_numero = serializers.CharField(source='orden.numero', read_only=True, default=None)

    class Meta:
        model = Tarea
        fields = [
            'id', 'titulo', 'descripcion', 'cliente',
            'colaborador', 'companeros', 'companeros_nombres', 'pasos', 'pasos_texto', 'progreso',
            'proyecto', 'proyecto_nombre', 'orden', 'orden_numero', 'fecha_inicio', 'horas_estimadas', 'colaborador_nombre', 'colaborador_puesto', 'colaborador_departamento',
            'asignada_por', 'asignada_por_nombre',
            'kpi_asignado', 'kpi_nombre',
            'prioridad', 'estado', 'fecha_limite', 'fecha_completada', 'a_tiempo', 'a_la_primera',
            'evidencia_nota', 'evidencia_enlace', 'evidencias',
            'validada_por', 'validada_por_nombre', 'fecha_validacion', 'comentario_revision',
            'calificacion_calidad', 'comentario_evaluacion', 'rondas_revision', 'es_recurrente',
            'puedo_gestionar', 'puedo_revisar', 'soy_participante',
            'fecha_creacion', 'fecha_modificacion',
        ]
        # El estado y la calificación solo cambian con las acciones (iniciar, entregar, validar,
        # devolver, reabrir), que dejan historial y avisos. Editar no salta el flujo.
        read_only_fields = [
            'asignada_por', 'estado', 'orden', 'fecha_completada', 'evidencia_nota', 'evidencia_enlace',
            'validada_por', 'fecha_validacion', 'comentario_revision', 'calificacion_calidad',
            'comentario_evaluacion', 'rondas_revision',
        ]

    def _usuario(self):
        request = self.context.get('request')
        return getattr(request, 'user', None)

    def get_colaborador_nombre(self, obj):
        return _nombre(obj.colaborador)

    def get_asignada_por_nombre(self, obj):
        return _nombre(obj.asignada_por)

    def get_validada_por_nombre(self, obj):
        return _nombre(obj.validada_por)

    def get_es_recurrente(self, obj):
        return obj.recurrencia_id is not None

    def get_puedo_gestionar(self, obj):
        user = self._usuario()
        return bool(user and puede_gestionar(user, obj.colaborador))

    def get_puedo_revisar(self, obj):
        user = self._usuario()
        return bool(user and user.pk not in obj.participantes_ids() and puede_revisar(user, obj.colaborador))

    def get_soy_participante(self, obj):
        user = self._usuario()
        return bool(user and user.pk in obj.participantes_ids())

    def get_companeros_nombres(self, obj):
        return [_nombre(u) for u in obj.companeros.all()]

    def get_progreso(self, obj):
        pasos = list(obj.pasos.all())
        if not pasos:
            return None
        return {'hechos': sum(1 for p in pasos if p.hecho), 'total': len(pasos)}

    def _guardar_pasos(self, tarea, textos):
        if textos is None:
            return
        textos = [t.strip() for t in textos if t and t.strip()]
        existentes = list(tarea.pasos.all())
        for i, texto in enumerate(textos):
            if i < len(existentes):
                paso = existentes[i]
                if paso.texto != texto or paso.orden != i:
                    if paso.texto != texto:
                        paso.hecho, paso.hecho_por, paso.fecha_hecho = False, None, None
                    paso.texto, paso.orden = texto, i
                    paso.save()
            else:
                PasoTarea.objects.create(tarea=tarea, texto=texto, orden=i)
        for paso in existentes[len(textos):]:
            paso.delete()

    def create(self, validated_data):
        textos = validated_data.pop('pasos_texto', None)
        tarea = super().create(validated_data)
        self._guardar_pasos(tarea, textos)
        return tarea

    def update(self, instance, validated_data):
        textos = validated_data.pop('pasos_texto', None)
        tarea = super().update(instance, validated_data)
        self._guardar_pasos(tarea, textos)
        return tarea

    def validate_titulo(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Escribe qué hay que hacer.")
        return value

    def validate(self, data):
        colaborador = data.get('colaborador', getattr(self.instance, 'colaborador', None))
        kpi = data.get('kpi_asignado', getattr(self.instance, 'kpi_asignado', None))
        puesto = getattr(getattr(colaborador, 'perfil', None), 'puesto_trabajo', None)
        if kpi and (puesto is None or kpi.puesto_trabajo_id != puesto.id):
            raise serializers.ValidationError(
                {"kpi_asignado": "Ese KPI no pertenece al puesto del colaborador."}
            )
        if kpi and kpi.es_entrada_manual:
            raise serializers.ValidationError(
                {"kpi_asignado": "Ese KPI se anota a mano cada mes; solo los KPIs automáticos se alimentan de tareas."}
            )
        companeros = data.get('companeros')
        if companeros is not None and colaborador is not None:
            data['companeros'] = [u for u in companeros if u.pk != colaborador.pk]  # el responsable no es su propio compañero
        inicio = data.get('fecha_inicio', getattr(self.instance, 'fecha_inicio', None))
        limite = data.get('fecha_limite', getattr(self.instance, 'fecha_limite', None))
        if inicio and limite and inicio > limite:
            raise serializers.ValidationError({"fecha_inicio": "Empieza después de su fecha límite."})
        return data


class EntregaSerializer(serializers.Serializer):
    evidencia_nota = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    evidencia_enlace = serializers.URLField(required=False, allow_blank=True, max_length=500)
    archivos = serializers.ListField(child=serializers.FileField(), required=False, allow_empty=True)

    EXTENSIONES = ('.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.gif', '.pdf')

    def validate_archivos(self, archivos):
        maximo = settings.EVIDENCIA_MAX_ARCHIVOS
        if len(archivos) > maximo:
            raise serializers.ValidationError(f"Como máximo {maximo} archivos por entrega.")
        for archivo in archivos:
            if archivo.size > settings.EVIDENCIA_MAX_MB * 1024 * 1024:
                raise serializers.ValidationError(f"«{archivo.name}» pesa más de {settings.EVIDENCIA_MAX_MB} MB.")
            if os.path.splitext(archivo.name)[1].lower() not in self.EXTENSIONES:
                raise serializers.ValidationError(f"«{archivo.name}»: solo se aceptan fotos o PDF.")
        return archivos

    def validate(self, data):
        if not (data.get('evidencia_nota', '').strip() or data.get('evidencia_enlace') or data.get('archivos')):
            raise serializers.ValidationError({"detail": "Agrega una nota, un enlace o una foto como evidencia."})
        return data


class ValidacionSerializer(serializers.Serializer):
    calificacion_calidad = serializers.IntegerField(min_value=1, max_value=5)
    comentario_evaluacion = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class RechazoSerializer(serializers.Serializer):
    comentario_revision = serializers.CharField(max_length=2000)

    def validate_comentario_revision(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Explica qué debe corregir, para que sepa qué hacer.")
        return value.strip()


class ReaperturaSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=2000)


class ResultadoKPISerializer(serializers.ModelSerializer):
    colaborador_nombre = serializers.SerializerMethodField()
    kpi_nombre = serializers.CharField(source='kpi_asignado.plantilla_kpi.nombre', read_only=True)
    unidad_medida = serializers.CharField(source='kpi_asignado.plantilla_kpi.unidad_medida', read_only=True)
    menor_es_mejor = serializers.BooleanField(source='kpi_asignado.plantilla_kpi.menor_es_mejor', read_only=True)
    cumplimiento = serializers.FloatField(read_only=True)

    class Meta:
        model = ResultadoKPI
        fields = [
            'id', 'kpi_asignado', 'kpi_nombre', 'unidad_medida', 'menor_es_mejor',
            'colaborador', 'colaborador_nombre', 'periodo',
            'valor_meta', 'valor_real', 'cumplimiento', 'comentario',
            'fecha_registro', 'fecha_modificacion',
        ]

    def get_colaborador_nombre(self, obj):
        return _nombre(obj.colaborador)

    def validate_periodo(self, value):
        return value.replace(day=1)

    def validate(self, data):
        kpi = data.get('kpi_asignado', getattr(self.instance, 'kpi_asignado', None))
        colaborador = data.get('colaborador', getattr(self.instance, 'colaborador', None))
        puesto = getattr(getattr(colaborador, 'perfil', None), 'puesto_trabajo', None)
        if kpi and puesto and kpi.puesto_trabajo_id != puesto.id:
            raise serializers.ValidationError(
                {"kpi_asignado": "Este KPI no está asignado al puesto del colaborador."}
            )
        if kpi and not puesto:
            raise serializers.ValidationError(
                {"colaborador": "El colaborador no tiene un puesto de trabajo asignado."}
            )
        for campo in ('valor_meta', 'valor_real'):
            if campo in data and data[campo] < 0:
                raise serializers.ValidationError({campo: "No puede ser negativo."})
        return data


class EmpleadoDelMesSerializer(serializers.ModelSerializer):
    colaborador_nombre = serializers.SerializerMethodField()
    puesto = serializers.CharField(source='colaborador.perfil.puesto_trabajo.nombre', read_only=True, default=None)
    departamento_nombre = serializers.CharField(source='departamento.nombre', read_only=True, default=None)

    class Meta:
        model = EmpleadoDelMes
        fields = [
            'id', 'periodo', 'colaborador', 'colaborador_nombre', 'puesto',
            'departamento', 'departamento_nombre',
            'puntaje', 'motivo', 'beneficio', 'fecha_declaracion',
        ]
        read_only_fields = ['puntaje']
        validators = []

    def get_colaborador_nombre(self, obj):
        return _nombre(obj.colaborador)

    def validate_periodo(self, value):
        return value.replace(day=1)


class NotificacionSerializer(serializers.ModelSerializer):
    remitente_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Notificacion
        fields = ['id', 'tipo', 'titulo', 'mensaje', 'enlace', 'tarea', 'remitente_nombre', 'leida', 'fecha']

    def get_remitente_nombre(self, obj):
        return _nombre(obj.remitente)


class TareaRecurrenteSerializer(serializers.ModelSerializer):
    colaborador_nombre = serializers.SerializerMethodField()
    kpi_nombre = serializers.CharField(source='kpi_asignado.plantilla_kpi.nombre', read_only=True, default=None)
    frecuencia_texto = serializers.SerializerMethodField()

    class Meta:
        model = TareaRecurrente
        fields = [
            'id', 'titulo', 'descripcion', 'colaborador', 'colaborador_nombre', 'kpi_asignado', 'kpi_nombre',
            'prioridad', 'frecuencia', 'frecuencia_texto', 'dia_semana', 'dia_mes', 'inicio', 'activa',
            'generada_hasta', 'fecha_creacion',
        ]
        read_only_fields = ['generada_hasta']

    def get_colaborador_nombre(self, obj):
        return _nombre(obj.colaborador)

    def get_frecuencia_texto(self, obj):
        if obj.frecuencia == 'SEMANAL':
            return f"Cada {obj.get_dia_semana_display().lower()}"
        return f"Cada mes, el día {obj.dia_mes}"

    def validate_dia_mes(self, value):
        if not 1 <= value <= 28:
            raise serializers.ValidationError("Elige un día entre 1 y 28 (así existe en todos los meses).")
        return value

    def validate(self, data):
        colaborador = data.get('colaborador', getattr(self.instance, 'colaborador', None))
        kpi = data.get('kpi_asignado', getattr(self.instance, 'kpi_asignado', None))
        puesto = getattr(getattr(colaborador, 'perfil', None), 'puesto_trabajo', None)
        if kpi and (puesto is None or kpi.puesto_trabajo_id != puesto.id or kpi.es_entrada_manual):
            raise serializers.ValidationError({"kpi_asignado": "Elige un KPI automático del puesto del colaborador."})
        return data


class ConfiguracionSerializer(serializers.ModelSerializer):
    peso_kpis = serializers.IntegerField(read_only=True)

    class Meta:
        model = ConfiguracionDesempeno
        fields = ['peso_tareas', 'peso_kpis', 'nota_tarde', 'minimo_tareas_empleado_mes', 'tramos_bono', 'fecha_modificacion']

    def validate_peso_tareas(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Debe estar entre 0 y 100.")
        return value

    def validate_nota_tarde(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Debe estar entre 0 y 100.")
        return value

    def validate_tramos_bono(self, value):
        limpios = []
        for tramo in value or []:
            try:
                desde, porcentaje = float(tramo['desde']), float(tramo['porcentaje'])
            except (KeyError, TypeError, ValueError):
                raise serializers.ValidationError("Cada tramo necesita «desde» y «porcentaje» numéricos.")
            if not (0 <= desde <= 100 and 0 <= porcentaje <= 100):
                raise serializers.ValidationError("Los valores van de 0 a 100.")
            limpios.append({'desde': desde, 'porcentaje': porcentaje})
        return sorted(limpios, key=lambda t: -t['desde'])
