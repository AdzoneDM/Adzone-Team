"""Revisión antivirus de archivos comprimidos con ClamAV (el demonio `clamd` del servidor), sin extraer ni ejecutar nada.

Se habla con clamd por su socket usando el protocolo INSTREAM: el archivo se envía por trozos y clamd responde `OK` o el nombre de la amenaza.
Política configurable (`CHAT_ANTIVIRUS`): «exigir» (si no se puede revisar, el archivo se rechaza) u «omitir» (solo desarrollo)."""
import socket
import struct

from django.conf import settings

TROZO = 64 * 1024
LIMPIO, INFECTADO, NO_DISPONIBLE, NO_REVISADO = 'LIMPIO', 'INFECTADO', 'NO_DISPONIBLE', 'NO_REVISADO'


def _conectar():
    ruta = getattr(settings, 'CLAMAV_SOCKET', '')
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(getattr(settings, 'CLAMAV_TIMEOUT', 60))
    s.connect(ruta)
    return s


def escanear(archivo):
    """Devuelve (estado, detalle): LIMPIO, INFECTADO (con el nombre de la amenaza) o NO_DISPONIBLE (clamd no respondió)."""
    try:
        s = _conectar()
    except OSError as e:
        return NO_DISPONIBLE, f'sin conexión con el antivirus ({e.__class__.__name__})'
    try:
        s.sendall(b'zINSTREAM\0')
        archivo.seek(0)
        while True:
            trozo = archivo.read(TROZO)
            if not trozo:
                break
            s.sendall(struct.pack('!I', len(trozo)) + trozo)
        s.sendall(struct.pack('!I', 0))
        respuesta = b''
        while not respuesta.endswith(b'\0') and len(respuesta) < 4096:
            parte = s.recv(1024)
            if not parte:
                break
            respuesta += parte
    except OSError as e:
        return NO_DISPONIBLE, f'falló la revisión ({e.__class__.__name__})'
    finally:
        s.close()
        archivo.seek(0)
    texto = respuesta.rstrip(b'\0').decode('utf-8', 'replace').strip()
    if texto.endswith('OK'):
        return LIMPIO, ''
    if texto.endswith('FOUND'):
        return INFECTADO, texto.split(':', 1)[-1].replace('FOUND', '').strip()
    return NO_DISPONIBLE, texto or 'respuesta vacía del antivirus'
