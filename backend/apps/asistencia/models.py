"""
Control de horario: horarios (turnos), marcajes de entrada, pausas y salida, permisos/vacaciones y feriados.

La jornada de cada día (llegó a tiempo, tarde, ausente, horas trabajadas, extra) no se guarda: se calcula de los
marcajes con `servicios.jornada()`, así un marcaje corregido arregla el día sin tocar nada más.
"""
from django.contrib.auth.models import User
from django.db import models

DIAS = [(0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo')]


class Horario(models.Model):
    """Un turno: qué días, a qué hora entra y sale, almuerzo y tolerancia. Cada día puede tener su propia hora."""
    nombre = models.CharField(max_length=80, unique=True)
    # {"0": ["08:00", "17:00"], ..., "5": ["08:00", "12:00"]}: día de la semana (0 = lunes) → entrada y salida.
    dias = models.JSONField(default=dict, help_text='Día (0 = lunes) → ["entrada", "salida"], p. ej. {"0": ["08:00", "17:00"]}.')
    almuerzo_minutos = models.PositiveSmallIntegerField(default=60, help_text="Pausa de almuerzo que no cuenta como trabajada.")
    tolerancia_minutos = models.PositiveSmallIntegerField(default=10, help_text="Minutos de gracia antes de contar tardanza.")
    por_defecto = models.BooleanField(default=False, help_text="Se usa para quien no tiene horario asignado.")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Horario'

    def __str__(self):
        return self.nombre

    def turno(self, dia_semana):
        """(entrada, salida) como texto «HH:MM», o None si ese día no trabaja."""
        valor = (self.dias or {}).get(str(dia_semana))
        return tuple(valor) if valor and len(valor) == 2 else None

    def minutos_programados(self, dia_semana):
        t = self.turno(dia_semana)
        if not t:
            return 0
        (h1, m1), (h2, m2) = (map(int, t[0].split(':')), map(int, t[1].split(':')))
        total = (h2 * 60 + m2) - (h1 * 60 + m1)
        return max(0, total - (self.almuerzo_minutos if total > 6 * 60 else 0))


class SitioMarcaje(models.Model):
    """Un lugar donde se marca: la oficina (con su pantalla de QR) o una sucursal. La ubicación sirve como alternativa al QR."""
    nombre = models.CharField(max_length=80)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    radio_m = models.PositiveIntegerField(default=150, help_text="A cuántos metros del punto cuenta como «en el lugar».")
    redes = models.CharField(max_length=255, blank=True, help_text="IP pública del internet de la oficina (o varias, separadas por coma). "
                             "Si se pone, el QR y la ubicación solo valen conectados a esa red.")
    clave_pantalla = models.CharField(max_length=40, unique=True, help_text="Enlace secreto de la pantalla que muestra el QR.")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Lugar de marcaje'

    def __str__(self):
        return self.nombre


class AsignacionHorario(models.Model):
    LUGARES = [('LIBRE', 'Donde sea'), ('OFICINA', 'En la oficina (QR o ubicación)'), ('CALLE', 'Donde sea, con ubicación')]
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='asignacion_horario')
    horario = models.ForeignKey(Horario, on_delete=models.PROTECT, related_name='asignaciones')
    marca_obligatoria = models.BooleanField(default=True, help_text="Si no marca entrada un día laborable, sale como ausente.")
    donde_marca = models.CharField(max_length=8, choices=LUGARES, default='LIBRE',
                                   help_text="Oficina: con el QR de la pantalla o estando en el lugar. Calle (instalaciones, eventos): donde sea, guardando la ubicación.")

    class Meta:
        verbose_name = 'Horario de una persona'


class Marcaje(models.Model):
    ENTRADA, PAUSA, REGRESO, SALIDA = 'ENTRADA', 'PAUSA', 'REGRESO', 'SALIDA'
    TIPOS = [(ENTRADA, 'Entrada'), (PAUSA, 'Inicio de pausa'), (REGRESO, 'Fin de pausa'), (SALIDA, 'Salida')]
    ORIGENES = [('WEB', 'Plataforma'), ('MOVIL', 'Celular'), ('QR', 'QR de la oficina'), ('AGENTE', 'Agente de escritorio'), ('MANUAL', 'Corrección manual')]
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='marcajes')
    tipo = models.CharField(max_length=10, choices=TIPOS)
    momento = models.DateTimeField(db_index=True)
    origen = models.CharField(max_length=10, choices=ORIGENES, default='WEB')
    motivo_pausa = models.CharField(max_length=60, blank=True, help_text="Almuerzo, diligencia, reunión fuera…")
    ip = models.GenericIPAddressField(null=True, blank=True)
    nota = models.CharField(max_length=255, blank=True)
    corregido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
                                      help_text="Quién lo agregó o corrigió a mano (vacío = la propia persona).")
    sitio = models.ForeignKey('SitioMarcaje', on_delete=models.SET_NULL, null=True, blank=True, related_name='marcajes')
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    precision_m = models.PositiveIntegerField(null=True, blank=True, help_text="Precisión de la ubicación que dio el celular.")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['momento']
        indexes = [models.Index(fields=['usuario', 'momento'])]
        verbose_name = 'Marcaje'

    def __str__(self):
        return f'{self.usuario} · {self.get_tipo_display()} · {self.momento:%d/%m %H:%M}'


class Ausencia(models.Model):
    TIPOS = [('VACACIONES', 'Vacaciones'), ('LICENCIA', 'Licencia médica'), ('PERMISO', 'Permiso'),
             ('TRABAJO_FUERA', 'Trabajo fuera de la oficina'), ('OTRO', 'Otro')]
    ESTADOS = [('PENDIENTE', 'Pendiente'), ('APROBADA', 'Aprobada'), ('RECHAZADA', 'Rechazada')]
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ausencias')
    tipo = models.CharField(max_length=15, choices=TIPOS)
    desde = models.DateField()
    hasta = models.DateField()
    motivo = models.TextField(blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='PENDIENTE')
    revisada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    comentario_revision = models.CharField(max_length=255, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-desde']
        verbose_name = 'Permiso o vacaciones'

    def cubre(self, dia):
        return self.estado == 'APROBADA' and self.desde <= dia <= self.hasta


class Feriado(models.Model):
    fecha = models.DateField(unique=True)
    nombre = models.CharField(max_length=120)

    class Meta:
        ordering = ['fecha']
