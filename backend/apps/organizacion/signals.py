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

GESTION = {'Supervisor', 'Gerente de Departamento', 'Administrador'}


def _dar_supervisor(usuario):
    """Si `usuario` tiene gente a cargo y ningún perfil de gestión, recibe «Supervisor».
    No se toca a quien la dirección ya le ajustó permisos a mano (tiene excepciones)."""
    from django.contrib.auth.models import Group
    from apps.core.models import ExcepcionPermiso
    if not usuario.is_active or usuario.groups.filter(name__in=GESTION).exists() or ExcepcionPermiso.objects.filter(usuario=usuario).exists():
        return
    grupo = Group.objects.filter(name='Supervisor').first()
    if grupo:
        usuario.groups.add(grupo)
        usuario.groups.remove(*usuario.groups.filter(name='Colaborador'))  # «Colaborador» es solo el perfil de quien no tiene otro
        usuario._permisos_acceso = None


@receiver(post_save, sender=PerfilUsuario)
def perfil_de_jefe_segun_organigrama(sender, instance, raw=False, **kwargs):
    """El organigrama dice sobre quién; el perfil dice qué. Quien queda con gente a cargo recibe el perfil Supervisor."""
    if raw or not instance.puesto_trabajo_id:
        return
    from apps.desempeno.permisos import subordinados
    puesto = instance.puesto_trabajo
    if subordinados(instance.user).exists():
        _dar_supervisor(instance.user)
    jefe = puesto.supervisor
    vistos = set()
    while jefe is not None and jefe.pk not in vistos:  # el primer puesto ocupado hacia arriba es quien lo gestiona
        vistos.add(jefe.pk)
        ocupantes = list(User.objects.filter(is_active=True, perfil__puesto_trabajo=jefe).exclude(pk=instance.user_id))
        if ocupantes:
            for u in ocupantes:
                _dar_supervisor(u)
            break
        jefe = jefe.supervisor
