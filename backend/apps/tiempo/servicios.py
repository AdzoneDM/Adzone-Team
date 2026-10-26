from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import MAX_MINUTOS, RegistroTiempo


def activo(usuario):
    return RegistroTiempo.objects.filter(usuario=usuario, fin__isnull=True).select_related('tarea', 'orden', 'proyecto').first()


def detener(registro):
    ahora = timezone.now()
    minutos = int((ahora - registro.inicio).total_seconds() // 60)
    if minutos > MAX_MINUTOS:  # se quedó corriendo: se cierra en 12 h y se avisa en la descripción
        minutos = MAX_MINUTOS
        ahora = registro.inicio + timedelta(minutes=MAX_MINUTOS)
        registro.descripcion = (registro.descripcion + " · Cronómetro olvidado: se cerró en 12 h").strip(" ·")[:255]
    registro.fin = ahora
    registro.minutos = max(minutos, 0)
    registro.save()
    return registro


def iniciar(usuario, tarea=None, orden=None, proyecto=None, descripcion=''):
    """Un solo cronómetro por persona: empezar uno detiene el anterior."""
    previo = activo(usuario)
    if previo:
        detener(previo)
    registro = RegistroTiempo(usuario=usuario, tarea=tarea, orden=orden, proyecto=proyecto,
                              descripcion=descripcion[:255], inicio=timezone.now())
    registro.completar_desde_tarea()
    registro.save()
    return registro, previo


def rango_semana(fecha):
    lunes = fecha - timedelta(days=fecha.weekday())
    return lunes, lunes + timedelta(days=6)


def _dt(d, fin=False):
    return timezone.make_aware(datetime.combine(d, time.max if fin else time.min))


def minutos_por_usuario(desde, hasta, usuarios=None):
    qs = RegistroTiempo.objects.filter(inicio__range=(_dt(desde), _dt(hasta, True)))
    if usuarios is not None:
        qs = qs.filter(usuario__in=usuarios)
    totales = {}
    for r in qs:
        totales[r.usuario_id] = totales.get(r.usuario_id, 0) + r.minutos_hasta_ahora()
    return totales
