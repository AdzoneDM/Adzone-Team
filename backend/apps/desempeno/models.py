import os
import uuid

from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Departamento
from apps.kpis.models import KPIAsignado


class Tarea(models.Model):
    # Flujo: PENDIENTE → EN_PROGRESO → EN_REVISION (entregada) → COMPLETADA (validada).
    # Si el supervisor rechaza la entrega, vuelve a EN_PROGRESO con un comentario.
    # BLOQUEADA: no puede seguir por una dependencia o un problema (con motivo); al resolverse vuelve a EN_PROGRESO.
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROGRESO', 'En progreso'),
        ('BLOQUEADA', 'Bloqueada'),
        ('EN_REVISION', 'En revisión'),
        ('COMPLETADA', 'Validada'),
        ('CANCELADA', 'Cancelada'),
    ]
    PRIORIDAD_CHOICES = [
        ('BAJA', 'Baja'),
        ('MEDIA', 'Media'),
        ('ALTA', 'Alta'),
    ]

    titulo = models.CharField(max_length=255, verbose_name="Título")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    cliente = models.CharField(max_length=150, blank=True, verbose_name="Cliente",
                               help_text="Para quién es el trabajo (p. ej. Merengue Restaurant).")
    colaborador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tareas",
        verbose_name="Colaborador"
    )
    companeros = models.ManyToManyField(
        User,
        blank=True,
        related_name="tareas_compartidas",
        verbose_name="Compañeros",
        help_text="Tarea compartida: también la ven, la trabajan y les cuenta cuando se valida."
    )
    revisor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="tareas_a_revisar",
        help_text="Quien valida la tarea cuando la persona se la asignó a sí misma (Dirección). Vacío: la valida su supervisor.")
    departamento_origen = models.ForeignKey(
        'core.Departamento', on_delete=models.SET_NULL, null=True, blank=True, related_name='tareas_pedidas',
        help_text="Área de quien asignó la tarea (al crearla). Si es distinta a la de la persona, es un aporte entre áreas.")
    asignada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tareas_asignadas",
        verbose_name="Asignada por"
    )
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='MEDIA')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    proyecto = models.ForeignKey('operaciones.Proyecto', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='tareas', verbose_name="Proyecto")
    orden = models.ForeignKey('operaciones.OrdenTrabajo', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='tareas', verbose_name="Orden de trabajo")
    oa = models.ForeignKey('operaciones.OrdenArea', on_delete=models.SET_NULL, null=True, blank=True,
                           related_name='tareas', verbose_name="Orden de Área")
    fecha_inicio = models.DateField(null=True, blank=True, verbose_name="Empieza",
                                    help_text="Para el cronograma. Si está vacía, se toma la fecha de creación.")
    horas_estimadas = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True,
                                          verbose_name="Horas estimadas", help_text="Para medir la carga de cada persona.")
    fecha_limite = models.DateField(verbose_name="Fecha Límite")
    kpi_asignado = models.ForeignKey(
        KPIAsignado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tareas",
        verbose_name="KPI al que aporta",
        help_text="Si el KPI se calcula con tareas, cada tarea validada suma a su resultado."
    )
    fecha_completada = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Entrega",
        help_text="Día en que el colaborador entregó la tarea; define si fue a tiempo."
    )
    evidencia_nota = models.TextField(blank=True, verbose_name="Nota de Entrega")
    evidencia_enlace = models.URLField(blank=True, verbose_name="Enlace de Evidencia")
    rondas_revision = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Veces devuelta",
        help_text="Cuántas veces el supervisor devolvió la entrega para corregir."
    )
    recurrencia = models.ForeignKey(
        'TareaRecurrente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tareas",
        verbose_name="Generada por la tarea recurrente"
    )
    validada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tareas_validadas",
        verbose_name="Validada por"
    )
    fecha_validacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Validación")
    comentario_revision = models.TextField(
        blank=True,
        verbose_name="Motivo del Rechazo",
        help_text="Lo que el colaborador debe corregir antes de volver a entregar."
    )
    calificacion_calidad = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Calificación de Calidad (1-5)",
        help_text="Calidad del trabajo entregado, de 1 (deficiente) a 5 (excelente)."
    )
    comentario_evaluacion = models.TextField(blank=True, verbose_name="Comentario de Evaluación")
    motivo_bloqueo = models.TextField(blank=True, verbose_name="Motivo del bloqueo",
                                      help_text="Qué impide seguir (dependencia, falta de material, aprobación…).")
    bloqueada_desde = models.DateTimeField(null=True, blank=True, verbose_name="Bloqueada desde")
    fecha_inicio_trabajo = models.DateTimeField(null=True, blank=True, verbose_name="Empezó a trabajarla",
                                                help_text="Primera vez que pasó a «En progreso»: mide el tiempo de ejecución.")
    fecha_entrega_real = models.DateTimeField(null=True, blank=True, verbose_name="Entregada (fecha y hora)")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def participantes_ids(self):
        """Responsable y compañeros (ids). Usa el prefetch si existe."""
        return [self.colaborador_id, *[u.pk for u in self.companeros.all()]]

    @property
    def a_la_primera(self):
        return self.estado == 'COMPLETADA' and self.rondas_revision == 0

    @property
    def a_tiempo(self):
        if self.estado != 'COMPLETADA' or not self.fecha_completada:
            return None
        return self.fecha_completada <= self.fecha_limite

    def __str__(self):
        return f"{self.titulo} ({self.colaborador.username})"

    class Meta:
        verbose_name = "Tarea"
        verbose_name_plural = "Tareas"
        ordering = ['-fecha_limite', 'titulo']


