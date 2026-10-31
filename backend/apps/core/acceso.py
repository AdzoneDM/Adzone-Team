"""Clave general del equipo: el primer paso de la entrada, compartido por todo ADZONE."""
from django.contrib.auth.hashers import check_password, make_password

from .models import AccesoEquipo

SESION_EQUIPO = 'equipo_ok'


def clave_configurada():
    return AccesoEquipo.objects.exclude(clave='').exists()


def fijar_clave(texto):
    acceso = AccesoEquipo.objects.first() or AccesoEquipo()
    acceso.clave = make_password(texto)
    acceso.save()


def clave_valida(texto):
    acceso = AccesoEquipo.objects.exclude(clave='').first()
    return bool(acceso and texto and check_password(texto, acceso.clave))


def equipo_abierto(request):
    return bool(request.session.get(SESION_EQUIPO)) or request.user.is_authenticated
