
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


class AccesoEquipo(models.Model):
    """Clave general del equipo. Desbloquea en un dispositivo la lista de áreas y personas para
    elegir quién entra; no da acceso a nada más. Hay una sola fila."""
    clave = models.CharField(max_length=128, blank=True, verbose_name="Clave (cifrada)")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Modificación")

    def __str__(self):
        return "Clave general del equipo"

    class Meta:
        verbose_name = "Clave general del equipo"
        verbose_name_plural = "Clave general del equipo"


class PermisosDePerfil(models.Model):
    """Qué permite cada perfil de acceso (un grupo de Django). El catálogo de permisos está en apps/core/acceso.py."""
    grupo = models.OneToOneField('auth.Group', on_delete=models.CASCADE, related_name='permisos_acceso')
    descripcion = models.CharField(max_length=255, blank=True)
    permisos = models.JSONField(default=list, blank=True)
    orden = models.PositiveSmallIntegerField(default=50)

    class Meta:
        ordering = ['orden', 'grupo__name']
        verbose_name = 'Permisos de un perfil'

    def __str__(self):
        return self.grupo.name


class ExcepcionPermiso(models.Model):
    """Un permiso que se da o se quita a una persona, por encima de lo que dicen sus perfiles."""
    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='excepciones_permiso')
    permiso = models.CharField(max_length=40)
    conceder = models.BooleanField(default=True, help_text="Sí = se le da; No = se le quita aunque su perfil lo tenga.")
    motivo = models.CharField(max_length=200, blank=True)
    creado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='+')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'permiso')
        verbose_name = 'Excepción de permiso'


class EquipoExtra(models.Model):
    """Personas que alguien gestiona aunque no dependan de su puesto (p. ej. un coordinador de proyecto)."""
    jefe = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='equipo_extra')
    colaborador = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='jefes_extra')
    motivo = models.CharField(max_length=200, blank=True)
    hasta = models.DateField(null=True, blank=True, help_text="Vacío = sin fecha de fin.")
    creado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='+')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('jefe', 'colaborador')
        verbose_name = 'Equipo adicional'
