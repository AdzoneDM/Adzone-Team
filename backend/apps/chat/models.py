"""Chat: la sala global de la empresa, los chats privados de dos personas y los grupos por área."""
import os
import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.utils import timezone

LIMITE_TEXTO = 20000  # caracteres por mensaje (unas 3 000 palabras); la columna es longtext, no hay tope de la base de datos


class Conversacion(models.Model):
    GLOBAL, DIRECTA, GRUPO = 'GLOBAL', 'DIRECTA', 'GRUPO'
    TIPOS = [(GLOBAL, 'Sala de toda la empresa'), (DIRECTA, 'Chat privado'), (GRUPO, 'Grupo')]
    tipo = models.CharField(max_length=7, choices=TIPOS, default=DIRECTA)
    # Solo en los privados; siempre «a» es la persona con el id menor, así el par es único sin importar quién lo abrió.
    a = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    b = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    creado = models.DateTimeField(auto_now_add=True)
    # Solo en los grupos: su nombre, el área a la que pertenecen (opcional), quién los creó y quiénes participan
    nombre = models.CharField(max_length=80, blank=True)
    departamento = models.ForeignKey('core.Departamento', on_delete=models.SET_NULL, null=True, blank=True, related_name='grupos_chat')
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    miembros = models.ManyToManyField(User, blank=True, related_name='grupos_chat')
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
            models.CheckConstraint(condition=Q(tipo__in=['GLOBAL', 'GRUPO']) | Q(a__isnull=False, b__isnull=False, a__lt=models.F('b')), name='chat_par_ordenado'),
        ]

    def __str__(self):
        if self.tipo == self.GRUPO:
            return f'Grupo {self.nombre}'
        return 'Sala global' if self.tipo == self.GLOBAL else f'Privado {self.a_id}-{self.b_id}'

    def participa(self, usuario):
        if self.tipo == self.GRUPO:
            return self.miembros.filter(pk=usuario.id).exists()
        return self.tipo == self.GLOBAL or usuario.id in (self.a_id, self.b_id)

    def otro(self, usuario):
        return self.b if usuario.id == self.a_id else self.a


def _ruta_archivo(instancia, nombre):
    ext = os.path.splitext(nombre)[1].lower()[:10]
    return f'chat/{timezone.localdate():%Y/%m}/{uuid.uuid4().hex}{ext}'


class Mensaje(models.Model):
    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name='mensajes')
    autor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='mensajes_chat')
    texto = models.TextField(max_length=LIMITE_TEXTO, blank=True)
    # Un archivo adjunto (documento o imagen): el texto puede ir vacío si hay archivo
    archivo = models.FileField(upload_to=_ruta_archivo, null=True, blank=True)
    archivo_nombre = models.CharField(max_length=150, blank=True)
    archivo_es_imagen = models.BooleanField(default=False)
    archivo_tamano = models.PositiveIntegerField(default=0)
    archivo_purgado = models.BooleanField(default=False, help_text="El video o ZIP ya se borró (limpieza automática de archivos pesados del chat).")
    # A quién se mencionó con @usuario (solo participantes de la conversación): [{'id', 'username', 'nombre'}]
    menciones = models.JSONField(default=list, blank=True)
    # Solo ZIP: cuántos archivos trae y si el antivirus lo revisó (LIMPIO) o no (NO_REVISADO: ambiente de desarrollo)
    archivo_items = models.PositiveIntegerField(null=True, blank=True)
    archivo_escaneo = models.CharField(max_length=12, blank=True, default='')
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
