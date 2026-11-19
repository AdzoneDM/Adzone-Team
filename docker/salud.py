"""Chequeo de salud del contenedor.

web (por defecto): la app responde la pantalla de entrada. Se hace pasar por el proxy (Host del dominio +
X-Forwarded-Proto: https) para que Django no redirija a HTTPS ni rechace el Host.
tareas: supercronic sigue siendo el proceso principal y la base de datos acepta conexiones.
"""
import os
import socket
import sys
import urllib.request


def web():
    host = (os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost').replace(',', ' ').split() or ['localhost'])[0].lstrip('.')
    req = urllib.request.Request('http://127.0.0.1:8000/', headers={'Host': host, 'X-Forwarded-Proto': 'https'})
    with urllib.request.urlopen(req, timeout=4) as r:
        return r.status < 500


def tareas():
    with open('/proc/1/comm', encoding='utf-8') as f:
        if f.read().strip() != 'supercronic':
            return False
    if os.environ.get('DB_ENGINE', 'sqlite') == 'sqlite':
        return True
    with socket.create_connection((os.environ.get('DB_HOST', 'localhost'), int(os.environ.get('DB_PORT', '3306'))), timeout=4):
        return True


try:
    sys.exit(0 if (tareas() if sys.argv[1:] == ['tareas'] else web()) else 1)
except Exception:
    sys.exit(1)
