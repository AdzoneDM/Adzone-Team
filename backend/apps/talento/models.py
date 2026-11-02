"""
Gestión del talento: evaluaciones (autoevaluación, supervisor y compañeros — 360°), planes de mejora, expediente
del colaborador (reconocimientos, observaciones, amonestaciones, incidencias, capacitación), historial de salario y
bonos, y la auditoría de los cambios administrativos de toda la plataforma.
"""
from django.contrib.auth.models import User
from django.db import models

COMPETENCIAS = [
    ('calidad', 'Calidad del trabajo'),
    ('cumplimiento', 'Cumplimiento de plazos'),
    ('equipo', 'Trabajo en equipo'),
    ('comunicacion', 'Comunicación'),
    ('iniciativa', 'Iniciativa e innovación'),
    ('cliente', 'Orientación al cliente'),
    ('tecnica', 'Conocimiento técnico del puesto'),
    ('politicas', 'Cumplimiento de políticas y procedimientos'),
]
ESCALA = {1: 'Muy por debajo', 2: 'Por debajo', 3: 'Cumple', 4: 'Supera', 5: 'Excepcional'}


class CicloEvaluacion(models.Model):
    TIPOS = [('MENSUAL', 'Mensual'), ('TRIMESTRAL', 'Trimestral'), ('ANUAL', 'Anual')]
    nombre = models.CharField(max_length=80, help_text="Ej.: 4.º trimestre 2026")
    tipo = models.CharField(max_length=10, choices=TIPOS, default='TRIMESTRAL')
    desde = models.DateField()
    hasta = models.DateField()
    cierre = models.DateField(help_text="Fecha límite para enviar las evaluaciones.")
    con_pares = models.BooleanField(default=True, help_text="Incluye evaluación de compañeros (360°).")
    abierto = models.BooleanField(default=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-desde']

    def __str__(self):
        return self.nombre


class Evaluacion(models.Model):
    """Una evaluación de una persona por otra (o por sí misma) dentro de un ciclo."""
    TIPOS = [('AUTO', 'Autoevaluación'), ('SUPERVISOR', 'Supervisor'), ('PAR', 'Compañero')]
    ESTADOS = [('PENDIENTE', 'Pendiente'), ('ENVIADA', 'Enviada'), ('EN_REVISION', 'En revisión de la dirección'), ('CERRADA', 'Cerrada')]
    ciclo = models.ForeignKey(CicloEvaluacion, on_delete=models.CASCADE, related_name='evaluaciones')
    evaluado = models.ForeignKey(User, on_delete=models.CASCADE, related_name='evaluaciones_recibidas')
    evaluador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='evaluaciones_hechas')
    tipo = models.CharField(max_length=10, choices=TIPOS)
    estado = models.CharField(max_length=12, choices=ESTADOS, default='PENDIENTE')
    puntajes = models.JSONField(default=dict, blank=True, help_text="Competencia → 1 a 5.")
    fortalezas = models.TextField(blank=True)
    a_mejorar = models.TextField(blank=True)
    comentario = models.TextField(blank=True)
    enviada = models.DateTimeField(null=True, blank=True)
    revisada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
                                     help_text="Las evaluaciones bajas del supervisor las confirma la dirección antes de cerrarse.")
    nota_revision = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('ciclo', 'evaluado', 'evaluador', 'tipo')
        ordering = ['ciclo', 'evaluado__first_name']

    @property
    def promedio(self):
        v = [int(x) for x in (self.puntajes or {}).values() if str(x).isdigit()]
        return round(sum(v) / len(v), 2) if v else None


class PlanMejora(models.Model):
    ESTADOS = [('ABIERTO', 'En curso'), ('CUMPLIDO', 'Cumplido'), ('NO_CUMPLIDO', 'No cumplido'), ('CANCELADO', 'Cancelado')]
    colaborador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='planes_mejora')
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    motivo = models.TextField(help_text="Qué se observó: KPI bajo el umbral, evaluación, incidencias…")
    kpi = models.ForeignKey('kpis.PlantillaKPI', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    objetivos = models.JSONField(default=list, help_text='[{"texto": "...", "meta": "...", "fecha": "AAAA-MM-DD", "cumplido": false}]')
    capacitacion = models.TextField(blank=True, help_text="Capacitación o acompañamiento asignado.")
    inicio = models.DateField()
    revision = models.DateField(help_text="Fecha de revisión del plan.")
    estado = models.CharField(max_length=12, choices=ESTADOS, default='ABIERTO')
    resultado = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-inicio']


class EventoExpediente(models.Model):
    TIPOS = [('RECONOCIMIENTO', 'Reconocimiento'), ('OBSERVACION', 'Observación'), ('AMONESTACION_VERBAL', 'Amonestación verbal'),
             ('AMONESTACION_ESCRITA', 'Amonestación escrita'), ('INCIDENCIA', 'Incidencia'), ('CAPACITACION', 'Capacitación'),
             ('BONO', 'Bono'), ('OTRO', 'Otro')]
    colaborador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expediente')
    tipo = models.CharField(max_length=22, choices=TIPOS)
    fecha = models.DateField()
    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Para bonos.")
    horas = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, help_text="Para capacitaciones.")
    visible_al_colaborador = models.BooleanField(default=True)
    justificacion = models.TextField(blank=True, help_text="Descargo o justificación del colaborador.")
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-creado']


class CambioSalarial(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cambios_salario')
    fecha = models.DateField()
    anterior = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    nuevo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    motivo = models.CharField(max_length=200, blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')

    class Meta:
        ordering = ['-fecha', '-id']


class AuditoriaCambio(models.Model):
    """Quién cambió qué y cuándo: metas y pesos de KPIs, reglas del puntaje, salarios, marcajes, monitoreo, evaluaciones."""
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    accion = models.CharField(max_length=60)
    objeto = models.CharField(max_length=200)
    antes = models.JSONField(null=True, blank=True)
    despues = models.JSONField(null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-fecha']