class ResultadoKPI(models.Model):
    """Valor real alcanzado por un colaborador en un KPI de su puesto durante un mes."""
    kpi_asignado = models.ForeignKey(
        KPIAsignado,
        on_delete=models.CASCADE,
        related_name="resultados",
        verbose_name="KPI Asignado"
    )
    colaborador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="resultados_kpi",
        verbose_name="Colaborador"
    )
    periodo = models.DateField(
        verbose_name="Periodo (mes)",
        help_text="Primer día del mes evaluado."
    )
    valor_meta = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Meta Numérica")
    valor_real = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Alcanzado")
    comentario = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    @property
    def cumplimiento(self):
        """Porcentaje de cumplimiento de la meta, entre 0 y 100."""
        from .puntaje import cumplimiento
        return cumplimiento(self.valor_meta, self.valor_real, self.kpi_asignado.plantilla_kpi.menor_es_mejor)

    def __str__(self):
        return f"{self.kpi_asignado.plantilla_kpi.nombre} - {self.colaborador.username} ({self.periodo:%m/%Y})"

    class Meta:
        verbose_name = "Resultado de KPI"
        verbose_name_plural = "Resultados de KPIs"
        unique_together = ('kpi_asignado', 'colaborador', 'periodo')
        ordering = ['-periodo', 'colaborador__username']


class EmpleadoDelMes(models.Model):
    """Reconocimiento declarado por un administrador. Sin departamento = ganador general."""
    periodo = models.DateField(verbose_name="Periodo (mes)", help_text="Primer día del mes.")
    colaborador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reconocimientos_mes",
        verbose_name="Colaborador"
    )
    departamento = models.ForeignKey(
        Departamento,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="empleados_del_mes",
        verbose_name="Departamento",
        help_text="Vacío para el Empleado del Mes de toda la empresa."
    )
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Puntaje")
    motivo = models.TextField(blank=True, verbose_name="Motivo del Reconocimiento")
    beneficio = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Beneficio Otorgado",
        help_text="Ej: Bono, día libre, aumento salarial."
    )
    declarado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+"
    )
    fecha_declaracion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        ambito = self.departamento.nombre if self.departamento else "General"
        return f"{self.colaborador.username} - {ambito} ({self.periodo:%m/%Y})"

    class Meta:
        verbose_name = "Empleado del Mes"
        verbose_name_plural = "Empleados del Mes"
        constraints = [
            models.UniqueConstraint(
                fields=['periodo', 'departamento'],
                name='unico_empleado_mes_por_departamento'
            ),
            # Los NULL no chocan en la restricción anterior: un solo ganador general por mes
            models.UniqueConstraint(
                fields=['periodo'],
                condition=models.Q(departamento__isnull=True),
                name='unico_empleado_mes_general'
            ),
        ]
        ordering = ['-periodo', 'departamento__nombre']


class PasoTarea(models.Model):
    """Paso de una tarea (checklist): deja claro cómo avanzar y muestra el progreso."""
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, related_name="pasos")
    texto = models.CharField(max_length=255)
    hecho = models.BooleanField(default=False)
    orden = models.PositiveSmallIntegerField(default=0)
    hecho_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    fecha_inicio = models.DateTimeField(null=True, blank=True, help_text="Seguimiento de la ejecución: inicio de la etapa.")
    fecha_hecho = models.DateTimeField(null=True, blank=True)
    resultado = models.CharField("Resultado / observación", max_length=255, blank=True)

    def __str__(self):
        return self.texto

    class Meta:
        verbose_name = "Paso"
        verbose_name_plural = "Pasos"
        ordering = ['orden', 'id']


