"""
Monitoreo de actividad en las computadoras de ADZONE (agente de escritorio).

Qué se guarda, por minuto y solo en jornada (entre la entrada y la salida/pausa marcadas): la aplicación y el título
de la ventana en uso, el sitio si se reconoce, segundos con actividad e inactivos, nivel de actividad y cambios de
ventana. Capturas de pantalla solo si la administración las activa (desenfocadas por defecto).

Nunca: teclas, contraseñas, contenido de mensajes o correos, audio, cámara ni actividad fuera de jornada.
"""
import hashlib
import secrets
import uuid

from django.contrib.auth.models import User
from django.db import models

PRODUCTIVA, NEUTRAL, IMPRODUCTIVA = 'P', 'N', 'I'
CATEGORIAS = [(PRODUCTIVA, 'Productiva'), (NEUTRAL, 'Neutral'), (IMPRODUCTIVA, 'Improductiva')]

POLITICA = """ADZONE Digital Marketing SRL mide la actividad de sus computadoras de trabajo con el agente de Adzone Team para
conocer la productividad, distribuir mejor la carga y proteger los equipos (Código de Trabajo arts. 39 y 47; Ley 172-13).

1. Solo se mide en jornada: desde que marcas entrada hasta que marcas pausa o salida. Fuera de eso el agente no registra nada.
2. Se registra por minuto: la aplicación y el título de la ventana en uso, el sitio cuando se reconoce, si hubo actividad
   (teclado o ratón, sin guardar qué se escribe) y cuántas veces cambias de ventana.
3. Capturas de pantalla: solo si la administración las activa; se toman cada cierto tiempo, desenfocadas por defecto, y
   se borran solas a los 30 días.
4. Nunca se registran teclas, contraseñas, el contenido de mensajes o correos, audio ni cámara.
5. Ves tus propios datos en «Mi actividad», igual que tu supervisor. Solo tu cadena de supervisión y la administración
   pueden verlos. Los datos se borran a los 90 días.
6. El agente está siempre visible en la barra de tareas. Para gestiones personales, marca una pausa.
7. Puedes pedir acceso, corrección o explicación de tus datos a la administración (derechos de la Ley 172-13)."""


class ConfiguracionMonitoreo(models.Model):
    activo = models.BooleanField(default=True, help_text="Apagado, ningún agente registra.")
    umbral_inactivo_seg = models.PositiveSmallIntegerField(default=180, help_text="Sin teclado ni ratón por este tiempo = inactivo.")
    capturas = models.BooleanField(default=False, help_text="Tomar capturas de pantalla en jornada.")
    capturas_cada_min = models.PositiveSmallIntegerField(default=10)
    desenfocar_capturas = models.BooleanField(default=True)
    alerta_inactivo_min = models.PositiveSmallIntegerField(default=20, help_text="Aviso al supervisor tras estos minutos inactivo en jornada.")
    alerta_sin_pc_min = models.PositiveSmallIntegerField(default=30, help_text="Aviso si marcó entrada y su computadora no reporta en este tiempo.")
    alerta_improductivo_pct = models.PositiveSmallIntegerField(default=30, help_text="Aviso si el tiempo improductivo del día pasa este %.")
    meta_productividad_pct = models.PositiveSmallIntegerField(default=75, help_text="Meta de % productivo para el KPI automático.")
    retencion_dias = models.PositiveSmallIntegerField(default=90)
    retencion_capturas_dias = models.PositiveSmallIntegerField(default=30)
    version_politica = models.CharField(max_length=10, default='1.0')
    texto_politica = models.TextField(default=POLITICA)

    class Meta:
        verbose_name = 'Configuración del monitoreo'

    @classmethod
    def actual(cls):
        obj = cls.objects.order_by('id').first()
        return obj or cls.objects.create()


