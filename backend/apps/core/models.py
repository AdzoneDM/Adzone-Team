from django.db import models


class Departamento(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Departamento")
    descripcion = models.CharField(max_length=255, blank=True, verbose_name="Qué hace")
    color = models.CharField(max_length=7, default='#2f3a4f', verbose_name="Color del texto",
                             help_text="Hex, p. ej. #1d4189. Se usa en etiquetas y gráficos.")
    color_fondo = models.CharField(max_length=7, default='#eef1f6', verbose_name="Color de fondo")
    orden = models.PositiveSmallIntegerField(default=0, verbose_name="Orden en las listas")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Modificación")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Departamento"
        verbose_name_plural = "Departamentos"
        ordering = ['orden', 'nombre']
