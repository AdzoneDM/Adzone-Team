"""
Finanzas operativas: cotización → orden → factura → cobro, gastos y rentabilidad.

No reemplaza la contabilidad formal ni emite comprobantes fiscales: el NCF de la factura
se anota desde el sistema contable para cruzar la información.
"""
import os
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.operaciones.models import Cliente, OrdenTrabajo, Proyecto, siguiente_numero

ITBIS = Decimal('18')
MONEDAS = [('DOP', 'RD$'), ('USD', 'US$')]
DOS = Decimal('0.01')


def redondear(x):
    return Decimal(x).quantize(DOS, rounding=ROUND_HALF_UP)


class Documento(models.Model):
    """Lo común de cotizaciones y facturas."""
    numero = models.CharField(max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='%(class)ss')
    proyecto = models.ForeignKey(Proyecto, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)ss')
    titulo = models.CharField(max_length=200, blank=True)
    fecha = models.DateField(default=timezone.localdate)
    moneda = models.CharField(max_length=3, choices=MONEDAS, default='DOP')
    notas = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    itbis = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    creada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    cashflow_id = models.CharField(max_length=60, blank=True, help_text="Id del documento en Cashflow.")
    cashflow_numero = models.CharField(max_length=40, blank=True)
    cashflow_estado = models.CharField(max_length=40, blank=True)
    cashflow_sincronizado = models.DateTimeField(null=True, blank=True)

    PREFIJO = ''

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = siguiente_numero(type(self), self.PREFIJO)
        super().save(*args, **kwargs)

    def recalcular(self):
        subtotal = itbis = Decimal('0')
        for linea in self.lineas.all():
            importe = redondear(linea.cantidad * linea.precio)
            subtotal += importe
            if linea.aplica_itbis:
                itbis += redondear(importe * ITBIS / 100)
        self.subtotal, self.itbis, self.total = redondear(subtotal), redondear(itbis), redondear(subtotal + itbis)
        self.save(update_fields=['subtotal', 'itbis', 'total'])

    class Meta:
        abstract = True
        ordering = ['-fecha', '-id']


class Linea(models.Model):
    descripcion = models.CharField(max_length=255)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    precio = models.DecimalField(max_digits=14, decimal_places=2)
    aplica_itbis = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    @property
    def importe(self):
        return redondear(self.cantidad * self.precio)

    class Meta:
        abstract = True
        ordering = ['orden', 'id']


class Cotizacion(Documento):
    ESTADOS = [('BORRADOR', 'Borrador'), ('ENVIADA', 'Enviada'), ('APROBADA', 'Aprobada'), ('RECHAZADA', 'Rechazada')]
    PREFIJO = 'COT'
    estado = models.CharField(max_length=10, choices=ESTADOS, default='BORRADOR')
    valida_hasta = models.DateField(null=True, blank=True)
    condiciones = models.TextField(blank=True, default="50% de anticipo para iniciar y 50% contra entrega.")

    class Meta(Documento.Meta):
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"


class LineaCotizacion(Linea):
    documento = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='lineas')


class Factura(Documento):
    ESTADOS = [('BORRADOR', 'Borrador'), ('EMITIDA', 'Emitida'), ('PAGADA', 'Pagada'), ('ANULADA', 'Anulada')]
    PREFIJO = 'FAC'
    estado = models.CharField(max_length=10, choices=ESTADOS, default='BORRADOR')
    vencimiento = models.DateField(null=True, blank=True)
    ncf = models.CharField("NCF / e-CF", max_length=20, blank=True, help_text="Se anota desde el sistema contable.")
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.SET_NULL, null=True, blank=True, related_name='facturas')
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='facturas')
    pagado = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    es_anticipo = models.BooleanField(default=False, help_text="Factura del anticipo que exige la compuerta G0.")

    @property
    def saldo(self):
        return redondear(self.total - self.pagado) if self.estado != 'ANULADA' else Decimal('0')

    @property
    def vencida(self):
        return self.estado == 'EMITIDA' and self.vencimiento and self.vencimiento < timezone.localdate() and self.saldo > 0

    def actualizar_pagos(self):
        # Se consulta la base (no el prefetch): el pago recién creado tiene que contar.
        self.pagado = redondear(Pago.objects.filter(factura=self).aggregate(t=models.Sum('monto'))['t'] or Decimal('0'))
        if self.estado in ('EMITIDA', 'PAGADA'):
            self.estado = 'PAGADA' if self.pagado >= self.total and self.total > 0 else 'EMITIDA'
        self.save(update_fields=['pagado', 'estado'])

    class Meta(Documento.Meta):
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"


class LineaFactura(Linea):
    documento = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='lineas')


class Pago(models.Model):
    METODOS = [('TRANSFERENCIA', 'Transferencia'), ('EFECTIVO', 'Efectivo'), ('CHEQUE', 'Cheque'),
               ('TARJETA', 'Tarjeta'), ('OTRO', 'Otro')]
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='pagos')
    fecha = models.DateField(default=timezone.localdate)
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    metodo = models.CharField(max_length=14, choices=METODOS, default='TRANSFERENCIA')
    referencia = models.CharField(max_length=100, blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    cashflow_id = models.CharField(max_length=60, blank=True, help_text="Recibo de ingreso en Cashflow (si vino de allá).")

    class Meta:
        ordering = ['-fecha', '-id']


def _ruta_comprobante(instancia, nombre):
    ext = os.path.splitext(nombre)[1].lower()[:10]
    return f"comprobantes/{timezone.localdate():%Y/%m}/{uuid.uuid4().hex}{ext}"


class Gasto(models.Model):
    CATEGORIAS = [('MATERIALES', 'Materiales e insumos'), ('PERSONAL', 'Personal / freelance'), ('PAUTA', 'Pauta publicitaria'),
                  ('TRANSPORTE', 'Transporte y viáticos'), ('EQUIPOS', 'Equipos'), ('SOFTWARE', 'Software y servicios'),
                  ('ALQUILER', 'Alquiler y servicios básicos'), ('IMPUESTOS', 'Impuestos'), ('OTRO', 'Otro')]
    fecha = models.DateField(default=timezone.localdate)
    concepto = models.CharField(max_length=200)
    categoria = models.CharField(max_length=12, choices=CATEGORIAS, default='MATERIALES')
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    moneda = models.CharField(max_length=3, choices=MONEDAS, default='DOP')
    proveedor = models.CharField(max_length=150, blank=True)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.SET_NULL, null=True, blank=True, related_name='gastos')
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.SET_NULL, null=True, blank=True, related_name='gastos')
    comprobante = models.FileField(upload_to=_ruta_comprobante, null=True, blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