def _ruta_evidencia(instancia, nombre):
    """evidencias/AAAA/MM/<uuid>.<ext>: el nombre original no queda en el disco ni en la URL."""
    from django.utils import timezone
    ext = os.path.splitext(nombre)[1].lower()[:8]
    hoy = timezone.localdate()
    return f"evidencias/{hoy:%Y/%m}/{uuid.uuid4().hex}{ext}"


class EvidenciaArchivo(models.Model):
    """Foto o PDF de una entrega. Una tarea puede tener varias, de varias rondas."""
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, related_name="evidencias")
    archivo = models.FileField(upload_to=_ruta_evidencia)
    nombre_original = models.CharField(max_length=255, blank=True)
    tipo = models.CharField(max_length=100, blank=True)
    tamano = models.PositiveIntegerField(default=0)
    ronda = models.PositiveSmallIntegerField(default=0, help_text="Ronda de entrega en la que se subió (0 = primera).")
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    fecha = models.DateTimeField(auto_now_add=True)

    # Los videos pesan mucho: se borran solos unos días después de validada la tarea (la fila queda, con el aviso)
    purgado = models.BooleanField(default=False, help_text="El archivo ya se borró (limpieza automática de videos).")
    purgado_en = models.DateTimeField(null=True, blank=True)

    @property
    def es_imagen(self):
        return self.tipo.startswith('image/') or self.archivo.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic'))

    @property
    def es_video(self):
        from apps.core.archivos import es_video
        return es_video(self.nombre_original or self.archivo.name, self.tipo)

    def __str__(self):
        return f"Evidencia de {self.tarea_id}: {self.nombre_original}"

    class Meta:
        verbose_name = "Evidencia"
        verbose_name_plural = "Evidencias"
        ordering = ['fecha', 'id']


def _ruta_referencia(instancia, nombre):
    """referencias/AAAA/MM/<uuid>.<ext>: el nombre original no queda en el disco ni en la URL."""
    from django.utils import timezone
    ext = os.path.splitext(nombre)[1].lower()[:8]
    return f"referencias/{timezone.localdate():%Y/%m}/{uuid.uuid4().hex}{ext}"


class ReferenciaArchivo(models.Model):
    """Boceto, imagen o PDF que quien supervisa adjunta a una tarea para que la persona tenga referencia:
    al asignarla o al devolverla con correcciones. Distinto de la evidencia, que es lo que entrega quien trabaja."""
    ASIGNACION, CORRECCION = 'ASIGNACION', 'CORRECCION'
    MOMENTOS = [(ASIGNACION, 'Al asignar'), (CORRECCION, 'Al devolver')]
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, related_name="referencias")
    archivo = models.FileField(upload_to=_ruta_referencia)
    nombre_original = models.CharField(max_length=255, blank=True)
    tipo = models.CharField(max_length=100, blank=True)
    tamano = models.PositiveIntegerField(default=0)
    momento = models.CharField(max_length=10, choices=MOMENTOS, default=ASIGNACION)
    ronda = models.PositiveSmallIntegerField(default=0, help_text="Ronda de revisión a la que corresponde (en una corrección, la que sigue a la devolución).")
    nota = models.CharField(max_length=200, blank=True)
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    fecha = models.DateTimeField(auto_now_add=True)

    purgado = models.BooleanField(default=False, help_text="El archivo ya se borró (limpieza automática de videos).")
    purgado_en = models.DateTimeField(null=True, blank=True)

    @property
    def es_imagen(self):
        return self.tipo.startswith('image/') or self.archivo.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic'))

    @property
    def es_video(self):
        from apps.core.archivos import es_video
        return es_video(self.nombre_original or self.archivo.name, self.tipo)

    def __str__(self):
        return f"Referencia de {self.tarea_id}: {self.nombre_original}"

    class Meta:
        verbose_name = "Referencia"
        verbose_name_plural = "Referencias"
        ordering = ['fecha', 'id']


