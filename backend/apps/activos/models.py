"""Activos y equipos: computadoras, cámaras, audio, iluminación, herramientas, vehículos y mobiliario."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Activo(models.Model):
    CATEGORIAS = [('COMPUTADORA', 'Computadora de escritorio'), ('LAPTOP', 'Laptop'), ('MONITOR', 'Monitor'), ('CELULAR', 'Celular o tableta'),
                  ('CAMARA', 'Cámara'), ('AUDIO', 'Audio y micrófonos'), ('ILUMINACION', 'Iluminación'), ('IMPRESION', 'Máquina de impresión'),
                  ('HERRAMIENTA', 'Herramienta'), ('VEHICULO', 'Vehículo'), ('RED', 'Red y servidores'), ('MOBILIARIO', 'Mobiliario'), ('OTRO', 'Otro')]
    ESTADOS = [('DISPONIBLE', 'Disponible'), ('ASIGNADO', 'Asignado'), ('MANTENIMIENTO', 'En mantenimiento'), ('DANADO', 'Dañado'), ('BAJA', 'De baja')]
    codigo = models.CharField(max_length=20, unique=True, editable=False)
    nombre = models.CharField(max_length=150)
    categoria = models.CharField(max_length=12, choices=CATEGORIAS, default='OTRO')
    marca = models.CharField(max_length=60, blank=True)
    modelo = models.CharField(max_length=80, blank=True)
    serie = models.CharField("Número de serie", max_length=80, blank=True)
    estado = models.CharField(max_length=14, choices=ESTADOS, default='DISPONIBLE')
    ubicacion = models.CharField(max_length=100, blank=True, help_text="Oficina, estudio, taller, segundo nivel…")
    asignado_a = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activos')
    proyecto = models.ForeignKey('operaciones.Proyecto', on_delete=models.SET_NULL, null=True, blank=True, related_name='activos')
    dispositivo = models.OneToOneField('monitoreo.Dispositivo', on_delete=models.SET_NULL, null=True, blank=True, related_name='activo_fijo',
                                       help_text="La computadora vinculada al monitoreo, si aplica.")
    fecha_compra = models.DateField(null=True, blank=True)
    costo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    proveedor = models.CharField(max_length=120, blank=True)
    garantia_hasta = models.DateField(null=True, blank=True)
    vida_util_meses = models.PositiveSmallIntegerField(default=36)
    valor_residual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mantenimiento_cada_meses = models.PositiveSmallIntegerField(null=True, blank=True)
    proximo_mantenimiento = models.DateField(null=True, blank=True)
    notas = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'Activo'

    def __str__(self):
        return f'{self.codigo} · {self.nombre}'

    def save(self, *args, **kwargs):
        if not self.codigo:
            ultimo = Activo.objects.order_by('-id').values_list('codigo', flat=True).first()
            n = int(ultimo.split('-')[1]) + 1 if ultimo and '-' in ultimo and ultimo.split('-')[1].isdigit() else 1
            self.codigo = f'ACT-{n:04d}'
            while Activo.objects.filter(codigo=self.codigo).exists():
                n += 1
                self.codigo = f'ACT-{n:04d}'
        super().save(*args, **kwargs)

    def valor_actual(self, hoy=None):
        """Depreciación en línea recta hasta el valor residual."""
        if self.costo is None or not self.fecha_compra:
            return self.costo
        hoy = hoy or timezone.localdate()
        meses = max(0, (hoy.year - self.fecha_compra.year) * 12 + hoy.month - self.fecha_compra.month)
        vida = max(1, self.vida_util_meses)
        costo, residual = Decimal(self.costo), Decimal(self.valor_residual or 0)
        return max(residual, costo - (costo - residual) * Decimal(min(meses, vida)) / vida).quantize(Decimal('0.01'))


class MovimientoActivo(models.Model):
    TIPOS = [('ALTA', 'Alta'), ('ASIGNACION', 'Asignación'), ('DEVOLUCION', 'Devolución'), ('TRASLADO', 'Traslado'),
             ('MANTENIMIENTO', 'Mantenimiento'), ('REPARACION', 'Reparación'), ('DANO', 'Daño reportado'), ('BAJA', 'Baja')]
    activo = models.ForeignKey(Activo, on_delete=models.CASCADE, related_name='movimientos')
    tipo = models.CharField(max_length=14, choices=TIPOS)
    fecha = models.DateField(default=date.today)
    persona = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    costo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    nota = models.CharField(max_length=255, blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
