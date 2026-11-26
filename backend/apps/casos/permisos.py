"""Quién hace qué con los casos. Usa los accesos que ya existen (no crea ni cambia permisos):

- Reportar: cualquier persona activa (ve los casos que reportó).
- Operaciones (quien tiene su puesto en el departamento de Operaciones) y Dirección: ven todos, clasifican, derivan, escalan,
  documentan el cierre y reabren.
- Área competente: quien gestiona el departamento asignado designa al responsable; el responsable informa avances, bloqueos,
  fecha estimada y la solución. Las personas del área ven los casos asignados a su área.
"""
from django.conf import settings
from django.db.models import Q

from apps.desempeno.permisos import es_administrador, puestos_de
from apps.operaciones.permisos import gestiona_departamento


def departamento_gestor():
    return getattr(settings, 'CASOS_DEPARTAMENTO_GESTOR', 'Operaciones')


def departamentos_de(user):
    return {p.departamento_id for p in puestos_de(user) if p.departamento_id}


def es_operaciones(user):
    if not (user and user.is_authenticated):
        return False
    if es_administrador(user):
        return True
    return any(p.departamento and p.departamento.nombre == departamento_gestor() for p in puestos_de(user))


def filtro(user):
    """Q de los casos que ve `user`; None = todos."""
    if es_operaciones(user):
        return None
    from apps.operaciones.permisos import departamentos_a_cargo
    deptos = departamentos_de(user) | set(departamentos_a_cargo(user) or set())
    return Q(reportado_por=user) | Q(responsable=user) | Q(area_asignada_id__in=deptos)


def puede_ver(user, caso):
    f = filtro(user)
    if f is None:
        return True
    from .models import Caso
    return Caso.objects.filter(f, pk=caso.pk).exists()


def gestiona_area(user, caso):
    """Quien gestiona el área asignada (designa al responsable)."""
    return bool(caso.area_asignada_id) and gestiona_departamento(user, caso.area_asignada_id)


def puede_atender(user, caso):
    """Informar avances, bloqueos, fecha estimada y la solución."""
    return es_operaciones(user) or caso.responsable_id == user.pk or gestiona_area(user, caso)


def es_tecnologia(caso):
    return bool(caso.area_asignada_id) and caso.area_asignada.nombre == getattr(settings, 'CASOS_DEPARTAMENTO_TECNICO', 'Tecnología')
