"""Asistente con IA: conversaciones (preguntas sobre los datos de la plataforma) e informes diarios de alertas.

La IA nunca recibe la base de datos: solo puede pedir datos con las herramientas de `herramientas.py`, que se ejecutan
aquí, son de solo lectura y responden únicamente con lo que la persona que pregunta ya puede ver.
"""
from django.contrib.auth.models import User
from django.db import models


class ConversacionIA(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversaciones_ia')
    titulo = models.CharField(max_length=120, blank=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-actualizada']


class MensajeIA(models.Model):
    """Cada turno tal como se envió o recibió de la API (`contenido`), para reenviar la conversación sin alterarla,
    y el texto visible. Las vueltas internas (llamadas a herramientas y sus resultados) quedan con `visible=False`."""
    conversacion = models.ForeignKey(ConversacionIA, on_delete=models.CASCADE, related_name='mensajes')
    rol = models.CharField(max_length=10)   # user | assistant
    contenido = models.JSONField()
    texto = models.TextField(blank=True)
    visible = models.BooleanField(default=True)
    herramientas = models.JSONField(default=list, blank=True)   # qué consultas hizo para responder
    tokens_entrada = models.PositiveIntegerField(default=0)
    tokens_salida = models.PositiveIntegerField(default=0)
    tokens_cache = models.PositiveIntegerField(default=0)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']


class InformeIA(models.Model):
    """Análisis diario de cada responsable (Dirección y quien gestiona un área): alertas con números y, si hay IA, su lectura."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='informes_ia')
    fecha = models.DateField()
    alertas = models.JSONField(default=list)
    texto = models.TextField(blank=True)
    con_ia = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'fecha')
        ordering = ['-fecha']
