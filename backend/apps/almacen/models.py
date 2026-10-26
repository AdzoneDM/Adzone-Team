"""Almacén: materiales, existencias y el Vale de Salida de Materiales (F-11). Sin vale no sale material."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models

from apps.operaciones.models import OrdenArea, OrdenTrabajo, siguiente_numero


class Material(models.Model):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=150)
    unidad = models.CharField(max_length=20, default='unidad', help_text="pie², m², rollo, hoja, galón, unidad…")
    existencia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    punto_reposicion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    proveedor = models.CharField(max_length=150, blank=True)
    activo = models.BooleanField(default=True)

    @property
    def bajo_minimo(self):
        return self.existencia <= self.punto_reposicion

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = "Materiales"


class MovimientoInventario(models.Model):
    """Entradas (compras), salidas (vales), devoluciones y ajustes. La existencia siempre tiene historia."""
    TIPOS = [('ENTRADA', 'Entrada'), ('SALIDA', 'Salida por vale'), ('DEVOLUCION', 'Devolución'), ('AJUSTE', 'Ajuste')]
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=10, choices=TIPOS)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, help_text="Positiva entra, negativa sale.")
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vale = models.ForeignKey('ValeMaterial', on_delete=models.SET_NULL, null=True, blank=True, related_name='movimientos')
    nota = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']


class ValeMaterial(models.Model):
    """
    F-11. SOLICITADO (supervisor del área) → AUTORIZADO (Coordinación) → DESPACHADO (Almacén descuenta en el momento)
    → CERRADO (devolución de sobrantes y desperdicio registrados).
    """
    ESTADOS = [('SOLICITADO', 'Solicitado'), ('AUTORIZADO', 'Autorizado'), ('DESPACHADO', 'Despachado'), ('CERRADO', 'Cerrado'),
               ('RECHAZADO', 'Rechazado')]
    numero = models.CharField(max_length=20, unique=True, editable=False)
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.PROTECT, related_name='vales')
    oa = models.ForeignKey(OrdenArea, on_delete=models.SET_NULL, null=True, blank=True, related_name='vales')
    estado = models.CharField(max_length=10, choices=ESTADOS, default='SOLICITADO')
    solicitado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    autorizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    despachado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    recibido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_autorizado = models.DateTimeField(null=True, blank=True)
    fecha_despacho = models.DateTimeField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    notas = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = siguiente_numero(ValeMaterial, 'VS', corto=True)
        super().save(*args, **kwargs)

    @property
    def costo_total(self):
        return sum(((l.cantidad_despachada - l.cantidad_devuelta) * l.costo_unitario for l in self.lineas.all()), Decimal('0'))

    class Meta:
        ordering = ['-fecha']
        verbose_name = "Vale de salida de materiales"
        verbose_name_plural = "Vales de salida de materiales"


class LineaVale(models.Model):
    vale = models.ForeignKey(ValeMaterial, on_delete=models.CASCADE, related_name='lineas')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='+')
    cantidad_solicitada = models.DecimalField(max_digits=12, decimal_places=2)
    cantidad_despachada = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lote = models.CharField("Lote / proveedor", max_length=60, blank=True)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cantidad_devuelta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    desperdicio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    causa_desperdicio = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['id']
