import os
import uuid

from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Departamento
from apps.kpis.models import KPIAsignado


class Tarea(models.Model):
    # Flujo: PENDIENTE → EN_PROGRESO → EN_REVISION (entregada) → COMPLETADA (validada).
    # Si el supervisor rechaza la entrega, vuelve a EN_PROGRESO con un comentario.
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROGRESO', 'En progreso'),
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
    fecha_hecho = models.DateTimeField(null=True, blank=True)

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

    @property
    def es_imagen(self):
        return self.tipo.startswith('image/') or self.archivo.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic'))

    def __str__(self):
        return f"Evidencia de {self.tarea_id}: {self.nombre_original}"

    class Meta:
        verbose_name = "Evidencia"
        verbose_name_plural = "Evidencias"
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
    peso_tareas = models.PositiveSmallIntegerField(default=60, help_text="% del puntaje que sale de las tareas.")
    nota_tarde = models.PositiveSmallIntegerField(default=50, help_text="Puntualidad de una entrega tarde (0-100).")
    minimo_tareas_empleado_mes = models.PositiveSmallIntegerField(
        default=3, help_text="Tareas validadas mínimas en el mes para ser candidato a Empleado del Mes.")
    tramos_bono = models.JSONField(
        default=list, blank=True,
        help_text='Bono sugerido según el puntaje del mes, p. ej. [{"desde": 90, "porcentaje": 10}, {"desde": 80, "porcentaje": 5}].')
    fecha_modificacion = models.DateTimeField(auto_now=True)

    TRAMOS_POR_DEFECTO = [{"desde": 90, "porcentaje": 10}, {"desde": 80, "porcentaje": 5}]

    @property
    def peso_kpis(self):
        return 100 - self.peso_tareas

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
                return float(tramo.get('porcentaje', 0))
        return 0

    class Meta:
        verbose_name = "Configuración del desempeño"
        verbose_name_plural = "Configuración del desempeño"
