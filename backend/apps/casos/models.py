"""Control y seguimiento operativo: incidencias, solicitudes y oportunidades de mejora de los procesos internos.

Operaciones recibe, registra, prioriza y deriva cada caso; el área competente designa a un responsable y lo atiende; Operaciones
documenta el cierre con su validación. Es un registro INDEPENDIENTE de los datos de origen: aquí solo se guarda una referencia
(«OT-26-0012», «tarea 381»…), nunca se cambia lo que se reporta.
"""
import os
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.core.models import Departamento
from apps.operaciones.models import siguiente_numero


class Caso(models.Model):
    TIPOS = [('INCIDENCIA', 'Incidencia'), ('SOLICITUD', 'Solicitud'), ('MEJORA', 'Oportunidad de mejora')]
    ESTADOS = [('RECIBIDO', 'Recibido'), ('EN_ATENCION', 'En atención'), ('PENDIENTE_VALIDACION', 'Pendiente de validación'),
               ('CERRADO', 'Cerrado')]
    ABIERTOS = ('RECIBIDO', 'EN_ATENCION', 'PENDIENTE_VALIDACION')
    PRIORIDADES = [('ALTA', 'Alta'), ('MEDIA', 'Media'), ('BAJA', 'Baja')]
    IMPACTOS = [('ALTO', 'Alto: detiene el trabajo o afecta a clientes'), ('MEDIO', 'Medio: lo retrasa o hay que rodearlo'),
                ('BAJO', 'Bajo: molesta, pero se puede seguir')]
    CATEGORIAS = [('ACCESOS', 'Accesos y permisos'), ('DATOS', 'Corrección de datos'), ('CONFIGURACION', 'Configuración'),
                  ('FUNCIONALIDAD', 'Funcionalidad de la plataforma'), ('PROCESO', 'Proceso o procedimiento'),
                  ('EQUIPOS', 'Equipos e infraestructura'), ('PERSONAL', 'Coordinación entre áreas'), ('OTRO', 'Otro')]
    TECNICAS = ('ACCESOS', 'DATOS', 'CONFIGURACION', 'FUNCIONALIDAD')   # las que requieren intervención de Tecnología

    codigo = models.CharField(max_length=20, unique=True, editable=False)
    tipo = models.CharField(max_length=12, choices=TIPOS, default='INCIDENCIA')
    categoria = models.CharField(max_length=14, choices=CATEGORIAS, default='OTRO')
    titulo = models.CharField(max_length=160)
    descripcion = models.TextField(max_length=4000)
    impacto = models.CharField("Impacto reportado", max_length=6, choices=IMPACTOS, default='MEDIO')
    referencia = models.CharField("Referencia al registro de origen", max_length=160, blank=True,
                                  help_text="Por ejemplo «OT-26-0012» o «tarea 381»: lo suficiente para encontrarlo, sin copiar datos.")
    reportado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='casos_reportados')
    area_origen = models.ForeignKey(Departamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='casos_originados')
    recibido = models.DateTimeField(default=timezone.now)

    # Lo que decide Operaciones
    prioridad = models.CharField(max_length=5, choices=PRIORIDADES, blank=True)
    area_asignada = models.ForeignKey(Departamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='casos_asignados')
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='casos_a_cargo')
    responsable_confirmado = models.BooleanField(default=False)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='RECIBIDO')
    proxima_revision = models.DateField(null=True, blank=True)
    fecha_estimada = models.DateField("Fecha estimada de resolución", null=True, blank=True)
    bloqueado = models.BooleanField(default=False)
    motivo_bloqueo = models.CharField(max_length=500, blank=True)
    # Cierre
    resultado = models.TextField(blank=True)
    validado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    validacion = models.CharField("Cómo se validó", max_length=500, blank=True)
    cerrado = models.DateTimeField(null=True, blank=True)
    reaperturas = models.PositiveSmallIntegerField(default=0)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-recibido']
        verbose_name = 'Caso operativo'
        verbose_name_plural = 'Casos operativos'
        indexes = [models.Index(fields=['estado', 'proxima_revision'])]

    def __str__(self):
        return f'{self.codigo} {self.titulo}'

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = siguiente_numero(Caso, 'CAS', campo='codigo', corto=True)
        super().save(*args, **kwargs)

    @property
    def abierto(self):
        return self.estado in self.ABIERTOS

    def vencido(self, hoy=None):
        """Abierto y pasó su fecha de revisión sin que se documentara el seguimiento (documentarlo mueve la fecha)."""
        hoy = hoy or timezone.localdate()
        return self.abierto and self.proxima_revision is not None and self.proxima_revision < hoy


class MovimientoCaso(models.Model):
    """Historial del caso: cada actuación queda con quién, cuándo y qué. No se edita ni se borra."""
    TIPOS = [('RECIBIDO', 'Recibido'), ('INFO', 'Información agregada'), ('CLASIFICADO', 'Clasificado'), ('DERIVADO', 'Derivado'),
             ('RESPONSABLE', 'Responsable designado'), ('CONFIRMADO', 'Responsable confirmado'), ('AVANCE', 'Avance'),
             ('BLOQUEO', 'Bloqueo'), ('DESBLOQUEO', 'Bloqueo resuelto'), ('REVISION', 'Próxima revisión'), ('ESCALADO', 'Escalado'),
             ('SOLUCION', 'Solución comunicada'), ('TECNICA', 'Respuesta de Tecnología'), ('VALIDADO', 'Validado'),
             ('CERRADO', 'Cerrado'), ('REABIERTO', 'Reabierto'), ('UNIDO', 'Reporte unido')]
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name='movimientos')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    tipo = models.CharField(max_length=12, choices=TIPOS)
    nota = models.TextField(blank=True, max_length=4000)
    datos = models.JSONField(default=dict, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['fecha', 'id']


def _ruta(instancia, nombre):
    ext = os.path.splitext(nombre)[1].lower()[:10]
    return f'casos/{timezone.localdate():%Y/%m}/{uuid.uuid4().hex}{ext}'


class EvidenciaCaso(models.Model):
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name='evidencias')
    archivo = models.FileField(upload_to=_ruta)
    nombre = models.CharField(max_length=150)
    tamano = models.PositiveIntegerField(default=0)
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['fecha']
