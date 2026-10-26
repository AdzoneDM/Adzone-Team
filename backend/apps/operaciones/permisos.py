"""
Quién ve y quién gestiona clientes, proyectos y órdenes.

- Administración general (administradores) y Finanzas ven todo.
- Quien supervisa gestiona las órdenes y proyectos de su departamento y de los departamentos
  de los puestos que dependen de él.
- Cada colaborador ve el tablero de su departamento y lo que pidió, tiene a cargo o en lo que participa.
- Los montos (precios, presupuestos) solo los ven Finanzas, administradores y quien gestiona.
"""
from django.db.models import Q

from apps.desempeno.permisos import es_administrador, puesto_de, puestos_debajo

DEPARTAMENTO_FINANZAS = 'Administración'


def es_finanzas(user):
    if not (user and user.is_authenticated):
        return False
    if es_administrador(user) or user.groups.filter(name='Finanzas').exists():
        return True
    puesto = puesto_de(user)
    return bool(puesto and puesto.departamento and puesto.departamento.nombre == DEPARTAMENTO_FINANZAS)


def departamentos_a_cargo(user):
    """Ids de departamentos que `user` gestiona. None = todos (administrador)."""
    if es_administrador(user):
        return None
    puesto = puesto_de(user)
    if puesto is None:
        return set()
    debajo = puestos_debajo(puesto)
    if not debajo:
        return set()
    from apps.organizacion.models import PuestoDeTrabajo
    ids = set(PuestoDeTrabajo.objects.filter(id__in=debajo).values_list('departamento_id', flat=True))
    ids.add(puesto.departamento_id)
    ids.discard(None)
    return ids


def mi_departamento(user):
    puesto = puesto_de(user)
    return puesto.departamento_id if puesto else None


def gestiona_departamento(user, departamento_id):
    a_cargo = departamentos_a_cargo(user)
    return a_cargo is None or departamento_id in a_cargo


def filtro_ordenes(user):
    """Q de las órdenes que `user` puede ver; None = todas."""
    if es_administrador(user) or es_finanzas(user):
        return None
    deptos = set(departamentos_a_cargo(user) or set())
    propio = mi_departamento(user)
    if propio:
        deptos.add(propio)
    from apps.desempeno.permisos import subordinados
    # También lo que pidió o trabaja su gente: el gerente sigue los pedidos de su equipo a otras áreas.
    return (Q(solicitada_por=user) | Q(responsable=user) | Q(equipo=user) | Q(departamento_id__in=deptos)
            | Q(tareas__colaborador=user) | Q(tareas__companeros=user) | Q(solicitada_por__in=subordinados(user)))


def puede_gestionar_orden(user, orden):
    return gestiona_departamento(user, orden.departamento_id)


def filtro_proyectos(user):
    if es_administrador(user) or es_finanzas(user):
        return None
    deptos = set(departamentos_a_cargo(user) or set())
    propio = mi_departamento(user)
    if propio:
        deptos.add(propio)
    return Q(responsable=user) | Q(miembros=user) | Q(departamento_id__in=deptos) | Q(creado_por=user)


def puede_gestionar_proyecto(user, proyecto):
    if proyecto.responsable_id == user.pk or es_administrador(user):
        return True
    return bool(proyecto.departamento_id) and gestiona_departamento(user, proyecto.departamento_id)


def ve_montos(user, objeto=None):
    """Precios y presupuestos: Finanzas, administradores y quien gestiona ese departamento o proyecto."""
    if es_finanzas(user):
        return True
    if objeto is None:
        return gestiona_algo(user)
    if hasattr(objeto, 'miembros') and objeto.responsable_id == user.pk:
        return True
    depto = getattr(objeto, 'departamento_id', None)
    return depto is not None and gestiona_departamento(user, depto)


def gestiona_algo(user):
    return es_administrador(user) or bool(departamentos_a_cargo(user))
