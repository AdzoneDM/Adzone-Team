"""Acciones que dejan rastro: historial de la tarea, avisos y tareas recurrentes."""
import calendar
import logging
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import HistorialTarea, Notificacion, Tarea, TareaRecurrente
from .permisos import revisores_de

log = logging.getLogger('adzone')


def nombre(usuario):
    return (usuario.get_full_name() or usuario.username) if usuario else 'Alguien'


def registrar(tarea, usuario, accion, comentario=''):
    HistorialTarea.objects.create(tarea=tarea, usuario=usuario, accion=accion, comentario=comentario or '')


def avisar(destinatarios, tipo, titulo, mensaje='', tarea=None, enlace='', excepto=None):
    """Crea un aviso por persona. Nunca se avisa a quien provocó la acción."""
    vistos = set()
    for usuario in destinatarios:
        if usuario is None or usuario.pk in vistos or (excepto and usuario.pk == excepto.pk):
            continue
        vistos.add(usuario.pk)
        Notificacion.objects.create(destinatario=usuario, remitente=excepto, tipo=tipo, titulo=titulo[:255],
                                    mensaje=mensaje, tarea=tarea, enlace=enlace)


def al_asignar(tarea, quien):
    registrar(tarea, quien, 'CREADA')
    avisar([tarea.colaborador, *tarea.companeros.all()], 'ASIGNADA', f"Nueva tarea: {tarea.titulo}",
           f"{nombre(quien)} te la asignó. Entrega: {tarea.fecha_limite:%d/%m/%Y}.",
           tarea=tarea, enlace='/mis-tareas', excepto=quien)


def al_entregar(tarea, quien):
    registrar(tarea, quien, 'ENTREGADA', tarea.evidencia_nota)
    ronda = f" (entrega n.º {tarea.rondas_revision + 1})" if tarea.rondas_revision else ''
    avisar(revisores_de(tarea.colaborador), 'ENTREGADA', f"Por validar: {tarea.titulo}",
           f"{nombre(quien)} la entregó{ronda}.", tarea=tarea, enlace='/validar', excepto=quien)


def al_validar(tarea, quien):
    estrellas = f" · {tarea.calificacion_calidad}/5" if tarea.calificacion_calidad else ''
    registrar(tarea, quien, 'VALIDADA', f"Calidad {tarea.calificacion_calidad}/5. {tarea.comentario_evaluacion}".strip())
    avisar([tarea.colaborador, *tarea.companeros.all()], 'VALIDADA', f"Validada: {tarea.titulo}",
           f"{nombre(quien)} validó tu entrega{estrellas}. Ya cuenta para tu puntaje.",
           tarea=tarea, enlace='/mis-tareas?ver=validadas', excepto=quien)


def al_devolver(tarea, quien):
    registrar(tarea, quien, 'DEVUELTA', tarea.comentario_revision)
    avisar([tarea.colaborador, *tarea.companeros.all()], 'DEVUELTA', f"Para corregir: {tarea.titulo}",
           tarea.comentario_revision, tarea=tarea, enlace='/mis-tareas', excepto=quien)


def al_reabrir(tarea, quien, motivo):
    registrar(tarea, quien, 'REABIERTA', motivo)
    avisar([tarea.colaborador, *tarea.companeros.all()], 'REABIERTA', f"Reabierta: {tarea.titulo}",
           motivo or f"{nombre(quien)} la volvió a poner en revisión.", tarea=tarea, enlace='/mis-tareas', excepto=quien)


# ---------------------------------------------------------------------------
# Tareas recurrentes
# ---------------------------------------------------------------------------
DIAS_ADELANTE = 7  # se crean con una semana de anticipación para que el colaborador las vea venir


def fechas_de(recurrente, desde, hasta):
    """Fechas de entrega de la recurrente entre `desde` y `hasta` (incluidas)."""
    fechas = []
    if recurrente.frecuencia == 'SEMANAL':
        dia = desde + timedelta(days=(recurrente.dia_semana - desde.weekday()) % 7)
        while dia <= hasta:
            fechas.append(dia)
            dia += timedelta(days=7)
    else:
        anio, mes = desde.year, desde.month
        while True:
            ultimo = calendar.monthrange(anio, mes)[1]
            dia = date(anio, mes, min(recurrente.dia_mes, ultimo))
            if dia > hasta:
                break
            if dia >= desde:
                fechas.append(dia)
            mes += 1
            if mes > 12:
                anio, mes = anio + 1, 1
    return fechas


