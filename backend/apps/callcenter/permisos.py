from django.contrib.auth.models import User

from apps.desempeno.permisos import es_administrador, puesto_de, subordinados

GRUPO_AGENTE = 'Agente Call Center'
DEPARTAMENTO = 'Call Center'


def es_agente(user):
    """Agente de call center: entra a su pantalla propia y se evalúa aparte del resto del equipo."""
    return bool(user and user.is_authenticated) and user.groups.filter(name=GRUPO_AGENTE).exists()


def agentes():
    return User.objects.filter(is_active=True, groups__name=GRUPO_AGENTE).distinct()


def gestiona_call_center(user):
    """Crea y edita campañas: la dirección, quien trabaja en el departamento de Call Center sin ser agente
    (gerente, supervisor de calidad) y cualquiera que supervise a un agente."""
    if not (user and user.is_authenticated):
        return False
    if es_administrador(user):
        return True
    if es_agente(user):
        return False
    puesto = puesto_de(user)
    if puesto and puesto.departamento_id and puesto.departamento.nombre == DEPARTAMENTO:
        return True
    return subordinados(user).filter(groups__name=GRUPO_AGENTE).exists()
