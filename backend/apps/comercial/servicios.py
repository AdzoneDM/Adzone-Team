from django.db import transaction
from django.utils import timezone

from apps.desempeno.servicios import avisar

from .models import MovimientoComercial, Oportunidad, SolicitudServicio


def registrar(usuario, tipo, oportunidad=None, solicitud=None, antes='', despues='', texto='', cambios=None):
    return MovimientoComercial.objects.create(usuario=usuario, tipo=tipo, oportunidad=oportunidad, solicitud=solicitud,
                                              estado_antes=antes, estado_despues=despues, texto=texto, cambios=cambios or {})


def gerentes_de(departamento_id):
    """Quienes gestionan el departamento (para avisarles de una solicitud nueva sin responsable)."""
    from django.contrib.auth.models import User

    from apps.operaciones.permisos import departamentos_a_cargo
    from apps.organizacion.models import PuestoDeTrabajo
    candidatos = User.objects.filter(is_active=True, perfil__puesto_trabajo__in=PuestoDeTrabajo.objects.filter(
        departamento_id=departamento_id)).distinct()
    salida = []
    for u in candidatos:
        a_cargo = departamentos_a_cargo(u)
        if a_cargo is not None and departamento_id in a_cargo:
            salida.append(u)
    return salida


def _valor(v):
    if hasattr(v, 'pk'):
        return str(v)
    return '' if v is None else str(v)


def guardar_cambios(instancia, datos, usuario, motivo=''):
    """Aplica `datos` y deja en el historial el antes y el después (estado aparte, como cambio de estado)."""
    estado_antes = instancia.estado
    cambios = {}
    for campo, valor in datos.items():
        antes = getattr(instancia, campo)
        if _valor(antes) != _valor(valor):
            cambios[campo] = {'antes': _valor(antes), 'despues': _valor(valor)}
            setattr(instancia, campo, valor)
    if not cambios:
        return instancia, {}
    if isinstance(instancia, Oportunidad) and 'estado' in cambios:
        instancia.fecha_cierre = timezone.now() if instancia.estado in Oportunidad.CERRADOS else None
    instancia.save()
    kw = {'oportunidad': instancia} if isinstance(instancia, Oportunidad) else {'solicitud': instancia}
    if 'estado' in cambios:
        registrar(usuario, 'ESTADO', antes=estado_antes, despues=instancia.estado, texto=motivo[:4000], **kw)
    otros = {k: v for k, v in cambios.items() if k != 'estado'}
    if otros:
        registrar(usuario, 'CAMBIO', cambios=otros, **kw)
    return instancia, cambios


def avisar_solicitud_nueva(s, quien):
    destinatarios = [s.responsable] if s.responsable else gerentes_de(s.departamento_id)
    avisar(destinatarios, 'COMERCIAL', f"Solicitud de servicio {s.codigo}: {s.servicio_nombre}",
           f"Cliente: {s.cliente}. {s.descripcion[:200]}", enlace=f"/oportunidades?solicitud={s.pk}", excepto=quien)


@transaction.atomic
def convertir_en_proyecto(s, usuario):
    """La solicitud aprobada se vuelve proyecto: el proyecto se enlaza (cliente, servicio y descripción no se copian a mano)."""
    from apps.operaciones.models import Proyecto
    proyecto = Proyecto.objects.create(
        nombre=f"{s.servicio_nombre} · {s.cliente.nombre}"[:200], cliente=s.cliente, departamento=s.departamento,
        responsable=s.responsable or usuario, creado_por=usuario,
        descripcion=f"Desde la solicitud {s.codigo}" + (f" (oportunidad {s.oportunidad.codigo})" if s.oportunidad_id else '')
                    + (f".\n\n{s.descripcion}" if s.descripcion else '.'))
    antes = s.estado
    s.proyecto, s.estado = proyecto, 'EN_EJECUCION'
    s.save(update_fields=['proyecto', 'estado', 'fecha_modificacion'])
    registrar(usuario, 'CONVERSION', solicitud=s, antes=antes, despues=s.estado, texto=f"Proyecto {proyecto.codigo}")
    if s.oportunidad_id:
        registrar(usuario, 'CONVERSION', oportunidad=s.oportunidad, texto=f"{s.codigo} → proyecto {proyecto.codigo}")
    return proyecto


@transaction.atomic
def enlazar_orden(s, orden, usuario):
    antes = s.estado
    s.orden, s.estado = orden, 'EN_EJECUCION'
    s.save(update_fields=['orden', 'estado', 'fecha_modificacion'])
    registrar(usuario, 'CONVERSION', solicitud=s, antes=antes, despues=s.estado, texto=f"Orden de trabajo {orden.codigo}")
    if s.oportunidad_id:
        registrar(usuario, 'CONVERSION', oportunidad=s.oportunidad, texto=f"{s.codigo} → orden {orden.codigo}")


def avisar_seguimientos(hoy=None):
    """Oportunidades abiertas con el seguimiento para hoy o atrasado: aviso diario a su responsable (para el cron)."""
    hoy = hoy or timezone.localdate()
    n = 0
    for o in (Oportunidad.objects.exclude(estado__in=Oportunidad.CERRADOS).filter(proximo_seguimiento__lte=hoy)
              .select_related('cliente', 'responsable', 'creado_por')):
        quien = o.responsable or o.creado_por
        if quien is None:
            continue
        atraso = (hoy - o.proximo_seguimiento).days
        avisar([quien], 'COMERCIAL', f"Seguimiento pendiente: {o.cliente}",
               f"{o.codigo} · {o.titulo} · {o.get_estado_display()}" + (f" · {atraso} día(s) de atraso" if atraso else " · hoy"),
               enlace=f"/oportunidades?oportunidad={o.pk}")
        n += 1
    return n
