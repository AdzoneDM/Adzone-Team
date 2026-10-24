from django.db import models
from apps.organizacion.models import PuestoDeTrabajo # Importamos PuestoDeTrabajo
# Asegúrate de que la app 'puestos' está instalada y configurada correctamente
class PlantillaKPI(models.Model):
    nombre = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Nombre de la Plantilla de KPI"
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción del KPI"
    )
    unidad_medida = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Unidad de Medida",
        help_text="Ej: %, $, Unidades, Horas, Puntos, Escala 1-5"
    )
    menor_es_mejor = models.BooleanField(
        default=False,
        verbose_name="¿Menor es mejor?",
        help_text="Marcar si un valor más bajo indica mejor desempeño (ej: rondas de revisión, errores)."
    )
    # Podríamos añadir un campo 'tipo_dato_valor' si los valores de los KPIs
    # pueden ser de diferentes tipos (número, texto, booleano) y necesitamos validarlo.
    # tipo_dato_valor = models.CharField(max_length=20, choices=[('numero', 'Número'), ('texto', 'Texto')], default='numero')

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Modificación"
    )

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Plantilla de KPI"
        verbose_name_plural = "Plantillas de KPIs"
        ordering = ['nombre']



class KPIAsignado(models.Model):
    PERIODICIDAD_CHOICES = [
        ('MENSUAL', 'Mensual'),
        ('TRIMESTRAL', 'Trimestral'),
        ('SEMESTRAL', 'Semestral'),
        ('ANUAL', 'Anual'),
    ]

    puesto_trabajo = models.ForeignKey(
        PuestoDeTrabajo,
        on_delete=models.CASCADE, # Si se borra el puesto, se borran sus KPIs asignados
        related_name="kpis_asignados",
        verbose_name="Puesto de Trabajo"
    )
    plantilla_kpi = models.ForeignKey(
        PlantillaKPI,
        on_delete=models.PROTECT, # Proteger para no borrar plantillas en uso
        related_name="asignaciones",
        verbose_name="Plantilla de KPI"
    )
    ponderacion = models.DecimalField(
        max_digits=5, # Ej: 100.00
        decimal_places=2, # Dos decimales para el porcentaje
        verbose_name="Ponderación (%)",
        help_text="Peso del KPI para este puesto, ej: 20.00 para 20%"
    )
    objetivo_meta = models.CharField( # Usamos CharField para flexibilidad (ej. "Alcanzar X", ">90") o podría ser DecimalField si siempre es numérico
        max_length=255,
        verbose_name="Objetivo / Meta del KPI",
        help_text="Valor o descripción del objetivo a alcanzar para este KPI en este puesto."
    )
    periodicidad_objetivo = models.CharField(
        max_length=20,
        choices=PERIODICIDAD_CHOICES,
        default='MENSUAL',
        verbose_name="Periodicidad del Objetivo"
    )
    es_entrada_manual = models.BooleanField(
        default=True, # Por defecto, asumimos que el valor se ingresará manualmente
        verbose_name="¿Es de Entrada Manual?",
        help_text="Marcar si el valor de este KPI se ingresará manualmente por un Gerente/Admin."
    )
    meta_numerica = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Meta Numérica Mensual",
        help_text="Para KPIs que no son de entrada manual: cantidad de tareas validadas esperadas al mes."
    )
    # Podríamos añadir un campo 'formula_calculo' (TextField, opcional) para KPIs calculados en el futuro

    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion_asignacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True, verbose_name="¿Asignación Activa?")


    def __str__(self):
        return f"{self.plantilla_kpi.nombre} para {self.puesto_trabajo.nombre} (Peso: {self.ponderacion}%)"

    class Meta:
        verbose_name = "KPI Asignado a Puesto"
        verbose_name_plural = "KPIs Asignados a Puestos"
        # Asegurar que una plantilla de KPI solo se asigne una vez a un mismo puesto de trabajo
        unique_together = ('puesto_trabajo', 'plantilla_kpi')
        ordering = ['puesto_trabajo__nombre', 'plantilla_kpi__nombre']