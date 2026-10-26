from django.db import models
from apps.core.models import Departamento
from django.contrib.auth.models import User # Necesario para PerfilUsuario

class PuestoDeTrabajo(models.Model):
    nombre = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Nombre del Puesto"
    )
    departamento = models.ForeignKey(
        Departamento,
        on_delete=models.CASCADE,
        related_name="puestos_de_trabajo",
        verbose_name="Departamento"
    )
    # --- NUEVO CAMPO PARA SUPERVISOR ---
    supervisor = models.ForeignKey(
        'self', # Se relaciona consigo mismo
        on_delete=models.SET_NULL, # Si se borra el puesto supervisor, este campo se pone a NULL
        null=True, # Un puesto puede no tener supervisor (ej. el CEO)
        blank=True, # Permite que el campo esté vacío en formularios
        related_name='subordinados', # Desde un puesto, puedo acceder a sus subordinados
        verbose_name="Es Supervisado Por"
    )
    funciones_principales = models.TextField(
        blank=True,
        null=True,
        verbose_name="Funciones Principales"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Modificación"
    )

    def __str__(self):
        if self.supervisor:
            return f"{self.nombre} ({self.departamento.nombre}) - Supervisado por: {self.supervisor.nombre}"
        return f"{self.nombre} ({self.departamento.nombre})"

    class Meta:
        verbose_name = "Puesto de Trabajo"
        verbose_name_plural = "Puestos de Trabajo"
        ordering = ['departamento__nombre', 'nombre']

# ... (El modelo PerfilUsuario se mantiene igual) ...
class PerfilUsuario(models.Model):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        primary_key=True,
        related_name='perfil'
    )
    puesto_trabajo = models.ForeignKey(
        PuestoDeTrabajo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfiles_usuarios",
        verbose_name="Puesto de Trabajo"
    )
    horas_semana = models.DecimalField(
        max_digits=4, decimal_places=1, default=44, verbose_name="Horas por semana",
        help_text="Capacidad semanal para medir la carga (jornada legal en RD: 44 horas).")
    costo_hora = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Costo por hora (RD$)",
        help_text="Solo lo ve Finanzas. Sirve para calcular la rentabilidad de cada proyecto.")
    fecha_creacion_perfil = models.DateTimeField(auto_now_add=True)
    fecha_modificacion_perfil = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Perfil de {self.user.username}"

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"