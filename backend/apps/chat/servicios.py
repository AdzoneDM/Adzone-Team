from datetime import timedelta

from django.db.models import Max
from django.utils import timezone

from apps.desempeno.permisos import es_administrador

from .models import Lectura, Mensaje

MAX_POR_MINUTO = 20   # contra spam y ráfagas accidentales
PAGINA = 40
PAGINA_MAX = 100


def puede_borrar(usuario, mensaje):
    return not mensaje.eliminado and (mensaje.autor_id == usuario.id or es_administrador(usuario))


def excede_ritmo(usuario):
    desde = timezone.now() - timedelta(minutes=1)
    return Mensaje.objects.filter(autor=usuario, creado__gte=desde).count() >= MAX_POR_MINUTO


def no_leidos(usuario):
    """Mensajes de otras personas posteriores a lo último que esta persona leyó."""
    lectura = Lectura.objects.filter(usuario=usuario).first()
    if lectura is None:
        # Primera vez: lo anterior a hoy no cuenta como pendiente.
        base = Mensaje.objects.filter(creado__gte=timezone.now() - timedelta(days=1))
    else:
        base = Mensaje.objects.filter(id__gt=lectura.ultimo_leido)
    return base.filter(eliminado=False).exclude(autor=usuario).count()


def ultimo_id():
    return Mensaje.objects.aggregate(m=Max('id'))['m'] or 0


def marcar_leido(usuario, hasta):
    lectura, _ = Lectura.objects.get_or_create(usuario=usuario)
    if hasta > lectura.ultimo_leido:
        lectura.ultimo_leido = min(hasta, ultimo_id())
        lectura.save(update_fields=['ultimo_leido', 'actualizado'])
