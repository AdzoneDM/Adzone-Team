"""Recordatorios personales: avisar a la hora elegida (lo corre el cron cada minuto) y calcular la próxima vez de los que se repiten."""
import calendar
from datetime import timedelta

from django.utils import timezone

from .models import Notificacion, Recordatorio

TOLERANCIA_ATRASO = timedelta(minutes=5)   # si el aviso sale con más atraso que esto (servidor caído), se aclara a qué hora era
DIAS_CONSERVAR_HECHOS = 90


def hora12(dt):
    dt = timezone.localtime(dt)
    return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'a. m.' if dt.hour < 12 else 'p. m.'}"


def _mas_un_mes(dt):
    """La misma fecha del mes siguiente (si ese mes no tiene ese día, el último)."""
    dt = timezone.localtime(dt)
    mes0 = dt.month  # 1..12
    anio, mes = dt.year + mes0 // 12, mes0 % 12 + 1
    dia = min(dt.day, calendar.monthrange(anio, mes)[1])
    return dt.replace(year=anio, month=mes, day=dia)


def siguiente(r, ahora):
    """La próxima vez que debe avisar un recordatorio que se repite: la primera fecha posterior a «ahora» que respete su ritmo (si el servidor estuvo
    apagado, se salta lo que ya pasó: se avisa una sola vez, no una por cada día perdido)."""
    base = timezone.localtime(r.recordar_en)
    for _ in range(2000):
        base = base + timedelta(days=1) if r.repetir == 'DIARIO' else base + timedelta(days=7) if r.repetir == 'SEMANAL' else _mas_un_mes(base)
        if base > ahora:
            return base
    return ahora + timedelta(days=1)


def avisar_recordatorios(ahora=None):
    """Crea el aviso de cada recordatorio que ya llegó a su hora. Devuelve cuántos avisó.
    Seguro si el cron corre dos veces a la vez: cada recordatorio se «reclama» con una actualización condicional, y solo quien la gana avisa."""
    ahora = ahora or timezone.now()
    avisados = 0
    pendientes = Recordatorio.objects.filter(recordar_en__lte=ahora, avisado=False, hecho=False, usuario__is_active=True).select_related('usuario')
    for r in pendientes:
        reclamado = Recordatorio.objects.filter(pk=r.pk, recordar_en=r.recordar_en, avisado=False, hecho=False)
        if r.repetir == 'NO':
            ganado = reclamado.update(avisado=True, ultimo_aviso=ahora)
        else:
            ganado = reclamado.update(recordar_en=siguiente(r, timezone.localtime(ahora)), ultimo_aviso=ahora)
        if not ganado:
            continue
        atraso = ahora - r.recordar_en
        partes = ([f"Era para las {hora12(r.recordar_en)}"] if atraso > TOLERANCIA_ATRASO else [f"{hora12(r.recordar_en)}"]) + ([r.nota.strip()] if r.nota.strip() else [])
        Notificacion.objects.create(destinatario=r.usuario, tipo='MI_RECORDATORIO', titulo=r.titulo[:255], mensaje=' · '.join(partes)[:500], enlace='/recordatorios')
        avisados += 1
    return avisados


def limpiar_hechos(ahora=None):
    """Borra los recordatorios hechos hace más de 90 días (no sirven para nada y solo ocupan lugar)."""
    ahora = ahora or timezone.now()
    return Recordatorio.objects.filter(hecho=True, recordar_en__lt=ahora - timedelta(days=DIAS_CONSERVAR_HECHOS)).delete()[0]
