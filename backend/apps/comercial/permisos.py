"""Quién ve y quién cambia oportunidades y solicitudes. Todo se valida aquí, en el servidor; la pantalla solo lo refleja.

- Oportunidades: el permiso «Oportunidades comerciales» (perfil «Gestión de clientes», es decir, Marketing) y Dirección.
- Solicitudes: además de lo comercial, cada departamento ve SOLO las suyas (no las de otros departamentos del mismo cliente).
- Cambiar una solicitud (estado, responsable, convertirla): Dirección, quien gestiona ese departamento, su responsable, o
  alguien con el permiso comercial que pertenece a ese departamento. Comentar: cualquiera que la vea.
"""
from django.db.models import Q

from apps.desempeno.permisos import es_administrador, puestos_de
from apps.operaciones.permisos import departamentos_a_cargo, gestiona_departamento


def es_comercial(user):
    from apps.core.permisos import tiene
    return bool(user and user.is_authenticated) and (es_administrador(user) or tiene(user, 'comercial.oportunidades'))


def departamentos_propios(user):
    """Departamentos de sus puestos y los que gestiona. None = todos (Dirección)."""
    a_cargo = departamentos_a_cargo(user)
    if a_cargo is None:
        return None
    return set(a_cargo) | {p.departamento_id for p in puestos_de(user) if p.departamento_id}


def filtro_solicitudes(user):
    """Q de las solicitudes que `user` ve; None = todas."""
    if es_comercial(user):
        return None
    propios = departamentos_propios(user)
    if propios is None:
        return None
    return Q(departamento_id__in=propios) | Q(responsable=user)


def ve_solicitudes(user):
    """Si tiene algo que ver en «Solicitudes de servicio» (para mostrarle la sección)."""
    from .models import SolicitudServicio
    if es_comercial(user):
        return True
    f = filtro_solicitudes(user)
    return f is None or SolicitudServicio.objects.filter(f).exists()


def puede_ver_solicitud(user, s):
    f = filtro_solicitudes(user)
    if f is None:
        return True
    propios = departamentos_propios(user) or set()
    return s.departamento_id in propios or s.responsable_id == user.pk


def puede_cambiar_solicitud(user, s):
    if es_administrador(user) or s.responsable_id == user.pk or gestiona_departamento(user, s.departamento_id):
        return True
    return es_comercial(user) and s.departamento_id in (departamentos_propios(user) or set())


def puede_cambiar_oportunidad(user, o):
    return es_comercial(user)