class Dispositivo(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dispositivos')
    nombre = models.CharField(max_length=100, help_text="Ej.: PC Diseño 2")
    sistema = models.CharField(max_length=60, blank=True)
    version_agente = models.CharField(max_length=20, blank=True)
    token_hash = models.CharField(max_length=64, unique=True)
    prefijo = models.CharField(max_length=8)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    ultimo_contacto = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['usuario__first_name', 'nombre']

    @staticmethod
    def hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def crear(cls, usuario, nombre):
        token = 'adz_' + secrets.token_urlsafe(32)
        d = cls.objects.create(usuario=usuario, nombre=nombre[:100], token_hash=cls.hash(token), prefijo=token[4:12])
        return d, token


class Consentimiento(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consentimientos_monitoreo')
    version = models.CharField(max_length=10)
    aceptado_en = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        unique_together = ('usuario', 'version')


class Actividad(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='actividad_pc')
    dispositivo = models.ForeignKey(Dispositivo, on_delete=models.SET_NULL, null=True, blank=True, related_name='actividad')
    minuto = models.DateTimeField()
    activos = models.PositiveSmallIntegerField(default=0, help_text="Segundos del minuto con actividad.")
    inactivos = models.PositiveSmallIntegerField(default=0)
    intensidad = models.PositiveSmallIntegerField(default=0, help_text="% de muestras del minuto con teclado o ratón.")
    cambios = models.PositiveSmallIntegerField(default=0, help_text="Cambios de ventana en el minuto.")
    app = models.CharField(max_length=100, blank=True)
    titulo = models.CharField(max_length=255, blank=True)
    dominio = models.CharField(max_length=150, blank=True)
    categoria = models.CharField(max_length=1, choices=CATEGORIAS, default=NEUTRAL)
    registro = models.ForeignKey('tiempo.RegistroTiempo', on_delete=models.SET_NULL, null=True, blank=True, related_name='actividad',
                                 help_text="Cronómetro (tarea, OT o proyecto) que corría en ese minuto.")
    justificada = models.BooleanField(default=False, help_text="Un supervisor aprobó que ese tiempo fue trabajo; no se reclasifica.")

    class Meta:
        unique_together = ('usuario', 'minuto')  # un minuto por persona aunque tenga dos computadoras
        indexes = [models.Index(fields=['usuario', 'minuto'])]
        ordering = ['minuto']


def _ruta_captura(instancia, nombre):
    return f'monitoreo/{instancia.tomada_en:%Y/%m/%d}/{instancia.usuario_id}-{uuid.uuid4().hex[:12]}.jpg'


class Captura(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='capturas')
    dispositivo = models.ForeignKey(Dispositivo, on_delete=models.SET_NULL, null=True, blank=True, related_name='capturas')
    tomada_en = models.DateTimeField()
    archivo = models.FileField(upload_to=_ruta_captura)
    desenfocada = models.BooleanField(default=True)
    app = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-tomada_en']


class ReglaProductividad(models.Model):
    TIPOS = [('APP', 'Aplicación'), ('DOMINIO', 'Sitio web'), ('TITULO', 'Texto en el título')]
    tipo = models.CharField(max_length=8, choices=TIPOS)
    patron = models.CharField(max_length=120, help_text="Sin distinguir mayúsculas: «photoshop», «youtube.com», «YouTube».")
    categoria = models.CharField(max_length=1, choices=CATEGORIAS)
    departamento = models.ForeignKey('core.Departamento', on_delete=models.CASCADE, null=True, blank=True,
                                     help_text="Vacío = para toda la empresa. Una regla del departamento gana sobre la general.")
    nota = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['tipo', 'patron']
        verbose_name = 'Regla de productividad'


class AlertaEnviada(models.Model):
    """Para no repetir el mismo aviso: una clave por persona y situación (p. ej. «inactivo-2026-11-02-10:40»)."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    clave = models.CharField(max_length=80)
    tipo = models.CharField(max_length=20)
    detalle = models.CharField(max_length=255, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'clave')
        ordering = ['-creada']


class Justificacion(models.Model):
    """La persona explica un tramo que el clasificador marcó como neutral o improductivo (ej.: YouTube para una referencia)."""
    ESTADOS = [('PENDIENTE', 'Pendiente'), ('APROBADA', 'Aprobada'), ('RECHAZADA', 'Rechazada')]
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='justificaciones_pc')
    desde = models.DateTimeField()
    hasta = models.DateTimeField()
    motivo = models.CharField(max_length=300)
    tarea = models.ForeignKey('desempeno.Tarea', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    estado = models.CharField(max_length=10, choices=ESTADOS, default='PENDIENTE')
    revisada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    nota = models.CharField(max_length=255, blank=True)
    minutos = models.PositiveIntegerField(default=0, help_text="Minutos que pasaron a productivos al aprobar.")
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada']


class PerfilMonitoreo(models.Model):
    """Como los perfiles de Teramind: qué se mide y cómo, por departamento o por persona."""
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)
    monitorear = models.BooleanField(default=True, help_text="Apagado: el agente de estas personas no registra (p. ej., dirección).")
    capturas = models.BooleanField(default=False)
    capturas_cada_min = models.PositiveSmallIntegerField(default=10)
    desenfocar_capturas = models.BooleanField(default=True)
    umbral_inactivo_seg = models.PositiveSmallIntegerField(default=180)
    departamentos = models.ManyToManyField('core.Departamento', blank=True, related_name='perfiles_monitoreo',
                                           help_text="Se aplica a todo el departamento, salvo a quien tenga un perfil propio.")
    personas = models.ManyToManyField(User, blank=True, related_name='perfiles_monitoreo',
                                      help_text="Asignación individual: gana sobre la del departamento.")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Perfil de monitoreo'

    def __str__(self):
        return self.nombre


class ReglaComportamiento(models.Model):
    """Reglas de comportamiento (como las de Teramind): si la persona usa X durante N minutos en el día, se registra o se avisa."""
    CAMPOS = [('APP', 'Aplicación'), ('DOMINIO', 'Sitio web'), ('TITULO', 'Texto en el título de la ventana')]
    RIESGOS = [('BAJO', 'Bajo'), ('MEDIO', 'Medio'), ('ALTO', 'Alto'), ('CRITICO', 'Crítico')]
    PESO = {'BAJO': 1, 'MEDIO': 3, 'ALTO': 6, 'CRITICO': 10}
    ACCIONES = [('REGISTRAR', 'Solo registrar'), ('ALERTAR', 'Registrar y avisar')]
    CATEGORIAS = [('PRODUCTIVIDAD', 'Productividad'), ('SEGURIDAD', 'Seguridad'), ('IA', 'Uso de IA'), ('CUMPLIMIENTO', 'Cumplimiento')]
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255, blank=True)
    categoria = models.CharField(max_length=14, choices=CATEGORIAS, default='PRODUCTIVIDAD')
    campo = models.CharField(max_length=8, choices=CAMPOS, default='DOMINIO')
    patrones = models.TextField(help_text="Uno por línea, sin distinguir mayúsculas. Sitios: el dominio y sus subdominios.")
    minutos_minimos = models.PositiveSmallIntegerField(default=1, help_text="Minutos en el día para que cuente como incidencia.")
    riesgo = models.CharField(max_length=8, choices=RIESGOS, default='MEDIO')
    accion = models.CharField(max_length=10, choices=ACCIONES, default='REGISTRAR')
    departamentos = models.ManyToManyField('core.Departamento', blank=True, related_name='+', help_text="Vacío = toda la empresa.")
    excluir_departamentos = models.ManyToManyField('core.Departamento', blank=True, related_name='+',
                                                   help_text="Departamentos donde es parte del trabajo (p. ej., AnyDesk en Tecnología).")
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['categoria', 'nombre']
        verbose_name = 'Regla de comportamiento'

    def __str__(self):
        return self.nombre

    def lista_patrones(self):
        return [p.strip().lower() for p in self.patrones.splitlines() if p.strip()]


class Incidencia(models.Model):
    """Una regla que se activó para una persona en un día (los minutos se acumulan en el mismo registro)."""
    ESTADOS = [('NUEVA', 'Nueva'), ('REVISADA', 'Revisada'), ('DESCARTADA', 'Descartada')]
    regla = models.ForeignKey(ReglaComportamiento, on_delete=models.CASCADE, related_name='incidencias')
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='incidencias_pc')
    dia = models.DateField()
    minutos = models.PositiveIntegerField(default=0)
    primera = models.DateTimeField()
    ultima = models.DateTimeField()
    ejemplo = models.CharField(max_length=255, blank=True, help_text="Aplicación o sitio y ventana que la activó.")
    avisada = models.BooleanField(default=False)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='NUEVA')
    revisada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    nota = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('regla', 'usuario', 'dia')
        ordering = ['-dia', '-ultima']
        indexes = [models.Index(fields=['usuario', 'dia'])]

    @property
    def cuenta(self):
        return self.minutos >= self.regla.minutos_minimos
