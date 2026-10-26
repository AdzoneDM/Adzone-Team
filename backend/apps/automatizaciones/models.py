"""Reglas «cuando pase X, haz Y», como las recetas de Monday.com. También avisan a n8n por webhook."""
from django.contrib.auth.models import User
from django.db import models

EVENTOS = [
    ('ORDEN_CREADA', 'Se pide una orden de trabajo'),
    ('ORDEN_ESTADO', 'Una orden cambia de estado'),
    ('ORDEN_VENCIDA', 'Una orden pasa su fecha comprometida'),
    ('TAREA_ENTREGADA', 'Se entrega una tarea'),
    ('TAREA_VALIDADA', 'Se valida una tarea'),
    ('TAREA_VENCIDA', 'Una tarea se vence sin entregar'),
    ('COTIZACION_APROBADA', 'El cliente aprueba una cotización'),
    ('FACTURA_EMITIDA', 'Se emite una factura'),
    ('FACTURA_VENCIDA', 'Una factura vence sin cobrarse'),
    ('PAGO_RECIBIDO', 'Se registra un pago'),
]
ACCIONES = [
    ('AVISAR', 'Avisar en la campanita'),
    ('CREAR_TAREA', 'Crear una tarea'),
    ('WEBHOOK', 'Enviar a n8n (webhook)'),
]


class Regla(models.Model):
    nombre = models.CharField(max_length=150)
    activa = models.BooleanField(default=True)
    evento = models.CharField(max_length=24, choices=EVENTOS)
    condiciones = models.JSONField(default=dict, blank=True,
                                   help_text="Filtros opcionales: area (de producción), estado, departamento_id.")
    accion = models.CharField(max_length=12, choices=ACCIONES)
    parametros = models.JSONField(default=dict, blank=True,
                                  help_text="AVISAR: a (lista), usuario_id, mensaje. CREAR_TAREA: titulo, asignar, usuario_id, dias. WEBHOOK: url.")
    creada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    veces = models.PositiveIntegerField(default=0)
    ultima_vez = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Regla de automatización"
        verbose_name_plural = "Reglas de automatización"
        ordering = ['evento', 'nombre']


class Ejecucion(models.Model):
    """Bitácora: qué regla se ejecutó, sobre qué y si funcionó. También evita repetir los avisos diarios."""
    regla = models.ForeignKey(Regla, on_delete=models.CASCADE, related_name='ejecuciones')
    objeto = models.CharField(max_length=60, help_text="Ej.: orden:12, factura:4")
    resultado = models.CharField(max_length=255)
    exito = models.BooleanField(default=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
        indexes = [models.Index(fields=['regla', 'objeto'])]
