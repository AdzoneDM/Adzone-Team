"""
Call Center: campañas con sus metas y los agentes que las atienden.

Los agentes son usuarios con el acceso «Agente Call Center». Entran a una pantalla propia
(su campaña, sus metas y sus KPIs del mes) y se evalúan en un ranking aparte del resto del equipo.
"""
from django.conf import settings
from django.db import models


class Campana(models.Model):
    TIPOS = [('ATENCION', 'Atención al cliente'), ('VENTAS', 'Ventas'), ('COBROS', 'Cobros'),
             ('SOPORTE', 'Soporte técnico'), ('ENCUESTAS', 'Encuestas'), ('CITAS', 'Agendamiento de citas')]
    CANALES = ['Llamadas entrantes', 'Llamadas salientes', 'WhatsApp', 'Chat web', 'Correo', 'Redes sociales']

    nombre = models.CharField(max_length=150)
    cliente = models.ForeignKey('operaciones.Cliente', on_delete=models.SET_NULL, null=True, blank=True, related_name='campanas')
    tipo = models.CharField(max_length=10, choices=TIPOS, default='ATENCION')
    canales = models.JSONField(default=list, blank=True)
    idioma = models.CharField(max_length=10, choices=[('ES', 'Español'), ('EN', 'Inglés'), ('BI', 'Bilingüe')], default='ES')
    horario = models.CharField("Horario de atención", max_length=150, blank=True, help_text="Ej.: lunes a viernes, 8:00 a 5:00")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    meta_contactos_dia = models.PositiveIntegerField("Contactos efectivos por agente al día", default=0)
    meta_conversion = models.DecimalField("Conversión o resolución (%)", max_digits=5, decimal_places=2, default=0)
    meta_calidad = models.DecimalField("Calidad mínima de monitoreo (%)", max_digits=5, decimal_places=2, default=85)
    guion = models.TextField("Guion y protocolos", blank=True)
    notas = models.TextField(blank=True)
    activa = models.BooleanField(default=True)
    agentes = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='campanas_call_center')
    orden = models.ForeignKey('operaciones.OrdenTrabajo', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='campanas', help_text="OT de la que sale la campaña, si la hay.")
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activa', 'nombre']
        verbose_name = 'Campaña'

    def __str__(self):
        return self.nombre