class HistorialTarea(models.Model):
    """Quién hizo qué y cuándo: el resultado de cada tarea es verificable."""
    ACCIONES = [
        ('CREADA', 'Creada'),
        ('EDITADA', 'Editada'),
        ('INICIADA', 'Iniciada'),
        ('ENTREGADA', 'Entregada'),
        ('VALIDADA', 'Validada'),
        ('DEVUELTA', 'Devuelta'),
        ('REABIERTA', 'Reabierta'),
        ('CANCELADA', 'Cancelada'),
        ('BLOQUEADA', 'Bloqueada'),
        ('DESBLOQUEADA', 'Desbloqueada'),
    ]
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, related_name="historial")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    accion = models.CharField(max_length=20, choices=ACCIONES)
    comentario = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historial de tarea"
        verbose_name_plural = "Historial de tareas"
        ordering = ['fecha', 'id']


class Notificacion(models.Model):
    """Avisos de la campanita: asignaciones, entregas, validaciones, devoluciones y reconocimientos."""
    TIPOS = [
        ('ASIGNADA', 'Tarea asignada'),
        ('ENTREGADA', 'Entrega por validar'),
        ('VALIDADA', 'Tarea validada'),
        ('DEVUELTA', 'Tarea devuelta'),
        ('REABIERTA', 'Tarea reabierta'),
        ('VENCE', 'Tarea por vencer'),
        ('EMPLEADO_MES', 'Empleado del Mes'),
        ('RECORDATORIO', 'Recordatorio del supervisor'),
        ('PIDE_TRABAJO', 'Pide más trabajo'),
        ('ORDEN', 'Orden de trabajo'),
        ('PROYECTO', 'Proyecto'),
        ('MENCION', 'Te mencionaron'),
        ('FINANZAS', 'Finanzas'),
        ('AUTOMATIZACION', 'Automatización'),
        ('ASISTENCIA', 'Asistencia'),
        ('ALMUERZO_HORA', 'Es la hora del almuerzo'),
        ('ALMUERZO_FIN', 'El almuerzo está por terminar'),
        ('ALMUERZO_EXCESO', 'Te pasaste del almuerzo'),
        ('MONITOREO', 'Monitoreo'),
        ('TALENTO', 'Talento y evaluaciones'),
        ('SEGURIDAD', 'Seguridad de la cuenta'),
        ('MODIFICADA', 'Tarea modificada'),
        ('BLOQUEADA', 'Tarea bloqueada'),
        ('COLABORACION', 'Colaboración'),
        ('ACTIVIDAD', 'Actividad adicional'),
        ('DOCUMENTO', 'Documento compartido'),
    ]
    destinatario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notificaciones")
    remitente = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                                  help_text="Quién provocó el aviso (vacío = la plataforma).")
    tipo = models.CharField(max_length=20, choices=TIPOS)
    titulo = models.CharField(max_length=255)
    mensaje = models.TextField(blank=True)
    enlace = models.CharField(max_length=255, blank=True)
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    leida = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ['-fecha', '-id']
        indexes = [models.Index(fields=['destinatario', 'leida'])]


