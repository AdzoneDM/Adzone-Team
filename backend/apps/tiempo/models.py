"""Registro de tiempo: el cronómetro y las horas anotadas a mano, por tarea, orden o proyecto."""
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

MAX_MINUTOS = 12 * 60  # un cronómetro olvidado no suma más de 12 horas


class RegistroTiempo(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='registros_tiempo')
    tarea = models.ForeignKey('desempeno.Tarea', on_delete=models.SET_NULL, null=True, blank=True, related_name='registros_tiempo')
    orden = models.ForeignKey('operaciones.OrdenTrabajo', on_delete=models.SET_NULL, null=True, blank=True, related_name='registros_tiempo')
    proyecto = models.ForeignKey('operaciones.Proyecto', on_delete=models.SET_NULL, null=True, blank=True, related_name='registros_tiempo')
    descripcion = models.CharField(max_length=255, blank=True)
    inicio = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True, help_text="Vacío mientras el cronómetro corre.")
    minutos = models.PositiveIntegerField(default=0)
    facturable = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    @property
    def corriendo(self):
        return self.fin is None

    def minutos_hasta_ahora(self):
        if self.fin:
            return self.minutos
        return min(MAX_MINUTOS, int((timezone.now() - self.inicio).total_seconds() // 60))

    def completar_desde_tarea(self):
        """Si se anotó en una tarea, hereda su orden y su proyecto."""
        if self.tarea_id:
            self.orden_id = self.orden_id or self.tarea.orden_id
            self.proyecto_id = self.proyecto_id or self.tarea.proyecto_id
        if self.orden_id and not self.proyecto_id:
            self.proyecto_id = self.orden.proyecto_id

    class Meta:
        ordering = ['-inicio']
        indexes = [models.Index(fields=['usuario', 'inicio'])]
