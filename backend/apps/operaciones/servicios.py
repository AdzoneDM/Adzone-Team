"""Lo que pasa cuando una orden cambia: historial, avisos, tarea de producción y automatizaciones."""
import re

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from apps.desempeno import servicios as tareas_srv
from apps.desempeno.models import PasoTarea, Tarea
from apps.desempeno.servicios import avisar, nombre
from .formularios import TIPOS
from .models import EventoOrden, OrdenTrabajo

PRIORIDAD_TAREA = {'BAJA': 'BAJA', 'NORMAL': 'MEDIA', 'ALTA': 'ALTA', 'URGENTE': 'ALTA'}


def disparar(evento, objeto, quien=None, **extra):
    from apps.automatizaciones.motor import disparar as _disparar
    _disparar(evento, objeto, quien=quien, **extra)


def registrar(orden, usuario, texto, detalle=''):
    EventoOrden.objects.create(orden=orden, usuario=usuario, texto=texto[:255], detalle=detalle or '')


def enlace(orden):
    return f"/ordenes/{orden.pk}"


def jefes_de_departamento(departamento_id):
    """Quienes gestionan el departamento: ocupan un puesto del que dependen otros de ese departamento."""
    from apps.desempeno.permisos import administradores
    from apps.organizacion.models import PuestoDeTrabajo
    con_gente_debajo = set(PuestoDeTrabajo.objects.filter(departamento_id=departamento_id, supervisor__isnull=False)
                           .values_list('supervisor_id', flat=True))
    jefes = list(User.objects.filter(is_active=True, perfil__puesto_trabajo_id__in=con_gente_debajo,
                                     perfil__puesto_trabajo__departamento_id=departamento_id))
    return jefes or list(administradores())


def al_crear(orden, quien):
    registrar(orden, quien, 'Orden solicitada')
    avisar(jefes_de_departamento(orden.departamento_id), 'ORDEN', f"Nueva orden {orden.numero}: {orden.titulo}",
           f"{nombre(quien)} la pidió para {orden.cliente}. Revísala y apruébala.", enlace=enlace(orden), excepto=quien)
    disparar('ORDEN_CREADA', orden, quien)


def cambiar_estado(orden, nuevo, quien, detalle='', forzar=False):
    """Mueve la orden respetando el flujo. Devuelve un texto de error o None."""
    if nuevo == orden.estado:
        return None
    if not forzar and nuevo not in OrdenTrabajo.TRANSICIONES.get(orden.estado, []):
        return (f"Una orden «{orden.get_estado_display()}» no puede pasar a "
                f"«{dict(OrdenTrabajo.ESTADOS)[nuevo]}».")
    if nuevo == 'LISTA' and not forzar and orden.tareas.filter(estado__in=['PENDIENTE', 'EN_PROGRESO', 'EN_REVISION']).exists():
        return "Faltan tareas por terminar y validar antes de marcarla lista."
    anterior = orden.get_estado_display()
    if nuevo == 'EN_PAUSA':
        orden.estado_antes_pausa = orden.estado
    orden.estado = nuevo
    if nuevo == 'LISTA':
        orden.fecha_lista = timezone.now()
    orden.save()
    registrar(orden, quien, f"{anterior} → {orden.get_estado_display()}", detalle)
    destinatarios = [orden.responsable, *orden.equipo.all()]
    if nuevo in ('LISTA', 'ENTREGADA', 'CANCELADA'):
        destinatarios.append(orden.solicitada_por)
    avisar(destinatarios, 'ORDEN', f"{orden.numero} · {orden.get_estado_display()}", f"{orden.titulo} ({orden.cliente}).",
           enlace=enlace(orden), excepto=quien)
    disparar('ORDEN_ESTADO', orden, quien)
    return None


