"""IP real del cliente detrás del proxy de Plesk (la misma regla que el límite de intentos: NUM_PROXIES)."""
import ipaddress

from django.conf import settings


def ip_real(request):
    meta = getattr(request, 'META', {})
    saltos = settings.REST_FRAMEWORK.get('NUM_PROXIES')
    xff = meta.get('HTTP_X_FORWARDED_FOR', '')
    if saltos and xff:
        partes = [p.strip() for p in xff.split(',') if p.strip()]
        if partes:
            return partes[-min(saltos, len(partes))]
    return meta.get('REMOTE_ADDR') or None


def en_redes(ip, redes):
    """¿La IP está en alguna de las redes («190.1.2.3, 10.0.0.0/24»)?"""
    try:
        dir_ip = ipaddress.ip_address(ip)
    except (TypeError, ValueError):
        return False
    for r in str(redes or '').replace(';', ',').split(','):
        r = r.strip()
        if not r:
            continue
        try:
            if dir_ip in ipaddress.ip_network(r, strict=False):
                return True
        except ValueError:
            continue
    return False