def generar_recurrentes(hoy=None):
    """Crea las tareas de las recurrentes activas hasta una semana adelante. Se puede llamar las veces que sea."""
    hoy = hoy or timezone.localdate()
    hasta = hoy + timedelta(days=DIAS_ADELANTE)
    creadas = 0
    for rec in TareaRecurrente.objects.filter(activa=True, colaborador__is_active=True).select_related('colaborador'):
        desde = max(rec.inicio, (rec.generada_hasta + timedelta(days=1)) if rec.generada_hasta else rec.inicio)
        if desde > hasta:
            continue
        with transaction.atomic():
            for fecha in fechas_de(rec, desde, hasta):
                if Tarea.objects.filter(recurrencia=rec, fecha_limite=fecha).exists():
                    continue
                tarea = Tarea.objects.create(
                    titulo=rec.titulo, descripcion=rec.descripcion, colaborador=rec.colaborador,
                    asignada_por=rec.creada_por, kpi_asignado=rec.kpi_asignado, prioridad=rec.prioridad,
                    fecha_limite=fecha, recurrencia=rec,
                )
                registrar(tarea, rec.creada_por, 'CREADA', 'Generada automáticamente por una tarea recurrente.')
                avisar([rec.colaborador], 'ASIGNADA', f"Nueva tarea: {tarea.titulo}",
                       f"Tarea recurrente. Entrega: {fecha:%d/%m/%Y}.", tarea=tarea, enlace='/mis-tareas')
                creadas += 1
            rec.generada_hasta = hasta
            rec.save(update_fields=['generada_hasta'])
    if creadas:
        log.info("Tareas recurrentes generadas: %s", creadas)
    return creadas


_ultima_generacion = {'dia': None}


def generar_recurrentes_si_toca():
    """Sin cron en el servidor, se generan la primera vez que alguien abre sus tareas cada día."""
    hoy = timezone.localdate()
    if _ultima_generacion['dia'] == hoy:
        return
    _ultima_generacion['dia'] = hoy
    try:
        generar_recurrentes(hoy)
    except Exception:  # nunca debe impedir que se vea la lista de tareas
        log.exception("No se pudieron generar las tareas recurrentes")


def avisar_por_vencer(hoy=None):
    """Aviso del día anterior a la fecha límite (para el cron diario)."""
    hoy = hoy or timezone.localdate()
    manana = hoy + timedelta(days=1)
    n = 0
    for tarea in Tarea.objects.filter(fecha_limite=manana, estado__in=['PENDIENTE', 'EN_PROGRESO']).select_related('colaborador'):
        if Notificacion.objects.filter(tarea=tarea, tipo='VENCE').exists():
            continue
        avisar([tarea.colaborador], 'VENCE', f"Vence mañana: {tarea.titulo}", '', tarea=tarea, enlace='/mis-tareas')
        n += 1
    return n


# ---------------------------------------------------------------------------
# Recordar y pedir trabajo (ideas traídas de Adzone Team)
# ---------------------------------------------------------------------------
ESPERA_RECORDATORIO = timedelta(hours=1)
ESPERA_PEDIR_TRABAJO = timedelta(hours=2)


def recordar(tarea, quien, mensaje=''):
    """El supervisor le recuerda una tarea abierta al colaborador. Como mucho una vez por hora por tarea."""
    hace_poco = timezone.now() - ESPERA_RECORDATORIO
    if Notificacion.objects.filter(tarea=tarea, tipo='RECORDATORIO', fecha__gte=hace_poco).exists():
        return "Ya se le recordó esta tarea hace menos de una hora."
    avisar([tarea.colaborador, *tarea.companeros.all()], 'RECORDATORIO', f"{nombre(quien)} te pide avanzar: {tarea.titulo}",
           mensaje or f"Entrega: {tarea.fecha_limite:%d/%m/%Y}.", tarea=tarea, enlace=f'/mis-tareas?tarea={tarea.id}',
           excepto=quien)
    return None


def pedir_trabajo(quien):
    """El colaborador sin tareas pendientes avisa a su supervisor que puede tomar más."""
    abiertas = Tarea.objects.filter(Q(colaborador=quien) | Q(companeros=quien), estado__in=['PENDIENTE', 'EN_PROGRESO']).distinct().count()
    if abiertas:
        return f"Todavía tienes {abiertas} tarea(s) por hacer. Pide más cuando termines."
    hace_poco = timezone.now() - ESPERA_PEDIR_TRABAJO
    if Notificacion.objects.filter(remitente=quien, tipo='PIDE_TRABAJO', fecha__gte=hace_poco).exists():
        return "Ya avisaste hace poco. Tu supervisor ya lo sabe."
    jefes = revisores_de(quien)
    avisar(jefes, 'PIDE_TRABAJO', f"{nombre(quien)} terminó sus tareas y pide más trabajo",
           "No tiene tareas pendientes.", enlace=f'/equipo?colaborador={quien.id}', excepto=quien)
    return [nombre(j) for j in jefes]
