
from django.db import models


class Departamento(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Departamento")
    descripcion = models.CharField(max_length=255, blank=True, verbose_name="Qué hace")
    color = models.CharField(max_length=7, default='#2f3a4f', verbose_name="Color del texto",
                             help_text="Hex, p. ej. #1d4189. Se usa en etiquetas y gráficos.")
    color_fondo = models.CharField(max_length=7, default='#eef1f6', verbose_name="Color de fondo")
    orden = models.PositiveSmallIntegerField(default=0, verbose_name="Orden en las listas")
    objetivos = models.TextField(blank=True, default='', verbose_name="Objetivos del área",
                                 help_text="Uno por línea. Se muestran en el espacio del departamento.")
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


class DosPasos(models.Model):
    """Verificación en dos pasos con app de códigos (Google o Microsoft Authenticator)."""
    usuario = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='dos_pasos')
    secreto = models.CharField(max_length=64)
    activo = models.BooleanField(default=False)
    ultimo_paso = models.BigIntegerField(default=0, help_text="Último intervalo de 30 s usado (un código no sirve dos veces).")
    respaldo = models.JSONField(default=list, blank=True, help_text="Códigos de respaldo de un solo uso (guardados cifrados).")
    activado = models.DateTimeField(null=True, blank=True)
    fallos = models.PositiveSmallIntegerField(default=0, help_text="Códigos equivocados seguidos (por persona, no por sesión).")
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Verificación en dos pasos'


class DispositivoConocido(models.Model):
    """Navegadores desde donde entró cada persona, para avisar cuando entra desde uno nuevo."""
    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='dispositivos_conocidos')
    huella = models.CharField(max_length=64)
    navegador = models.CharField(max_length=200, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    primero = models.DateTimeField(auto_now_add=True)
    ultimo = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('usuario', 'huella')
        verbose_name = 'Dispositivo conocido'


class SuscripcionPush(models.Model):
    """Un celular o navegador que recibe los avisos de la campanita como notificación (Web Push)."""
    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='suscripciones_push')
    endpoint = models.URLField(max_length=600, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    navegador = models.CharField(max_length=200, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Suscripción a notificaciones'


def _ruta_documento_area(instancia, nombre):
    import os
    import uuid
    return f'areas/{instancia.departamento_id}/{uuid.uuid4().hex}{os.path.splitext(nombre)[1].lower()[:10]}'


class DocumentoArea(models.Model):
    """Procedimientos, manuales, formularios y reportes de un departamento (su biblioteca de trabajo)."""
    TIPOS = [('PROCEDIMIENTO', 'Procedimiento'), ('MANUAL', 'Manual'), ('FORMULARIO', 'Formulario'), ('REPORTE', 'Reporte'), ('OTRO', 'Otro')]
    departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE, related_name='documentos_area')
    tipo = models.CharField(max_length=14, choices=TIPOS, default='PROCEDIMIENTO')
    titulo = models.CharField(max_length=150)
    resumen = models.CharField(max_length=300, blank=True)
    contenido = models.TextField(blank=True, help_text="Pasos o texto. Una línea por paso; «1.» o «-» al inicio para listas.")
    archivo = models.FileField(upload_to=_ruta_documento_area, blank=True, null=True)
    nombre_archivo = models.CharField(max_length=200, blank=True)
    solo_encargados = models.BooleanField(default=False, help_text="Solo lo ven el encargado, los supervisores del área y la Dirección.")
    version = models.PositiveIntegerField(default=1)
    actualizado = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        ordering = ['tipo', 'titulo']
        verbose_name = 'Documento del área'
