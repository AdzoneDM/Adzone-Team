"""
Quién puede gestionar a quién: los PERFILES DE ACCESO dicen qué puede hacer cada persona (apps/core/permisos.py) y el
ORGANIGRAMA dice sobre quién (más su equipo adicional).

- Dirección (el perfil «Administrador») gestiona a todos.
- Un supervisor gestiona a todos los que dependen de su puesto en el organigrama, directa o
  indirectamente: el gerente gestiona a sus encargados y también a los colaboradores de ellos
  (como en Adzone Team). Un encargado gestiona solo lo que cuelga de su puesto.
- Nadie valida, devuelve ni reabre sus propias tareas, aunque sea administrador.
"""
from django.contrib.auth.models import User
from rest_framework import permissions


def es_administrador(user):
    """Dirección: el permiso «direccion» (perfil «Administrador»). Ser «staff» de Django ya no da acceso a la plataforma."""
    from apps.core.permisos import tiene
    return bool(user and user.is_authenticated and tiene(user, 'direccion'))


def tiene(user, permiso):
    from apps.core.permisos import tiene as _tiene
    return _tiene(user, permiso)


def puesto_de(user):
    """Puesto principal (KPIs, puntaje, departamento). Para saber a quién supervisa, usar `puestos_de`."""
    return getattr(getattr(user, 'perfil', None), 'puesto_trabajo', None)


def puestos_de(user):
    """Todos los puestos que cubre `user`: el principal y los adicionales (sin repetir)."""
    perfil = getattr(user, 'perfil', None)
    if perfil is None or not getattr(user, 'pk', None):
        return []
    puestos = [perfil.puesto_trabajo] if perfil.puesto_trabajo_id else []
    vistos = {p.pk for p in puestos}
    for p in perfil.puestos_adicionales.all():
        if p.pk not in vistos:
            vistos.add(p.pk)
            puestos.append(p)
    return puestos


def ocupantes_de(puesto_id):
    """Personas activas que cubren un puesto, como principal o adicional."""
    from django.db.models import Q
    return User.objects.filter(Q(perfil__puesto_trabajo_id=puesto_id) | Q(perfil__puestos_adicionales__id=puesto_id),
                               is_active=True).distinct()


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


def puestos_debajo_de(user):
    """Ids de los puestos que dependen de cualquiera de los puestos de `user` (principal o adicionales)."""
    debajo = set()
    for puesto in puestos_de(user):
        debajo |= puestos_debajo(puesto)
    return debajo


def subordinados(user):
    """Usuarios activos cuyo puesto principal depende (directa o indirectamente) de alguno de los puestos de `user`."""
    debajo = puestos_debajo_de(user)
    if not debajo:
        return User.objects.none()
    return User.objects.filter(is_active=True, perfil__puesto_trabajo__in=debajo).exclude(pk=user.pk)


def subordinados_directos(user):
    puestos = [p.pk for p in puestos_de(user)]
    if not puestos:
        return User.objects.none()
    return User.objects.filter(is_active=True, perfil__puesto_trabajo__supervisor__in=puestos).exclude(pk=user.pk)


def equipo_base(user):
    """Su equipo: quienes dependen de su puesto en el organigrama, más su equipo adicional vigente."""
    from apps.core.permisos import extras
    ids = set(subordinados(user).values_list('pk', flat=True)) | set(extras(user))
    ids.discard(user.pk)
    return User.objects.filter(is_active=True, pk__in=ids)


def equipo_gestionable(user, permiso='equipo.ver'):
    """Personas sobre las que `user` puede ejercer `permiso`: todas si es Dirección, su equipo si tiene el permiso, nadie si no."""
    if not (user and user.is_authenticated):
        return User.objects.none()
    if es_administrador(user):
        return User.objects.filter(is_active=True)
    if not tiene(user, permiso):
        return User.objects.none()
    return equipo_base(user)


def puede_gestionar(user, colaborador, permiso='equipo.ver'):
    """¿Puede `user` ejercer `permiso` sobre `colaborador`? (Por defecto: ver su trabajo.)"""
    if es_administrador(user):
        return True
    return tiene(user, permiso) and equipo_base(user).filter(pk=colaborador.pk).exists()


def puede_asignar(user, colaborador):
    return puede_gestionar(user, colaborador, 'tareas.asignar')


def puede_revisar(user, colaborador):
    """Validar, devolver o reabrir: nunca el trabajo propio."""
    return user.pk != colaborador.pk and puede_gestionar(user, colaborador, 'tareas.validar')


def puede_validar(user):
    return es_administrador(user) or (tiene(user, 'tareas.validar') and equipo_base(user).exists())


def revisores_de(colaborador, permiso='tareas.validar'):
    """
    A quién avisar cuando `colaborador` entrega (o a quién le toca evaluarlo): quien ocupe el puesto del que depende
    y tenga el permiso. Si ese puesto está vacante o su ocupante no tiene el permiso, sube por el organigrama; si no hay
    nadie, Dirección. También quien lo tiene en su equipo adicional.
    """
    from apps.core.models import EquipoExtra
    from django.db.models import Q
    from django.utils import timezone
    hoy = timezone.localdate()
    extra = [e.jefe for e in EquipoExtra.objects.filter(colaborador=colaborador, jefe__is_active=True).filter(
        Q(hasta__isnull=True) | Q(hasta__gte=hoy)).select_related('jefe') if tiene(e.jefe, permiso)]
    puesto = puesto_de(colaborador)
    vistos = set()
    while puesto is not None and puesto.supervisor_id and puesto.supervisor_id not in vistos:
        vistos.add(puesto.supervisor_id)
        jefes = [j for j in ocupantes_de(puesto.supervisor_id).exclude(pk=colaborador.pk) if tiene(j, permiso)]
        if jefes:
            return list({u.pk: u for u in jefes + extra}.values())
        puesto = puesto.supervisor
    return list({u.pk: u for u in list(administradores().exclude(pk=colaborador.pk)) + extra}.values())


def administradores():
    """Dirección (quien tiene el permiso «direccion»)."""
    from apps.core.permisos import con_permiso
    return con_permiso('direccion')


class TienePermiso(permissions.BasePermission):
    """Uso: permission_classes = [TienePermiso.de('personal.usuarios')]."""
    permiso = None
    message = "No tienes permiso para esto."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and tiene(request.user, self.permiso))

    @classmethod
    def de(cls, permiso):
        return type(f'Permiso_{permiso}', (cls,), {'permiso': permiso})


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