@transaction.atomic
def aprobar(orden, quien, responsable, equipo, fecha_compromiso, pasos=None, crear_tarea=True):
    orden.responsable = responsable
    orden.fecha_compromiso = fecha_compromiso
    orden.aprobada_por = quien
    orden.fecha_aprobacion = timezone.now()
    orden.save()
    orden.equipo.set([u for u in equipo if u.pk != responsable.pk])
    tarea = None
    if crear_tarea:
        pasos = pasos if pasos is not None else TIPOS[orden.tipo]['pasos']
        tarea = Tarea.objects.create(
            titulo=f"{orden.numero} · {orden.titulo}", descripcion=orden.descripcion, cliente=orden.cliente.nombre,
            colaborador=responsable, asignada_por=quien, prioridad=PRIORIDAD_TAREA[orden.prioridad],
            fecha_limite=fecha_compromiso, fecha_inicio=timezone.localdate(), orden=orden, proyecto=orden.proyecto)
        tarea.companeros.set(orden.equipo.all())
        for i, texto in enumerate(p.strip() for p in pasos if p and p.strip()):
            PasoTarea.objects.create(tarea=tarea, texto=texto[:255], orden=i)
        tareas_srv.al_asignar(tarea, quien)
    error = cambiar_estado(orden, 'APROBADA', quien, f"Responsable: {nombre(responsable)}. Compromiso: {fecha_compromiso:%d/%m/%Y}.")
    if error is None:
        avisar([orden.solicitada_por], 'ORDEN', f"Aprobada: {orden.numero}",
               f"{nombre(responsable)} la tiene a cargo. Fecha comprometida: {fecha_compromiso:%d/%m/%Y}.",
               enlace=enlace(orden), excepto=quien)
    return tarea


def entregar(orden, quien, recibido_por, nota=''):
    orden.fecha_entrega = timezone.localdate()
    orden.recibido_por = recibido_por
    orden.save(update_fields=['fecha_entrega', 'recibido_por', 'fecha_modificacion'])
    return cambiar_estado(orden, 'ENTREGADA', quien, f"Recibió: {recibido_por}. {nota}".strip())


def sincronizar_desde_tareas(tarea, quien):
    """La orden sigue a sus tareas: empezar → producción, entregar → calidad, validar todo → lista."""
    orden = tarea.orden
    if orden is None or orden.estado not in ('APROBADA', 'EN_PRODUCCION', 'CONTROL_CALIDAD', 'LISTA'):
        return
    estados = list(orden.tareas.exclude(estado='CANCELADA').values_list('estado', flat=True))
    if not estados:
        return
    if all(e == 'COMPLETADA' for e in estados):
        nuevo = 'LISTA'
    elif any(e == 'EN_REVISION' for e in estados) and not any(e in ('PENDIENTE', 'EN_PROGRESO') for e in estados):
        nuevo = 'CONTROL_CALIDAD'
    elif any(e in ('EN_PROGRESO', 'COMPLETADA', 'EN_REVISION') for e in estados):
        nuevo = 'EN_PRODUCCION'
    else:
        return
    if nuevo != orden.estado:
        cambiar_estado(orden, nuevo, quien, f"Por la tarea «{tarea.titulo}».", forzar=True)


MENCION = re.compile(r'@([\w.\-]+)')


def mencionados(texto, excepto=None):
    nombres = {m.lower() for m in MENCION.findall(texto or '')}
    if not nombres:
        return []
    usuarios = [u for u in User.objects.filter(is_active=True) if u.username.lower() in nombres]
    return [u for u in usuarios if not excepto or u.pk != excepto.pk]


def al_comentar(comentario):
    objeto = comentario.orden or comentario.proyecto
    if comentario.orden:
        titulo, link = f"{comentario.orden.numero}", enlace(comentario.orden)
        interesados = [comentario.orden.responsable, comentario.orden.solicitada_por, *comentario.orden.equipo.all()]
    else:
        titulo, link = comentario.proyecto.codigo, f"/proyectos/{comentario.proyecto.pk}"
        interesados = [comentario.proyecto.responsable, *comentario.proyecto.miembros.all()]
    menciones = mencionados(comentario.texto, comentario.autor)
    avisar(menciones, 'MENCION', f"{nombre(comentario.autor)} te mencionó en {titulo}", comentario.texto[:300],
           enlace=link, excepto=comentario.autor)
    ya = {u.pk for u in menciones}
    avisar([u for u in interesados if u and u.pk not in ya], 'ORDEN' if comentario.orden else 'PROYECTO',
           f"Comentario en {titulo}: {getattr(objeto, 'titulo', None) or objeto.nombre}", comentario.texto[:300],
           enlace=link, excepto=comentario.autor)