class TareaRecurrente(models.Model):
    """Molde de una tarea que se repite (p. ej. la programación semanal de Adzone TV)."""
    FRECUENCIAS = [('SEMANAL', 'Cada semana'), ('MENSUAL', 'Cada mes')]
    DIAS_SEMANA = [(0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo')]

    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True)
    colaborador = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tareas_recurrentes")
    kpi_asignado = models.ForeignKey(KPIAsignado, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    prioridad = models.CharField(max_length=10, choices=Tarea.PRIORIDAD_CHOICES, default='MEDIA')
    frecuencia = models.CharField(max_length=10, choices=FRECUENCIAS, default='SEMANAL')
    dia_semana = models.PositiveSmallIntegerField(choices=DIAS_SEMANA, default=4,
                                                  help_text="Día de entrega, para las semanales.")
    dia_mes = models.PositiveSmallIntegerField(default=28, help_text="Día de entrega (1-28), para las mensuales.")
    inicio = models.DateField(help_text="Desde cuándo se generan.")
    activa = models.BooleanField(default=True)
    creada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    generada_hasta = models.DateField(null=True, blank=True,
                                      help_text="Última fecha de entrega ya creada como tarea.")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.titulo} ({self.get_frecuencia_display().lower()}, {self.colaborador.username})"

    class Meta:
        verbose_name = "Tarea recurrente"
        verbose_name_plural = "Tareas recurrentes"
        ordering = ['colaborador__first_name', 'titulo']


class ConfiguracionDesempeno(models.Model):
    """Reglas del puntaje y del bono. Una sola fila; se cambia en Administración → Configuración."""
    peso_tareas = models.PositiveSmallIntegerField(default=40, help_text="% del puntaje que sale del cumplimiento de las tareas.")
    peso_calidad = models.PositiveSmallIntegerField(
        default=15, help_text="% del puntaje de calidad y satisfacción: estrellas de las tareas, % a la primera y evaluación "
                              "del supervisor. Con 0, la calidad se promedia dentro de cada tarea.")
    peso_jornada = models.PositiveSmallIntegerField(
        default=10, help_text="% del puntaje de asistencia y puntualidad (adherencia al horario). La actividad en la "
                              "computadora no da puntos. Lo que queda (100 − tareas − calidad − asistencia) es de los KPIs.")
    nota_tarde = models.PositiveSmallIntegerField(default=50, help_text="Puntualidad de una entrega tarde (0-100).")
    minimo_tareas_empleado_mes = models.PositiveSmallIntegerField(
        default=3, help_text="Tareas validadas mínimas en el mes para ser candidato a Empleado del Mes.")
    puntaje_minimo = models.PositiveSmallIntegerField(
        default=70, help_text="Puntaje mínimo de desempeño del mes (0-100). Por debajo, la persona sale marcada.")
    minimo_tareas_evaluacion = models.PositiveSmallIntegerField(
        default=3, help_text="Tareas que ya cuentan en el mes para juzgar el mínimo. Con menos (y sin KPIs medidos), "
                             "la persona sale como «pocos datos» y no como incumplimiento.")
    dias_conservar_zip_chat = models.PositiveSmallIntegerField(
        default=30, help_text="Días que se conservan los archivos ZIP enviados por el chat; pasados se borran solos (el mensaje queda con el aviso).")
    dias_conservar_videos_chat = models.PositiveSmallIntegerField(
        default=14, help_text="Días que se conservan los videos enviados por el chat antes de borrarse solos para liberar espacio.")
    dias_conservar_videos = models.PositiveSmallIntegerField(
        default=7, help_text="Días que se conservan los videos de una tarea después de validada; luego se borran solos para liberar espacio. Con 0 se borran al validarla.")
    max_recordatorios = models.PositiveSmallIntegerField(
        default=15, help_text="Cuántas veces se puede recordar una misma tarea (0 = sin límite).")
    revisores_propias = models.ManyToManyField(
        User, blank=True, related_name='+',
        help_text="Quién puede validar las tareas que la gente se asigna a sí misma. Vacío: cualquiera de Dirección.")
    espera_recordatorio_min = models.PositiveSmallIntegerField(
        default=2, help_text="Minutos que deben pasar antes de volver a enviar un recordatorio de la misma tarea (0 = sin espera).")
    tramos_bono = models.JSONField(
        default=list, blank=True,
        help_text='Bono sugerido según el puntaje, p. ej. [{"desde": 100, "porcentaje": 10}, '
                  '{"desde": 80, "porcentaje": 10, "proporcional": true}]. «Proporcional»: porcentaje × puntaje ÷ 100.')
    fecha_modificacion = models.DateTimeField(auto_now=True)

    # Política de las descripciones de puesto: 100 % → 10 % del salario; 80 %-99 % → proporcional; menos de 80 % → nada.
    TRAMOS_POR_DEFECTO = [{"desde": 100, "porcentaje": 10}, {"desde": 80, "porcentaje": 10, "proporcional": True}]
    TRAMOS_ANTERIORES = [{"desde": 90, "porcentaje": 10}, {"desde": 80, "porcentaje": 5}]

    @property
    def peso_kpis(self):
        return max(0, 100 - self.peso_tareas - self.peso_calidad - self.peso_jornada)

    @classmethod
    def actual(cls):
        obj = cls.objects.order_by('id').first()
        if obj is None:
            obj = cls.objects.create(tramos_bono=cls.TRAMOS_POR_DEFECTO)
        return obj

    def bono_para(self, puntaje):
        if puntaje is None:
            return 0
        for tramo in sorted(self.tramos_bono or [], key=lambda t: -float(t.get('desde', 0))):
            if puntaje >= float(tramo.get('desde', 0)):
                porcentaje = float(tramo.get('porcentaje', 0))
                if tramo.get('proporcional'):
                    porcentaje = porcentaje * min(float(puntaje), 100.0) / 100
                return round(porcentaje, 2)
        return 0

    class Meta:
        verbose_name = "Configuración del desempeño"
        verbose_name_plural = "Configuración del desempeño"


class ResumenSemanal(models.Model):
    """El resumen de la semana para la Dirección: qué va bien, qué OT están en riesgo y dónde se pierde dinero."""
    semana = models.DateField(unique=True, help_text="Lunes de la semana resumida.")
    datos = models.JSONField(default=dict)
    texto = models.TextField()
    con_ia = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-semana']
        verbose_name = 'Resumen semanal'


# ---------------------------------------------------------------------------
# Disponibilidad, actividades adicionales y colaboración (12.4)
# ---------------------------------------------------------------------------
class EsperaAsignacion(models.Model):
    """La persona terminó todo y avisó a su supervisor: queda «en espera de asignación» hasta que le llegue una tarea."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="esperas")
    desde = models.DateTimeField(auto_now_add=True)
    hasta = models.DateTimeField(null=True, blank=True, help_text="Vacío mientras sigue esperando.")
    tarea_recibida = models.ForeignKey(Tarea, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                                       help_text="La tarea con la que terminó la espera.")

    @property
    def minutos(self):
        from django.utils import timezone
        return int(((self.hasta or timezone.now()) - self.desde).total_seconds() // 60)

    class Meta:
        verbose_name = "Espera de asignación"
        verbose_name_plural = "Esperas de asignación"
        ordering = ['-desde']
        indexes = [models.Index(fields=['usuario', 'hasta'])]


class ActividadAdicional(models.Model):
    """Lo que la persona hace por iniciativa propia (sobre todo mientras espera tareas). El supervisor la valida."""
    TIPOS = [
        ('DOCUMENTACION', 'Organizar y actualizar archivos y documentación'),
        ('ESTUDIO', 'Estudiar políticas, procedimientos y documentación interna'),
        ('CAPACITACION', 'Capacitación y aprendizaje'),
        ('APOYO', 'Apoyo a compañeros'),
        ('OTRO_DEPARTAMENTO', 'Colaboración con otro departamento (autorizada)'),
        ('MEJORA', 'Oportunidad de mejora en un proceso'),
        ('OTRA', 'Otra actividad de sus funciones'),
    ]
    ESTADOS = [('REGISTRADA', 'Por validar'), ('VALIDADA', 'Validada'), ('NO_VALIDADA', 'No validada')]
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="actividades_adicionales")
    fecha = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPOS)
    descripcion = models.TextField(help_text="Qué hizo.")
    resultado = models.TextField(blank=True, help_text="Qué quedó (documento, mejora propuesta, lo aprendido…).")
    minutos = models.PositiveIntegerField(default=0)
    proyecto = models.ForeignKey('operaciones.Proyecto', on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    estado = models.CharField(max_length=12, choices=ESTADOS, default='REGISTRADA')
    validada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    fecha_validacion = models.DateTimeField(null=True, blank=True)
    comentario_supervisor = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Actividad adicional"
        verbose_name_plural = "Actividades adicionales"
        ordering = ['-fecha', '-id']
        indexes = [models.Index(fields=['usuario', 'fecha'])]


class Colaboracion(models.Model):
    """
    Una persona apoya a otra. Flujo: SOLICITADA (alguien pide ayuda) → ACEPTADA → REALIZADA (con resultado)
    → VALIDADA / NO_VALIDADA por el supervisor de quien ayudó. También se puede registrar un apoyo ya dado (REALIZADA).
    """
    ESTADOS = [('SOLICITADA', 'Solicitada'), ('ACEPTADA', 'Aceptada'), ('RECHAZADA', 'No pudo'),
               ('REALIZADA', 'Realizada (por validar)'), ('VALIDADA', 'Validada'), ('NO_VALIDADA', 'No validada')]
    solicitante = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ayudas_pedidas",
                                    help_text="Quién necesita (o recibió) el apoyo.")
    ayudante = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ayudas_dadas",
                                 help_text="Quién da el apoyo.")
    registrada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    tarea = models.ForeignKey(Tarea, on_delete=models.SET_NULL, null=True, blank=True, related_name="colaboraciones")
    proyecto = models.ForeignKey('operaciones.Proyecto', on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    descripcion = models.TextField(help_text="En qué se necesita (o se dio) el apoyo.")
    resultado = models.TextField(blank=True)
    minutos = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=12, choices=ESTADOS, default='SOLICITADA')
    motivo = models.TextField(blank=True, help_text="Por qué no pudo ayudar o por qué no se validó.")
    validada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    fecha_validacion = models.DateTimeField(null=True, blank=True)
    fecha_realizada = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Colaboración"
        verbose_name_plural = "Colaboraciones"
        ordering = ['-fecha_creacion', '-id']
