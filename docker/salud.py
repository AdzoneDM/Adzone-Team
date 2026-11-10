"""Chequeo de salud del contenedor: la app responde la pantalla de entrada.

Se hace pasar por el proxy (Host del dominio + X-Forwarded-Proto: https) para que Django
no redirija a HTTPS ni rechace el Host.
"""
import os
import sys
import urllib.request

host = (os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost').replace(',', ' ').split() or ['localhost'])[0].lstrip('.')
req = urllib.request.Request('http://127.0.0.1:8000/', headers={'Host': host, 'X-Forwarded-Proto': 'https'})
try:
    with urllib.request.urlopen(req, timeout=4) as r:
        sys.exit(0 if r.status < 500 else 1)
except Exception:
    sys.exit(1)
