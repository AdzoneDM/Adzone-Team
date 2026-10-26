from django.contrib.auth.models import User
from django.db import models


class SincronizacionCashflow(models.Model):
    """Bitácora de cada llamada a Cashflow: qué se envió, qué respondió y si funcionó. Nunca guarda la API key."""
    operacion = models.CharField(max_length=40)
    objeto = models.CharField(max_length=60, blank=True)
    exito = models.BooleanField(default=True)
    modo = models.CharField(max_length=10, default='prueba')
    detalle = models.TextField(blank=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
