"""Chat global: una sola sala donde conversa toda la plataforma."""
from django.contrib.auth.models import User
from django.db import models

LIMITE_TEXTO = 2000


class Mensaje(models.Model):
    autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='mensajes_chat')
    texto = models.TextField(max_length=LIMITE_TEXTO)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)
    # Un mensaje borrado no se elimina de la base (queda constancia), pero deja de mostrar su texto.
    eliminado = models.BooleanField(default=False)
    eliminado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        ordering = ['id']
        verbose_name = 'Mensaje del chat'
        verbose_name_plural = 'Mensajes del chat'

    def __str__(self):
        return f'{self.autor_id}: {self.texto[:40]}'


class Lectura(models.Model):
    """Hasta qué mensaje ha leído cada persona (para el contador de no leídos)."""
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='lectura_chat')
    ultimo_leido = models.BigIntegerField(default=0)
    actualizado = models.DateTimeField(auto_now=True)
