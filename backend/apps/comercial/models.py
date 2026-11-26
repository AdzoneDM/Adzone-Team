"""Oportunidades comerciales de Marketing y las solicitudes de servicio que generan para cada departamento.

Cliente (punto central) → Oportunidad (Marketing, del primer contacto a la contratación) → Solicitudes de servicio (una por
servicio y departamento, cada una con su propio estado y responsable) → Proyecto u orden de trabajo (se enlaza, no se copia).
"""
from django.contrib.auth.models import User
from django.db import models

from apps.core.models import Departamento
from apps.operaciones.models import Cliente, OrdenTrabajo, Proyecto, siguiente_numero

# código: (nombre, departamento sugerido)
SERVICIOS = {
    'REDES': ('Gestión de redes sociales', 'Marketing'),
    'PUBLICIDAD': ('Publicidad digital', 'Marketing'),
    'ESTRATEGIA': ('Estrategia digital', 'Marketing'),
    'FOTOGRAFIA': ('Fotografía', 'Audiovisual'),
    'VIDEO': ('Producción de video', 'Audiovisual'),
    'GRABACION': ('Grabación / cobertura', 'Audiovisual'),
    'WEB': ('Página web', 'Tecnología'),
    'SISTEMA': ('Sistema o aplicación', 'Tecnología'),
    'TV': ('Pauta en AdZone TV', 'Adzone TV'),
    'IMPRESION': ('Impresión', 'Impresión'),
    'OTRO': ('Otro servicio', None),
}


class Oportunidad(models.Model):
    ESTADOS = [
        ('NUEVO', 'Nuevo contacto'),
        ('CONTACTADO', 'Contactado'),
        ('EVALUACION', 'Evaluación de necesidades'),
        ('COTIZADA', 'Cotización enviada'),
        ('NEGOCIACION', 'En negociación'),
        ('APROBADA', 'Aprobado'),
        ('NO_CONCRETADA', 'No concretado'),
    ]
    CERRADOS = ('APROBADA', 'NO_CONCRETADA')

    codigo = models.CharField(max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='oportunidades')
    titulo = models.CharField(max_length=200)
    necesidades = models.TextField("Descripción de sus necesidades", blank=True)
    departamento = models.ForeignKey(Departamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='oportunidades',
                                     help_text="Departamento que lleva la oportunidad (normalmente Marketing).")
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='oportunidades_a_cargo')
    estado = models.CharField(max_length=14, choices=ESTADOS, default='NUEVO')
    fecha_contacto = models.DateField("Primer contacto", null=True, blank=True)
    proximo_seguimiento = models.DateField(null=True, blank=True)
    motivo_no_concretado = models.CharField(max_length=255, blank=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Oportunidad comercial'
        verbose_name_plural = 'Oportunidades comerciales'

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = siguiente_numero(Oportunidad, 'OPC', 'codigo')
        super().save(*args, **kwargs)

    @property
    def abierta(self):
        return self.estado not in self.CERRADOS

    def __str__(self):
        return f"{self.codigo} · {self.titulo}"


class SolicitudServicio(models.Model):
    ESTADOS = [
        ('RECIBIDA', 'Recibida'),
        ('EVALUACION', 'En evaluación'),
        ('COTIZADA', 'Cotización enviada'),
        ('APROBADA', 'Aprobada por el cliente'),
        ('EN_EJECUCION', 'En proyecto / orden'),
        ('NO_CONCRETADA', 'No concretada'),
    ]
    CERRADOS = ('EN_EJECUCION', 'NO_CONCRETADA')

    codigo = models.CharField(max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='solicitudes_servicio')
    oportunidad = models.ForeignKey(Oportunidad, on_delete=models.PROTECT, null=True, blank=True, related_name='solicitudes')
    servicio = models.CharField(max_length=12, choices=[(k, v[0]) for k, v in SERVICIOS.items()])
    servicio_detalle = models.CharField("Servicio (detalle)", max_length=150, blank=True)
    departamento = models.ForeignKey(Departamento, on_delete=models.PROTECT, related_name='solicitudes_servicio')
    descripcion = models.TextField("Descripción del requerimiento", blank=True)
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_a_cargo')
    estado = models.CharField(max_length=14, choices=ESTADOS, default='RECIBIDA')
    proyecto = models.ForeignKey(Proyecto, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_servicio')
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_servicio')
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Solicitud de servicio'
        verbose_name_plural = 'Solicitudes de servicio'

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = siguiente_numero(SolicitudServicio, 'SOL', 'codigo')
        super().save(*args, **kwargs)

    @property
    def servicio_nombre(self):
        if self.servicio == 'OTRO' and self.servicio_detalle:
            return self.servicio_detalle
        return SERVICIOS.get(self.servicio, (self.servicio,))[0]

    def __str__(self):
        return f"{self.codigo} · {self.servicio_nombre}"


class MovimientoComercial(models.Model):
    """Historial: quién creó, cambió, comentó o convirtió cada oportunidad y solicitud (no se edita ni se borra)."""
    TIPOS = [('CREADA', 'Creada'), ('ESTADO', 'Cambio de estado'), ('CAMBIO', 'Cambio de datos'), ('COMENTARIO', 'Comentario'),
             ('CONVERSION', 'Convertida en proyecto u orden')]
    oportunidad = models.ForeignKey(Oportunidad, on_delete=models.CASCADE, null=True, blank=True, related_name='movimientos')
    solicitud = models.ForeignKey(SolicitudServicio, on_delete=models.CASCADE, null=True, blank=True, related_name='movimientos')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    tipo = models.CharField(max_length=12, choices=TIPOS)
    estado_antes = models.CharField(max_length=14, blank=True)
    estado_despues = models.CharField(max_length=14, blank=True)
    texto = models.TextField(blank=True)
    cambios = models.JSONField(default=dict, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
