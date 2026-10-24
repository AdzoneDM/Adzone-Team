"""
Quién puede gestionar a quién, según el organigrama de puestos.

- El administrador gestiona a todos.
- Un supervisor gestiona a todos los que dependen de su puesto en el organigrama, directa o
  indirectamente: el gerente gestiona a sus encargados y también a los colaboradores de ellos
  (como en Adzone Team). Un encargado gestiona solo lo que cuelga de su puesto.
- Nadie valida, devuelve ni reabre sus propias tareas, aunque sea administrador.
"""
from django.contrib.auth.models import User
from rest_framework import permissions


def es_administrador(user):
    return bool(user and user.is_authenticated and (user.is_staff or user.groups.filter(name='Administrador').exists()))


def puesto_de(user):
    return getattr(getattr(user, 'perfil', None), 'puesto_trabajo', None)


def puestos_debajo(puesto):
    """Ids de todos los puestos que dependen de `puesto` (en cualquier nivel)."""
    from apps.organizacion.models import PuestoDeTrabajo
    hijos_de = {}
    for pid, sup in PuestoDeTrabajo.objects.values_list('id', 'supervisor_id'):
        hijos_de.setdefault(sup, []).append(pid)
    encontrados, pendientes = set(), list(hijos_de.get(puesto.id, []))
    while pendientes:
        pid = pendientes.pop()
        if pid in encontrados or pid == puesto.id:
            continue
        encontrados.add(pid)
        pendientes.extend(hijos_de.get(pid, []))
    return encontrados


def subordinados(user):
    """Usuarios activos cuyos puestos dependen (directa o indirectamente) del puesto de `user`."""
    puesto = puesto_de(user)
    if puesto is None:
        return User.objects.none()
    return User.objects.filter(is_active=True, perfil__puesto_trabajo__in=puestos_debajo(puesto)).exclude(pk=user.pk)


def subordinados_directos(user):
    puesto = puesto_de(user)
    if puesto is None:
        return User.objects.none()
    return User.objects.filter(is_active=True, perfil__puesto_trabajo__supervisor=puesto).exclude(pk=user.pk)


def equipo_gestionable(user):
    """Colaboradores a los que `user` puede asignar y validar tareas."""
    if es_administrador(user):
        return User.objects.filter(is_active=True)
    return subordinados(user)


def puede_gestionar(user, colaborador):
    """Asignar, editar o borrar tareas de `colaborador`."""
    return es_administrador(user) or subordinados(user).filter(pk=colaborador.pk).exists()


def puede_revisar(user, colaborador):
    """Validar, devolver o reabrir: como gestionar, pero nunca el trabajo propio."""
    return user.pk != colaborador.pk and puede_gestionar(user, colaborador)


def puede_validar(user):
    return es_administrador(user) or subordinados(user).exists()


def revisores_de(colaborador):
    """
    A quién avisar cuando `colaborador` entrega: quien ocupe el puesto del que depende.
    Si ese puesto está vacante, sube por el organigrama; si no hay nadie, los administradores.
    """
    puesto = puesto_de(colaborador)
    vistos = set()
    while puesto is not None and puesto.supervisor_id and puesto.supervisor_id not in vistos:
        vistos.add(puesto.supervisor_id)
        jefes = User.objects.filter(is_active=True, perfil__puesto_trabajo_id=puesto.supervisor_id).exclude(pk=colaborador.pk)
        if jefes.exists():
            return list(jefes)
        puesto = puesto.supervisor
    return list(administradores().exclude(pk=colaborador.pk))


def administradores():
    from django.db.models import Q
    return User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(groups__name='Administrador')).distinct()


class EsAdministrador(permissions.BasePermission):
    message = "Solo un administrador puede hacer esto."

    def has_permission(self, request, view):
        return es_administrador(request.user)


class LecturaOAdministrador(permissions.BasePermission):
    """Cualquiera con sesión puede consultar; solo el administrador crea, edita o borra."""
    message = "Solo un administrador puede modificar estos datos."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in permissions.SAFE_METHODS or es_administrador(request.user)
