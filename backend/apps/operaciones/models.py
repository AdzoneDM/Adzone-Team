"""Clientes, proyectos y órdenes de trabajo: lo que ADZONE produce y para quién."""
import os
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.core.models import Departamento
from .formatos import AREA_CHOICES, AREAS

PRIORIDADES = [('BAJA', 'Baja'), ('NORMAL', 'Normal'), ('ALTA', 'Alta'), ('URGENTE', 'Urgente')]  # proyectos


def siguiente_numero(modelo, prefijo, campo='numero', corto=False):
    """PRE-AAAA-0001 (o PRE-AA-0001 con corto=True, como OT-26-0001), consecutivo por año."""
    anio = timezone.localdate().year
    base = f"{prefijo}-{anio % 100:02d}-" if corto else f"{prefijo}-{anio}-"
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
    cashflow_id = models.CharField(max_length=60, blank=True, help_text="Id del cliente en Cashflow.")
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
    OT Maestra (formato F-01). Comercial la pide, Coordinación la recibe en la compuerta G0 y,
    si todo está completo, la libera con su número OT-AA-0000 y emite las Órdenes de Área.

    Estados: SOLICITADA → (DEVUELTA) → LIBERADA (E1) → EN_PRODUCCION (áreas en E2–E5) → LISTA (todas en E5)
             → ENTREGADA (E6, acta F-12 firmada) → CERRADA (E7, G6 de Administración).  También EN_PAUSA y CANCELADA.
    """
    ESTADOS = [('SOLICITADA', 'Solicitud en G0'), ('DEVUELTA', 'Devuelta a Comercial'), ('LIBERADA', 'E1 · Liberada'),
               ('EN_PRODUCCION', 'En producción'), ('LISTA', 'Lista para entregar'), ('ENTREGADA', 'E6 · Entregada'),
               ('CERRADA', 'E7 · Cerrada'), ('EN_PAUSA', 'En pausa'), ('CANCELADA', 'Cancelada')]
    ABIERTAS = ['SOLICITADA', 'DEVUELTA', 'LIBERADA', 'EN_PRODUCCION', 'LISTA', 'EN_PAUSA']
    PRODUCCION = ['LIBERADA', 'EN_PRODUCCION', 'LISTA']
    PRIORIDADES = [('N', 'Normal'), ('U', 'Urgente'), ('E', 'Emergencia')]
    TIPOS_CLIENTE = [('NUEVO', 'Nuevo'), ('RECURRENTE', 'Recurrente'), ('IGUALA', 'Iguala')]

    numero = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False,
                              help_text="Lo asigna Coordinación al liberar (G0). Antes de eso es una solicitud.")
    solicitud = models.CharField(max_length=20, unique=True, editable=False)
    tipo = models.CharField(max_length=20, blank=True, help_text="Área principal (versiones anteriores).")
    titulo = models.CharField("Nombre del proyecto / trabajo", max_length=200)
    descripcion = models.TextField("Alcance: descripción, cantidades, piezas y resultado esperado", blank=True)
    exclusiones = models.TextField("Lo que no incluye este trabajo", blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='ordenes')
    proyecto = models.ForeignKey(Proyecto, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes')
    departamento = models.ForeignKey(Departamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes')
    detalles = models.JSONField(default=dict, blank=True)
    # Datos del cliente tal como se pidieron (sección 1 del F-01)
    contacto = models.CharField("Persona de contacto", max_length=150, blank=True)
    telefono = models.CharField("Teléfono / WhatsApp", max_length=40, blank=True)
    correo = models.EmailField(blank=True)
    direccion_entrega = models.CharField("Dirección de entrega / instalación", max_length=255, blank=True)
    tipo_cliente = models.CharField(max_length=10, choices=TIPOS_CLIENTE, default='RECURRENTE')
    asesor_comercial = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_vendidas')
    prioridad = models.CharField(max_length=8, choices=PRIORIDADES, default='N')
    estado = models.CharField(max_length=16, choices=ESTADOS, default='SOLICITADA')
    solicitada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ordenes_solicitadas')
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_a_cargo',
                                    help_text="Coordinador a cargo de la OT.")
    equipo = models.ManyToManyField(User, blank=True, related_name='ordenes_en_equipo')
    aprobada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
                                     help_text="Quien liberó la OT en G0 (Coordinación).")
    # Cotización y dinero
    cotizacion = models.ForeignKey('finanzas.Cotizacion', on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes')
    numero_cotizacion = models.CharField(max_length=40, blank=True)
    monto = models.DecimalField("Monto total RD$", max_digits=12, decimal_places=2, null=True, blank=True)
    anticipo_requerido = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    anticipo_confirmado = models.BooleanField(default=False)
    anticipo_fuente = models.CharField(max_length=10, blank=True, help_text="MANUAL o CASHFLOW")
    anticipo_confirmado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    anticipo_fecha = models.DateTimeField(null=True, blank=True)
    # Fechas y cálculo de la fecha comprometida (sección 4 del F-01)
    fecha_requerida = models.DateField("Fecha que pide el cliente", null=True, blank=True)
    fecha_compromiso = models.DateField("Fecha comprometida", null=True, blank=True)
    tiempo_estandar_dias = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    cola_dias = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    aprobacion_dias = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    colchon_pct = models.PositiveSmallIntegerField(null=True, blank=True)
    rondas_incluidas = models.PositiveSmallIntegerField(default=2)
    plan_areas = models.JSONField(default=list, blank=True,
                                  help_text="Sección 3 del F-01: [{area, secuencia, que_produce, fecha_entrega_interna, tiempo_estandar_dias}]")
    # G0 · compuerta de apertura
    g0 = models.JSONField(default=dict, blank=True)
    g0_entregada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    g0_entregada_fecha = models.DateTimeField(null=True, blank=True)
    g0_rechazo = models.TextField(blank=True)
    excepcion_g0_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
                                         help_text="Gerencia General autoriza liberar sin anticipo.")
    excepcion_g0_motivo = models.TextField(blank=True)
    excepcion_g0_regularizar = models.DateTimeField(null=True, blank=True)
    fecha_aprobacion = models.DateTimeField("Liberada", null=True, blank=True)
    fecha_lista = models.DateTimeField(null=True, blank=True)
    fecha_entrega = models.DateField("Fecha de entrega real", null=True, blank=True)
    recibido_por = models.CharField(max_length=150, blank=True)
    # G6 · cierre
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    cerrada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    costo_real = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    motivo_cancelacion = models.TextField(blank=True)
    estado_antes_pausa = models.CharField(max_length=16, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.solicitud:
            self.solicitud = siguiente_numero(OrdenTrabajo, 'S', 'solicitud', corto=True)
        super().save(*args, **kwargs)

    def asignar_numero(self):
        self.numero = siguiente_numero(OrdenTrabajo, 'OT', 'numero', corto=True)

    @property
    def codigo(self):
        return self.numero or self.solicitud

    @property
    def abierta(self):
        return self.estado in self.ABIERTAS

    @property
    def vencida(self):
        return bool(self.fecha_compromiso and self.estado in self.PRODUCCION + ['EN_PAUSA'] and self.estado != 'LISTA'
                    and self.fecha_compromiso < timezone.localdate())

    @property
    def a_tiempo(self):
        if self.estado not in ('ENTREGADA', 'CERRADA') or not self.fecha_compromiso or not self.fecha_entrega:
            return None
        return self.fecha_entrega <= self.fecha_compromiso

    def participantes_ids(self):
        ids = {self.responsable_id, *[u.pk for u in self.equipo.all()]}
        for oa in self.areas.all():
            ids.add(oa.responsable_id)
        ids.discard(None)
        return ids

    def __str__(self):
        return f"{self.codigo} · {self.titulo}"

    class Meta:
        verbose_name = "OT Maestra"
        verbose_name_plural = "OT Maestras"
        ordering = ['-fecha_creacion']
        indexes = [models.Index(fields=['estado'])]


class AreaConfig(models.Model):
    """Qué departamento hace cada área y quiénes la supervisan (reciben G1 y firman G3)."""
    codigo = models.CharField(max_length=4, unique=True, choices=AREA_CHOICES)
    departamento = models.ForeignKey(Departamento, on_delete=models.SET_NULL, null=True, blank=True)
    supervisores = models.ManyToManyField(User, blank=True, related_name='areas_supervisadas')
    activa = models.BooleanField(default=True)

    @classmethod
    def de(cls, codigo):
        conf = cls.objects.filter(codigo=codigo).select_related('departamento').first()
        if conf is None:
            conf = cls.objects.create(codigo=codigo, departamento=Departamento.objects.filter(nombre=AREAS[codigo]['departamento']).first())
        return conf

    def __str__(self):
        return self.get_codigo_display()

    class Meta:
        verbose_name = "Área de producción"
        verbose_name_plural = "Áreas de producción"


class OrdenArea(models.Model):
    """
    Orden de Área (F-02 a F-10). Estados E1–E5:
    EMITIDA (E1, espera G1) → RECIBIDA (E2) → EN_EJECUCION (E3) ⇄ EN_APROBACION (E4, G4) → TERMINADA (E5, G3 + G2/G5 con doble firma).
    RECHAZADA = el área la devolvió en G1 por falta de algo.
    """
    ESTADOS = [('EMITIDA', 'E1 · Emitida (espera G1)'), ('RECHAZADA', 'Rechazada en G1'), ('RECIBIDA', 'E2 · Recibida'),
               ('EN_EJECUCION', 'E3 · En ejecución'), ('EN_APROBACION', 'E4 · En aprobación del cliente'),
               ('TERMINADA', 'E5 · Terminada y traspasada'), ('CANCELADA', 'Cancelada')]
    ABIERTAS = ['EMITIDA', 'RECHAZADA', 'RECIBIDA', 'EN_EJECUCION', 'EN_APROBACION']

    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='areas')
    area = models.CharField(max_length=4, choices=AREA_CHOICES)
    numero = models.CharField(max_length=30, unique=True, editable=False)
    secuencia = models.PositiveSmallIntegerField(default=1, help_text="Las de la misma secuencia van en paralelo.")
    que_produce = models.CharField(max_length=255)
    fecha_entrega_interna = models.DateField(null=True, blank=True)
    tiempo_estandar_dias = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_area',
                                    help_text="Ejecutor principal.")
    estado = models.CharField(max_length=14, choices=ESTADOS, default='EMITIDA')
    especificacion = models.JSONField(default=dict, blank=True)
    # G1
    g1 = models.JSONField(default=dict, blank=True)
    g1_entrega_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    g1_recibe_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    g1_fecha = models.DateTimeField(null=True, blank=True)
    g1_rechazo = models.TextField(blank=True)
    # G4
    g4_aprobado = models.BooleanField(default=False)
    g4_canales = models.JSONField(default=list, blank=True)
    g4_ronda = models.PositiveSmallIntegerField(default=0)
    g4_fecha = models.DateTimeField(null=True, blank=True)
    g4_aprobado_por = models.CharField(max_length=150, blank=True)
    g4_version = models.CharField(max_length=60, blank=True)
    g4_con_cambios = models.BooleanField(default=False)
    # G3
    g3 = models.JSONField(default=dict, blank=True)
    g3_resultado = models.CharField(max_length=10, blank=True)
    g3_observaciones = models.TextField(blank=True)
    g3_supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    g3_fecha = models.DateTimeField(null=True, blank=True)
    # G2/G5
    g2 = models.JSONField(default=dict, blank=True)
    # Costos y retrabajo
    servicios_externos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    otros_materiales = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           help_text="Material que no salió por vale (compras directas).")
    pase_retrabajo = models.PositiveSmallIntegerField(default=0)
    fecha_terminada = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.numero:
            base = f"{self.orden.numero or self.orden.solicitud}-{self.area}"
            n = OrdenArea.objects.filter(numero__startswith=base).count()
            self.numero = base if n == 0 else f"{base}-{n + 1}"
        super().save(*args, **kwargs)

    @property
    def formato(self):
        return AREAS[self.area]

    @property
    def requiere_g4(self):
        return AREAS[self.area].get('requiere_g4', False)

    @property
    def vencida(self):
        return bool(self.fecha_entrega_interna and self.estado in self.ABIERTAS and self.fecha_entrega_interna < timezone.localdate())

    def __str__(self):
        return f"{self.numero} · {self.get_area_display()}"

    class Meta:
        verbose_name = "Orden de Área"
        verbose_name_plural = "Órdenes de Área"
        ordering = ['secuencia', 'id']


class Traspaso(models.Model):
    """Vale de traspaso entre áreas (F-13): sin doble firma el trabajo no avanza."""
    COMPUERTAS = [('G0', 'G0 · Apertura'), ('G1', 'G1 · Entrada al área'), ('G2', 'G2 · Salida a otra área'),
                  ('G4', 'G4 · Aprobación del cliente'), ('G5', 'G5 · Salida al cliente'), ('G6', 'G6 · Cierre')]
    RESULTADOS = [('PENDIENTE', 'Pendiente de recibir'), ('ACEPTADO', 'Aceptado'), ('RECHAZADO', 'Rechazado')]
    numero = models.CharField(max_length=20, unique=True, editable=False)
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='traspasos')
    oa = models.ForeignKey(OrdenArea, on_delete=models.CASCADE, null=True, blank=True, related_name='traspasos')
    destino_oa = models.ForeignKey(OrdenArea, on_delete=models.SET_NULL, null=True, blank=True, related_name='traspasos_recibidos')
    compuerta = models.CharField(max_length=2, choices=COMPUERTAS)
    que_entrega = models.TextField()
    entrega_area = models.CharField(max_length=60)
    entrega_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    entrega_fecha = models.DateTimeField(auto_now_add=True)
    recibe_area = models.CharField(max_length=60)
    recibe_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    recibe_fecha = models.DateTimeField(null=True, blank=True)
    verificacion = models.JSONField(default=dict, blank=True)
    resultado = models.CharField(max_length=10, choices=RESULTADOS, default='PENDIENTE')
    causa_rechazo = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = siguiente_numero(Traspaso, 'VT', corto=True)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-entrega_fecha', '-id']


class Firma(models.Model):
    """Firma digital: quién, con qué rol y cuándo. El cliente puede firmar en pantalla (imagen)."""
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, null=True, blank=True, related_name='firmas')
    oa = models.ForeignKey(OrdenArea, on_delete=models.CASCADE, null=True, blank=True, related_name='firmas')
    contexto = models.CharField(max_length=20, help_text="CIERRE_OT, CIERRE_OA, ACTA, CAMBIO…")
    rol = models.CharField(max_length=60)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    nombre = models.CharField(max_length=150, blank=True)
    documento = models.CharField("Cédula", max_length=20, blank=True)
    imagen = models.TextField(blank=True, help_text="Firma dibujada (data URL PNG).")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha']


class Incidencia(models.Model):
    """Observaciones, incidencias y tiempos muertos: la materia prima de la reunión semanal."""
    oa = models.ForeignKey(OrdenArea, on_delete=models.CASCADE, related_name='incidencias')
    reporta = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha = models.DateTimeField(default=timezone.now)
    descripcion = models.CharField("Incidencia", max_length=255)
    minutos_perdidos = models.PositiveIntegerField(default=0)
    resolucion = models.CharField("Cómo se resolvió", max_length=255, blank=True)

    class Meta:
        ordering = ['-fecha']


class SolicitudCambio(models.Model):
    """Solicitud de Cambio y Registro de Retrabajo (F-14)."""
    TIPOS = [('CAMBIO', 'Cambio de alcance (lo paga el cliente)'), ('RETRABAJO', 'Retrabajo (lo asume AdZone)')]
    ESTADOS = [('SOLICITADA', 'Solicitada'), ('AUTORIZADA', 'Autorizada'), ('RECHAZADA', 'Rechazada')]
    numero = models.CharField(max_length=20, unique=True, editable=False)
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='cambios')
    oa = models.ForeignKey(OrdenArea, on_delete=models.SET_NULL, null=True, blank=True, related_name='cambios')
    tipo = models.CharField(max_length=10, choices=TIPOS)
    clasificacion = models.JSONField(default=list, blank=True)
    descripcion = models.TextField()
    aprobado_original = models.TextField("¿Qué se aprobó originalmente?", blank=True)
    impacto = models.JSONField(default=dict, blank=True, help_text="horas, material, costo, fecha: {antes, despues}")
    area_responsable = models.CharField(max_length=4, choices=AREA_CHOICES, blank=True)
    costo_retrabajo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_cliente = models.DecimalField("Monto adicional al cliente", max_digits=12, decimal_places=2, default=0)
    areas_notificadas = models.JSONField(default=list, blank=True)
    accion_preventiva = models.TextField(blank=True)
    responsable_accion = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    fecha_verificacion = models.DateField(null=True, blank=True)
    autorizaciones = models.JSONField(default=dict, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='SOLICITADA')
    solicitado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = siguiente_numero(SolicitudCambio, 'SC', corto=True)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-fecha']


class Acta(models.Model):
    """Acta de Entrega / Instalación (F-12). Sin acta firmada no se cierra la OT ni se factura."""
    MODALIDADES = [('ENTREGA', 'Entrega'), ('INSTALACION', 'Instalación'), ('RETIRO', 'Retiro en taller')]
    CONFORMIDAD = [('CONFORME', 'Recibido conforme'), ('OBSERVACIONES', 'Recibido con observaciones'),
                   ('PENDIENTE', 'Pendiente por causa del cliente')]
    numero = models.CharField(max_length=20, unique=True, editable=False)
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='actas')
    modalidad = models.CharField(max_length=12, choices=MODALIDADES, default='ENTREGA')
    fecha = models.DateField(default=timezone.localdate)
    hora_llegada = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    contacto_sitio = models.CharField(max_length=150, blank=True)
    # G5 · liberación de salida
    g5 = models.JSONField(default=dict, blank=True)
    liberada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
                                     help_text="Administración libera la salida.")
    liberada_fecha = models.DateTimeField(null=True, blank=True)
    saldo_al_liberar = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    entrega_taller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    recibe_cuadrilla = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    items = models.JSONField(default=list, blank=True, help_text="[{descripcion, cantidad, observacion}]")
    verificacion = models.JSONField(default=dict, blank=True)
    hallazgos = models.TextField(blank=True)
    material_devuelto = models.TextField(blank=True)
    conformidad = models.CharField(max_length=14, choices=CONFORMIDAD, blank=True)
    observaciones_cliente = models.TextField(blank=True)
    garantia = models.CharField(max_length=150, blank=True)
    instrucciones_mantenimiento = models.BooleanField(default=False)
    proxima_revision = models.DateField(null=True, blank=True)
    supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    firmada = models.BooleanField(default=False)
    recibida_administracion = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = siguiente_numero(Acta, 'AE', corto=True)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-fecha_creacion']


class TiempoEstandar(models.Model):
    """Tabla de tiempos estándar por área y tipo de trabajo (la «Tabla 8.2» del manual)."""
    area = models.CharField(max_length=4, choices=AREA_CHOICES)
    trabajo = models.CharField(max_length=120)
    dias = models.DecimalField(max_digits=5, decimal_places=1)

    class Meta:
        ordering = ['area', 'trabajo']
        unique_together = [('area', 'trabajo')]


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
    CATEGORIAS = [('ARTE', 'Arte / archivo de trabajo'), ('APROBACION', 'Aprobación del cliente'), ('FOTO', 'Fotografía'),
                  ('COMPROBANTE', 'Comprobante'), ('OTRO', 'Otro')]
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name='archivos')
    oa = models.ForeignKey('OrdenArea', on_delete=models.SET_NULL, null=True, blank=True, related_name='archivos')
    categoria = models.CharField(max_length=12, choices=CATEGORIAS, default='OTRO')
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
