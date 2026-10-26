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


def _en_grupo(user, nombre):
    return bool(user and user.is_authenticated and user.groups.filter(name=nombre).exists())


def es_gerencia(user):
    """Gerencia General: los administradores (dirección)."""
    return es_administrador(user)


def es_coordinacion(user):
    """Coordinación de Producción: recibe y numera las OT (G0), emite las OA y autoriza vales."""
    return es_administrador(user) or _en_grupo(user, 'Coordinación')


def es_almacen(user):
    return es_administrador(user) or _en_grupo(user, 'Almacén')


def areas_que_supervisa(user):
    """Códigos de área que `user` supervisa: los asignados en AreaConfig o, si el área no tiene, por departamento."""
    from .formatos import AREAS
    from .models import AreaConfig
    if es_administrador(user):
        return list(AREAS)
    asignadas = set(AreaConfig.objects.filter(supervisores=user).values_list('codigo', flat=True))
    con_supervisores = set(AreaConfig.objects.filter(supervisores__isnull=False).values_list('codigo', flat=True))
    a_cargo = departamentos_a_cargo(user) or set()
    if a_cargo:
        for codigo, depto in departamento_de_areas().items():
            if codigo not in con_supervisores and depto in a_cargo:
                asignadas.add(codigo)
    return sorted(asignadas)


def departamento_de_areas():
    """{código de área: id del departamento que la hace}. AreaConfig manda; si no hay, el nombre del formato."""
    from apps.core.models import Departamento
    from .formatos import AREAS
    from .models import AreaConfig
    por_nombre = dict(Departamento.objects.values_list('nombre', 'id'))
    mapa = {c: por_nombre.get(v['departamento']) for c, v in AREAS.items()}
    mapa.update({c: d for c, d in AreaConfig.objects.exclude(departamento__isnull=True).values_list('codigo', 'departamento_id')})
    return mapa


def supervisa_area(user, codigo):
    return codigo in areas_que_supervisa(user)


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
    if es_administrador(user) or es_finanzas(user) or es_coordinacion(user) or es_almacen(user):
        return None
    deptos = set(departamentos_a_cargo(user) or set())
    propio = mi_departamento(user)
    if propio:
        deptos.add(propio)
    from apps.desempeno.permisos import subordinados
    codigos = {c for c, d in departamento_de_areas().items() if d in deptos} | set(areas_que_supervisa(user))
    # También lo que pidió o trabaja su gente: el gerente sigue los pedidos de su equipo a otras áreas.
    return (Q(solicitada_por=user) | Q(responsable=user) | Q(equipo=user) | Q(departamento_id__in=deptos)
            | Q(tareas__colaborador=user) | Q(tareas__companeros=user) | Q(solicitada_por__in=subordinados(user))
            | Q(asesor_comercial=user) | Q(areas__responsable=user) | Q(areas__area__in=codigos))


def puede_gestionar_orden(user, orden):
    """La OT Maestra la gestiona Coordinación de Producción (y la dirección)."""
    return es_coordinacion(user)


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
        return gestiona_algo(user) or es_coordinacion(user)
    if hasattr(objeto, 'solicitud'):  # OT Maestra: Coordinación y quien la vendió
        return es_coordinacion(user) or user.pk in (objeto.asesor_comercial_id, objeto.solicitada_por_id)
    if hasattr(objeto, 'miembros') and objeto.responsable_id == user.pk:
        return True
    depto = getattr(objeto, 'departamento_id', None)
    return depto is not None and gestiona_departamento(user, depto)


def gestiona_algo(user):
    return es_administrador(user) or bool(departamentos_a_cargo(user))
