"""
Gestión del talento: evaluaciones (autoevaluación, supervisor y compañeros — 360°), planes de mejora, expediente
del colaborador (reconocimientos, observaciones, amonestaciones, incidencias, capacitación), historial de salario y
bonos, y la auditoría de los cambios administrativos de toda la plataforma.
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

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


# ------------------------------------------------------------------ Políticas y cumplimiento
class Politica(models.Model):
    CATEGORIAS = [('REGLAMENTO', 'Reglamento interno'), ('ASISTENCIA', 'Asistencia y puntualidad'), ('PERMISOS', 'Permisos y vacaciones'),
                  ('TECNOLOGIA', 'Uso de computadoras e internet'), ('MONITOREO', 'Monitoreo y privacidad'), ('DATOS', 'Protección de datos'),
                  ('SEGURIDAD', 'Seguridad informática'), ('EQUIPOS', 'Equipos de la empresa'), ('REMOTO', 'Trabajo remoto'),
                  ('IA', 'Inteligencia artificial'), ('REDES', 'Redes sociales'), ('VEHICULOS', 'Vehículos y herramientas'),
                  ('CALIDAD', 'Calidad y entregas'), ('DISCIPLINA', 'Disciplina'), ('OTRA', 'Otra')]
    clave = models.SlugField(max_length=40, unique=True)
    codigo = models.CharField(max_length=12, blank=True, default='', help_text="POL-001, POL-002… (se asigna solo)")
    responsable = models.CharField(max_length=120, blank=True, default='', help_text="Quién responde por la política (puesto o área).")
    titulo = models.CharField(max_length=150)
    categoria = models.CharField(max_length=12, choices=CATEGORIAS, default='OTRA')
    resumen = models.CharField(max_length=300, blank=True, help_text="Lo esencial en una o dos líneas.")
    contenido = models.TextField(help_text="Texto completo. Admite párrafos y listas con guiones.")
    version = models.PositiveIntegerField(default=1)
    vigente_desde = models.DateField(default=timezone.localdate)
    para_todos = models.BooleanField(default=True, help_text="Toda la empresa. Si no, solo los departamentos y puestos elegidos.")
    departamentos = models.ManyToManyField('core.Departamento', blank=True, related_name='politicas')
    puestos = models.ManyToManyField('organizacion.PuestoDeTrabajo', blank=True, related_name='politicas')
    requiere_aceptacion = models.BooleanField(default=True)
    activa = models.BooleanField(default=True)
    borrador = models.BooleanField(default=False, help_text="Borrador: solo la administración la ve.")
    actualizada = models.DateTimeField(auto_now=True)
    creada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')

    class Meta:
        ordering = ['categoria', 'titulo']
        verbose_name = 'Política'

    def save(self, *args, **kwargs):
        if not self.codigo:
            ultimo = Politica.objects.filter(codigo__startswith='POL-').order_by('-codigo').values_list('codigo', flat=True).first()
            n = int(ultimo[4:]) + 1 if ultimo and ultimo[4:].isdigit() else 1
            self.codigo = f'POL-{n:03d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.titulo} (v{self.version})'


class VersionPolitica(models.Model):
    """Historial: el texto exacto de cada versión, para saber qué aceptó cada quien."""
    politica = models.ForeignKey(Politica, on_delete=models.CASCADE, related_name='versiones')
    version = models.PositiveIntegerField()
    titulo = models.CharField(max_length=150)
    contenido = models.TextField()
    cambio = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')

    class Meta:
        unique_together = ('politica', 'version')
        ordering = ['-version']


class AceptacionPolitica(models.Model):
    politica = models.ForeignKey(Politica, on_delete=models.CASCADE, related_name='aceptaciones')
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='politicas_aceptadas')
    version = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    navegador = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('politica', 'usuario', 'version')
        ordering = ['-fecha']


# ------------------------------------------------------------------ Documentos del expediente
def _ruta_documento(instancia, nombre):
    import os
    import uuid
    return f'expedientes/{instancia.colaborador_id}/{uuid.uuid4().hex}{os.path.splitext(nombre)[1].lower()[:10]}'


class DocumentoEmpleado(models.Model):
    TIPOS = [('CONTRATO', 'Contrato de trabajo'), ('IDENTIFICACION', 'Copia de identificación'),
             ('CONFIDENCIALIDAD', 'Acuerdo de confidencialidad'), ('TITULO', 'Título académico'),
             ('CERTIFICACION', 'Certificación o curso'), ('CARTA', 'Carta o constancia'), ('ACTA', 'Acta firmada'),
             ('POLIZA', 'Póliza o seguro'), ('OTRO', 'Otro')]
    REQUERIDOS = ['CONTRATO', 'IDENTIFICACION', 'CONFIDENCIALIDAD']
    colaborador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documentos_laborales')
    tipo = models.CharField(max_length=16, choices=TIPOS)
    titulo = models.CharField(max_length=150)
    archivo = models.FileField(upload_to=_ruta_documento)
    emitido = models.DateField(null=True, blank=True)
    vence = models.DateField(null=True, blank=True, help_text="Contratos por tiempo definido, pólizas, licencias…")
    visible_al_colaborador = models.BooleanField(default=True)
    notas = models.CharField(max_length=255, blank=True)
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['colaborador__first_name', 'tipo', '-creado']
        verbose_name = 'Documento del empleado'
