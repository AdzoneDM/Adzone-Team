from django.db.models.signals import post_save
from django.contrib.auth.models import User # El modelo User de Django es el "sender"
from django.dispatch import receiver
from .models import PerfilUsuario # El modelo PerfilUsuario que queremos crear

@receiver(post_save, sender=User)
def crear_o_actualizar_perfil_usuario(sender, instance, created, **kwargs):
    """
    Signal para crear o actualizar el PerfilUsuario cuando un User se guarda.
    Se enfoca en la creación del perfil.
    """
    if created: # Solo actuar si el User acaba de ser creado
        PerfilUsuario.objects.get_or_create(user=instance)


    # Si quisieras que el perfil se actualice cada vez que el User se guarda (no solo al crear),
    # podrías añadir lógica aquí, pero get_or_create ya maneja la existencia.
    # Por ejemplo, si PerfilUsuario tuviera campos que dependieran de User y necesitaran sincronizarse:
    # instance.perfil.save() # Asumiendo que 'perfil' es el related_name