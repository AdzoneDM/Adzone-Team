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
from django.db.models import Q
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
    """Su equipo: quienes dependen de su puesto en el organigrama, más su equipo adicional vigente.
    Con el permiso «Supervisar a toda la empresa»: todo el personal activo, salvo Dirección."""
    from apps.core.permisos import extras
    if tiene(user, 'equipo.todos'):
        return User.objects.filter(is_active=True).exclude(pk=user.pk).exclude(pk__in=administradores().values('pk'))
    ids = set(subordinados(user).values_list('pk', flat=True)) | set(extras(user))
    ids.discard(user.pk)
    return User.objects.filter(is_active=True, pk__in=ids)


def equipo_gestionable(user, permiso='equipo.ver'):
    """Personas sobre las que `user` puede ejercer `permiso`: todas si es Dirección, su equipo si tiene el permiso, nadie si no."""
    if not (user and user.is_authenticated):
        return User.objects.none()
    if es_administrador(user):
        return User.objects.filter(is_active=True)
    base = equipo_base(user) if tiene(user, permiso) else User.objects.none()
    if permiso == 'tareas.asignar' and tiene(user, 'tareas.propias'):
        base = User.objects.filter(Q(pk__in=base.values('pk')) | Q(pk=user.pk), is_active=True)
    return base


def puede_gestionar(user, colaborador, permiso='equipo.ver'):
    """¿Puede `user` ejercer `permiso` sobre `colaborador`? (Por defecto: ver su trabajo.)"""
    if es_administrador(user):
        return True
    if colaborador.pk == user.pk:
        # A sí mismo solo se asigna con «Asignarse tareas a sí mismo»; lo demás sobre uno mismo no aplica
        return permiso == 'tareas.asignar' and tiene(user, 'tareas.propias')
    return tiene(user, permiso) and equipo_base(user).filter(pk=colaborador.pk).exists()


def puede_asignar(user, colaborador):
    return puede_gestionar(user, colaborador, 'tareas.asignar')


# ---------------------------------------------------------------------------------------------------------------------
# Asignar entre áreas («Asignar tareas a otras áreas»): una jefatura puede pedir un aporte a cualquier persona de otra área.
# Quedan fuera Dirección y las áreas cerradas (Call Center: lo dirige su propia gerencia). La tarea guarda su área de origen.
# ---------------------------------------------------------------------------------------------------------------------
AREAS_CERRADAS = ('Call Center',)
# Áreas de servicio: cualquier jefatura (quien puede asignar tareas) puede pedirle trabajo a cualquiera de sus integrantes, también a los que
# tienen perfil de Dirección (Tecnología recibe solicitudes de todas las áreas).
AREAS_DE_SERVICIO = ('Tecnología',)


def _de_area_cerrada(colaborador):
    return any(p.departamento.nombre in AREAS_CERRADAS for p in puestos_de(colaborador) if p.departamento_id)


def _de_area_de_servicio(colaborador):
    return any(p.departamento.nombre in AREAS_DE_SERVICIO for p in puestos_de(colaborador) if p.departamento_id)


def entre_areas(user, colaborador):
    """¿Puede `user` asignarle una tarea a `colaborador` sin ser su supervisor? Sí si es de un área de servicio (Tecnología) y `user` puede asignar
    tareas, o con el permiso de otras áreas (menos Dirección y Call Center)."""
    if not (tiene(user, 'tareas.asignar') and colaborador.is_active and colaborador.pk != user.pk) or _de_area_cerrada(colaborador):
        return False
    if _de_area_de_servicio(colaborador):
        return True
    return bool(tiene(user, 'tareas.otras_areas') and not es_administrador(colaborador))


def puede_asignar_a(user, colaborador):
    """Asignar una tarea nueva a `colaborador`: a su equipo (como siempre) o, con el permiso de otras áreas, a cualquier otra área."""
    return puede_gestionar(user, colaborador, 'tareas.asignar') or entre_areas(user, colaborador)


def asignables(user):
    """Personas a las que `user` puede asignar tareas: su equipo (y él mismo si puede) más, con el permiso, las demás áreas."""
    base = equipo_gestionable(user, 'tareas.asignar')
    if es_administrador(user) or not tiene(user, 'tareas.asignar'):
        return base
    cerradas = Q(perfil__puesto_trabajo__departamento__nombre__in=AREAS_CERRADAS) | Q(perfil__puestos_adicionales__departamento__nombre__in=AREAS_CERRADAS)
    servicio = User.objects.filter(is_active=True).exclude(pk=user.pk).filter(
        Q(perfil__puesto_trabajo__departamento__nombre__in=AREAS_DE_SERVICIO) | Q(perfil__puestos_adicionales__departamento__nombre__in=AREAS_DE_SERVICIO)
    ).exclude(cerradas)
    ids = set(base.values_list('pk', flat=True)) | set(servicio.values_list('pk', flat=True))
    if tiene(user, 'tareas.otras_areas'):
        otras = User.objects.filter(is_active=True).exclude(pk=user.pk).exclude(pk__in=administradores().values('pk')).exclude(cerradas)
        ids |= set(otras.values_list('pk', flat=True))
    return User.objects.filter(pk__in=ids, is_active=True)


