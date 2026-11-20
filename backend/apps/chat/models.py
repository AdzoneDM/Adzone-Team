"""Chat: la sala global de la empresa y los chats privados de dos personas."""
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q

LIMITE_TEXTO = 2000


class Conversacion(models.Model):
    GLOBAL, DIRECTA = 'GLOBAL', 'DIRECTA'
    TIPOS = [(GLOBAL, 'Sala de toda la empresa'), (DIRECTA, 'Chat privado')]
    tipo = models.CharField(max_length=7, choices=TIPOS, default=DIRECTA)
    # Solo en los privados; siempre «a» es la persona con el id menor, así el par es único sin importar quién lo abrió.
    a = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    b = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    creado = models.DateTimeField(auto_now_add=True)
    # Resumen de lo último que se escribió (evita consultar los mensajes para armar la lista)
    ultimo_id = models.BigIntegerField(default=0)
    ultimo_texto = models.CharField(max_length=140, blank=True)
    ultimo_autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    ultima_actividad = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Conversación'
        verbose_name_plural = 'Conversaciones'
        constraints = [
            models.UniqueConstraint(fields=['a', 'b'], name='chat_par_unico'),
            models.CheckConstraint(condition=Q(tipo='GLOBAL') | Q(a__isnull=False, b__isnull=False, a__lt=models.F('b')), name='chat_par_ordenado'),
        ]

    def __str__(self):
        return 'Sala global' if self.tipo == self.GLOBAL else f'Privado {self.a_id}-{self.b_id}'

    def participa(self, usuario):
        return self.tipo == self.GLOBAL or usuario.id in (self.a_id, self.b_id)

    def otro(self, usuario):
        return self.b if usuario.id == self.a_id else self.a


class Mensaje(models.Model):
    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name='mensajes')
    autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='mensajes_chat')
    texto = models.TextField(max_length=LIMITE_TEXTO)
    creado = models.DateTimeField(auto_now_add=True, db_index=True)
    # Un mensaje borrado no se elimina de la base (queda constancia), pero deja de mostrar su texto.
    eliminado = models.BooleanField(default=False)
    eliminado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['conversacion', 'id'])]
        verbose_name = 'Mensaje del chat'
        verbose_name_plural = 'Mensajes del chat'

    def __str__(self):
        return f'{self.autor_id}: {self.texto[:40]}'


class Lectura(models.Model):
    """Hasta qué mensaje de cada conversación ha leído cada persona (contador de no leídos)."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lecturas_chat')
    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name='lecturas')
    ultimo_leido = models.BigIntegerField(default=0)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['usuario', 'conversacion'], name='chat_lectura_unica')]
