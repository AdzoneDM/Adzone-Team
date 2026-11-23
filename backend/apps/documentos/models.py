"""Documentos compartidos: archivos que una persona sube y envía a otras personas o a áreas completas, fuera del chat."""
import os
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


def _ruta(instancia, nombre):
    ext = os.path.splitext(nombre)[1].lower()[:10]
    return f'documentos/{timezone.localdate():%Y/%m}/{uuid.uuid4().hex}{ext}'


class DocumentoCompartido(models.Model):
    titulo = models.CharField(max_length=150)
    nota = models.CharField(max_length=300, blank=True)
    archivo = models.FileField(upload_to=_ruta)
    nombre_archivo = models.CharField(max_length=150)
    tamano = models.PositiveIntegerField(default=0)
    es_imagen = models.BooleanField(default=False)
    carpeta = models.CharField(max_length=60, blank=True, help_text="Para organizar: Contratos, Campañas, Reportes…")
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='documentos_subidos')
    # A quién se envía: personas y/o áreas completas. Sin nadie, es solo del que lo subió (su archivo personal).
    destinatarios = models.ManyToManyField(User, blank=True, related_name='documentos_recibidos')
    areas = models.ManyToManyField('core.Departamento', blank=True, related_name='documentos_compartidos')
    vistos = models.ManyToManyField(User, blank=True, related_name='documentos_vistos')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado', '-id']
        verbose_name = 'Documento compartido'
        verbose_name_plural = 'Documentos compartidos'

    def __str__(self):
        return self.titulo