def tiene_propias(user):
    return bool(tiene(user, 'tareas.propias'))


def tiene_otras_areas(user):
    return bool(tiene(user, 'tareas.asignar') and tiene(user, 'tareas.otras_areas'))


def por_validar(queryset, user):
    """Las entregas que `user` puede validar: las de su equipo, las tareas que él mismo se asignó (autovalidación) y,
    con el permiso de otras áreas, las que pidió a otras áreas."""
    ajenas = Q(colaborador__in=equipo_gestionable(user, 'tareas.validar')) & ~Q(colaborador=user) & ~Q(companeros=user)
    if tiene(user, 'tareas.propias'):
        ajenas |= Q(colaborador=user, asignada_por=user)
    if tiene(user, 'tareas.asignar') and tiene(user, 'tareas.validar'):
        pedidas = Q(asignada_por=user) & ~Q(colaborador=user)
        if not tiene_otras_areas(user):   # sin el permiso de otras áreas, solo lo que pidió a un área de servicio (Tecnología)
            pedidas &= (Q(colaborador__perfil__puesto_trabajo__departamento__nombre__in=AREAS_DE_SERVICIO)
                        | Q(colaborador__perfil__puestos_adicionales__departamento__nombre__in=AREAS_DE_SERVICIO))
        ajenas |= pedidas
    return revisables(queryset.filter(estado='EN_REVISION').filter(ajenas).distinct(), user)


def puede_gestionar_tarea(user, tarea):
    """Editar, reasignar o adjuntar referencias a una tarea ya creada: su supervisor o quien la asignó entre áreas."""
    return puede_gestionar(user, tarea.colaborador, 'tareas.asignar') or (
        tarea.asignada_por_id == user.pk and entre_areas(user, tarea.colaborador))


def puede_autovalidar(user, tarea):
    """Quien tiene «Asignarse tareas a sí mismo» valida esas mismas tareas (las que él creó para sí). Queda en el historial."""
    return bool(tiene(user, 'tareas.propias') and tarea.colaborador_id == user.pk and tarea.asignada_por_id == user.pk)


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
    from apps.core.permisos import con_permiso
    # «Supervisar a toda la empresa»: también le llegan los avisos de todos (salvo de Dirección)
    todos = [] if tiene(colaborador, 'direccion') else [j for j in con_permiso('equipo.todos').exclude(pk=colaborador.pk) if tiene(j, permiso) and not tiene(j, 'direccion')]
    extra = todos + [e.jefe for e in EquipoExtra.objects.filter(colaborador=colaborador, jefe__is_active=True).filter(
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

    @classmethod
    def de_alguno(cls, *permisos):
        """Basta con tener cualquiera de estos permisos."""
        def tiene_alguno(self, request, view):
            return bool(request.user and request.user.is_authenticated and any(tiene(request.user, p) for p in permisos))
        return type('Permiso_' + '_o_'.join(permisos), (cls,), {'has_permission': tiene_alguno})


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


# ---------------------------------------------------------------------------------------------------------------------
# Tareas que la persona se asigna a sí misma: las valida quien ella elige entre los revisores configurados
# (Reglas del puntaje → «Quién revisa las tareas propias»; sin configurar, cualquiera de Dirección).
# ---------------------------------------------------------------------------------------------------------------------
def revisores_propias_ids():
    from .models import ConfiguracionDesempeno
    elegidos = set(ConfiguracionDesempeno.actual().revisores_propias.filter(is_active=True).values_list('pk', flat=True))
    return elegidos or set(administradores().values_list('pk', flat=True))


def revisores_posibles(user):
    """Personas entre las que `user` puede elegir a quien valide sus tareas propias (nunca él mismo)."""
    return User.objects.filter(pk__in=revisores_propias_ids(), is_active=True).exclude(pk=user.pk).select_related(
        'perfil__puesto_trabajo').order_by('first_name', 'last_name', 'username')


def puede_revisar_tarea(user, tarea):
    """Validar, devolver o reabrir una tarea: nunca el trabajo propio. Si la tarea tiene revisor designado, solo él o los
    demás revisores configurados; si no, quien la supervisa (o Dirección)."""
    if puede_autovalidar(user, tarea):
        return True
    if user.pk in tarea.participantes_ids():
        return False
    if tarea.asignada_por_id == user.pk and entre_areas(user, tarea.colaborador) and tiene(user, 'tareas.validar'):
        return True  # quien pidió el aporte a otra área también lo valida
    if tarea.revisor_id:
        return user.pk == tarea.revisor_id or user.pk in revisores_propias_ids()
    return puede_revisar(user, tarea.colaborador)


def revisables(queryset, user):
    """Quita de «por validar» las tareas con revisor designado que `user` no puede revisar."""
    if user.pk in revisores_propias_ids():
        return queryset
    return queryset.filter(Q(revisor__isnull=True) | Q(revisor=user) | Q(colaborador=user, asignada_por=user))


def revisores_de_tarea(tarea):
    """A quién avisar de una entrega o un bloqueo: el revisor designado o, si no hay, la cadena de supervisión."""
    if tarea.revisor_id and tarea.revisor.is_active:
        return [tarea.revisor]
    return revisores_de(tarea.colaborador)
