"""Clientes, proyectos y órdenes de trabajo: lo que ADZONE produce y para quién."""
import os
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.core.models import Departamento
from .formularios import TIPO_CHOICES

PRIORIDADES = [('BAJA', 'Baja'), ('NORMAL', 'Normal'), ('ALTA', 'Alta'), ('URGENTE', 'Urgente')]


def siguiente_numero(modelo, prefijo, campo='numero'):
    """PRE-AAAA-0001, consecutivo por año."""
    anio = timezone.localdate().year
    base = f"{prefijo}-{anio}-"
    ultimo = (modelo.objects.filter(**{f"{campo}__startswith": base}).order_by(f"-{campo}")
              .values_list(campo, flat=True).first())
    n = int(ultimo.rsplit('-', 1)[1]) + 1 if ultimo else 1
    return f"{base}{n:04d}"


class Cliente(models.Model):
    TIPOS = [('EMPRESA', 'Empresa'), ('GOBIERNO', 'Gobierno'), ('ONG', 'ONG / institución'),
             ('PERSONA', 'Persona'), ('INTERNO', 'Interno (ADZONE)')]
    nombre = models.CharField(max_length=200, unique=True)
    tipo = models.CharField(max_length=10, choices=TIPOS, default='EMPRESA')
    rnc = models.CharField("RNC o cédula", max_length=20, blank=True)
    contacto = models.CharField("Persona de contacto", max_length=150, blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    correo = models.EmailField(blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    notas = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    @property
    def es_interno(self):
        return self.tipo == 'INTERNO'

    def __str__(self):
        return self.nombre

    class Meta:
        ordering = ['nombre']


class Proyecto(models.Model):
    ESTADOS = [('PLANIFICADO', 'Planificado'), ('EN_CURSO', 'En curso'), ('EN_PAUSA', 'En pausa'),
               ('TERMINADO', 'Terminado'), ('CANCELADO', 'Cancelado')]
    codigo = models.CharField(max_length=20, unique=True, editable=False)
    nombre = models.CharField(max_length=200)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='proyectos')
    departamento = models.ForeignKey(Departamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='proyectos')
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='proyectos_a_cargo')
    miembros = models.ManyToManyField(User, blank=True, related_name='proyectos')
    estado = models.CharField(max_length=12, choices=ESTADOS, default='PLANIFICADO')
    prioridad = models.CharField(max_length=8, choices=PRIORIDADES, default='NORMAL')
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField("Fecha de entrega", null=True, blank=True)
    presupuesto = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                      help_text="Monto vendido. Solo lo ven Finanzas y quien gestiona el proyecto.")
    descripcion = models.TextField(blank=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = siguiente_numero(Proyecto, 'PRY', 'codigo')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"

    class Meta:
        ordering = ['-fecha_creacion']


class OrdenTrabajo(models.Model):
    """
    Orden de trabajo (OT). Flujo:
    SOLICITADA → APROBADA → EN_PRODUCCION → CONTROL_CALIDAD → LISTA → ENTREGADA
    (EN_PAUSA y CANCELADA en cualquier punto antes de entregar).
    Al aprobarla se crea la tarea de producción con sus pasos; la orden avanza sola con esa tarea.
    """
    ESTADOS = [('SOLICITADA', 'Solicitada'), ('APROBADA', 'Aprobada'), ('EN_PRODUCCION', 'En producción'),
               ('CONTROL_CALIDAD', 'Control de calidad'), ('LISTA', 'Lista para entregar'), ('ENTREGADA', 'Entregada'),
               ('EN_PAUSA', 'En pausa'), ('CANCELADA', 'Cancelada')]
    ABIERTAS = ['SOLICITADA', 'APROBADA', 'EN_PRODUCCION', 'CONTROL_CALIDAD', 'LISTA', 'EN_PAUSA']
    TRANSICIONES = {
        'SOLICITADA': ['APROBADA', 'CANCELADA'],
        'APROBADA': ['EN_PRODUCCION', 'EN_PAUSA', 'CANCELADA'],
        'EN_PRODUCCION': ['CONTROL_CALIDAD', 'EN_PAUSA', 'CANCELADA'],
        'CONTROL_CALIDAD': ['EN_PRODUCCION', 'LISTA', 'EN_PAUSA', 'CANCELADA'],
        'LISTA': ['ENTREGADA', 'EN_PRODUCCION'],
        'EN_PAUSA': ['APROBADA', 'EN_PRODUCCION', 'CANCELADA'],
        'ENTREGADA': [],
        'CANCELADA': [],
    }

    numero = models.CharField(max_length=20, unique=True, editable=False)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='ordenes')
    proyecto = models.ForeignKey(Proyecto, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes')
    departamento = models.ForeignKey(Departamento, on_delete=models.PROTECT, related_name='ordenes')
    detalles = models.JSONField(default=dict, blank=True, help_text="Datos propios del tipo de orden (formularios.py).")
    prioridad = models.CharField(max_length=8, choices=PRIORIDADES, default='NORMAL')
    estado = models.CharField(max_length=16, choices=ESTADOS, default='SOLICITADA')
    solicitada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ordenes_solicitadas')
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_a_cargo')
    equipo = models.ManyToManyField(User, blank=True, related_name='ordenes_en_equipo')
    aprobada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    fecha_requerida = models.DateField("Fecha que pide el cliente", null=True, blank=True)
    fecha_compromiso = models.DateField("Fecha comprometida", null=True, blank=True)
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    fecha_lista = models.DateTimeField(null=True, blank=True)
    fecha_entrega = models.DateField(null=True, blank=True)
    recibido_por = models.CharField(max_length=150, blank=True)
    monto = models.DecimalField("Monto acordado", max_digits=12, decimal_places=2, null=True, blank=True)
    motivo_cancelacion = models.TextField(blank=True)
    estado_antes_pausa = models.CharField(max_length=16, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = siguiente_numero(OrdenTrabajo, 'OT')
        super().save(*args, **kwargs)

    @property
    def abierta(self):
        return self.estado in self.ABIERTAS

    @property
    def vencida(self):
        fecha = self.fecha_compromiso or self.fecha_requerida
        return bool(fecha and self.abierta and self.estado != 'LISTA' and fecha < timezone.localdate())

    @property
    def a_tiempo(self):
        fecha = self.fecha_compromiso or self.fecha_requerida
        if self.estado != 'ENTREGADA' or not fecha or not self.fecha_entrega:
            return None
        return self.fecha_entrega <= fecha

    def participantes_ids(self):
        ids = {self.responsable_id, *[u.pk for u in self.equipo.all()]}
        ids.discard(None)
        return ids

    def __str__(self):
        return f"{self.numero} · {self.titulo}"

    class Meta:
        verbose_name = "Orden de trabajo"
        verbose_name_plural = "Órdenes de trabajo"
        ordering = ['-fecha_creacion']
        indexes = [models.Index(fields=['estado', 'departamento'])]


class EventoOrden(models.Model):
    """Historial de la orden: quién la pidió, aprobó, movió, entregó…"""
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='eventos')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    texto = models.CharField(max_length=255)
    detalle = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']


def _ruta_archivo(instancia, nombre):
    ext = os.path.splitext(nombre)[1].lower()[:10]
    hoy = timezone.localdate()
    return f"ordenes/{hoy:%Y/%m}/{uuid.uuid4().hex}{ext}"


class ArchivoOrden(models.Model):
    """Artes, fotos, referencias o comprobantes de la orden. Se descargan por la API (no son públicos)."""
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='archivos')
    archivo = models.FileField(upload_to=_ruta_archivo)
    nombre_original = models.CharField(max_length=255)
    tipo = models.CharField(max_length=100, blank=True)
    tamano = models.PositiveIntegerField(default=0)
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']


class Comentario(models.Model):
    """Conversación en una orden o un proyecto. Las @menciones avisan a la persona."""
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, null=True, blank=True, related_name='comentarios')
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, null=True, blank=True, related_name='comentarios')
    autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    texto = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'id']
