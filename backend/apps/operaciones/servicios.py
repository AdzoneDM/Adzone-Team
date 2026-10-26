"""Utilidades de órdenes: historial, avisos, pausa/cancelación y comentarios. El flujo de compuertas está en servicios_ot."""
import re

from django.contrib.auth.models import User

from apps.desempeno.servicios import avisar, nombre
from .models import EventoOrden, OrdenTrabajo

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


def pausar(orden, quien, motivo):
    if orden.estado not in OrdenTrabajo.PRODUCCION:
        return "Solo se pausa una OT en producción."
    orden.estado_antes_pausa = orden.estado
    orden.estado = 'EN_PAUSA'
    orden.save(update_fields=['estado', 'estado_antes_pausa'])
    registrar(orden, quien, "En pausa", motivo)
    avisar([orden.responsable, *[oa.responsable for oa in orden.areas.all()]], 'ORDEN', f"{orden.codigo} en pausa", motivo,
           enlace=enlace(orden), excepto=quien)
    disparar('ORDEN_ESTADO', orden, quien)


def reanudar(orden, quien):
    if orden.estado != 'EN_PAUSA':
        return "La OT no está en pausa."
    orden.estado = orden.estado_antes_pausa if orden.estado_antes_pausa in OrdenTrabajo.PRODUCCION else 'LIBERADA'
    orden.save(update_fields=['estado'])
    registrar(orden, quien, "Reanudada")
    from .servicios_ot import sincronizar_orden
    sincronizar_orden(orden, quien)
    disparar('ORDEN_ESTADO', orden, quien)


def cancelar(orden, quien, motivo):
    if orden.estado in ('ENTREGADA', 'CERRADA', 'CANCELADA'):
        return "Esta OT ya no se puede cancelar."
    orden.estado = 'CANCELADA'
    orden.motivo_cancelacion = motivo
    orden.save(update_fields=['estado', 'motivo_cancelacion'])
    orden.areas.filter(estado__in=['EMITIDA', 'RECHAZADA', 'RECIBIDA', 'EN_EJECUCION', 'EN_APROBACION']).update(estado='CANCELADA')
    orden.tareas.filter(estado__in=['PENDIENTE', 'EN_PROGRESO', 'EN_REVISION']).update(estado='CANCELADA')
    registrar(orden, quien, "Cancelada", motivo)
    avisar([orden.solicitada_por, orden.asesor_comercial, orden.responsable, *[oa.responsable for oa in orden.areas.all()]],
           'ORDEN', f"Cancelada: {orden.codigo}", motivo, enlace=enlace(orden), excepto=quien)
    disparar('ORDEN_ESTADO', orden, quien)


def sincronizar_desde_tareas(tarea, quien):
    """La Orden de Área sigue a su tarea (empezar → E3)."""
    if tarea.oa_id:
        from .servicios_ot import sincronizar_desde_tarea
        sincronizar_desde_tarea(tarea, quien)


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
        o = comentario.orden
        titulo, link = o.codigo, enlace(o)
        interesados = [o.responsable, o.solicitada_por, o.asesor_comercial, *o.equipo.all(), *[oa.responsable for oa in o.areas.all()]]
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
