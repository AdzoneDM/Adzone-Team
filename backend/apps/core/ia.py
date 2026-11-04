"""
Cliente mínimo de la API de Claude (Anthropic). La clave va solo en backend/.env (ANTHROPIC_API_KEY).
Sin clave, o si la API falla, devuelve None y cada función usa su versión sin IA (reglas y números).
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)
URL = 'https://api.anthropic.com/v1/messages'


def activa():
    return bool(getattr(settings, 'ANTHROPIC_API_KEY', ''))


def preguntar(sistema, mensaje, max_tokens=1200, temperatura=0.3):
    """Texto de la respuesta, o None si no hay clave o la llamada falla."""
    if not activa():
        return None
    cuerpo = json.dumps({
        'model': settings.IA_MODELO, 'max_tokens': max_tokens, 'temperature': temperatura, 'system': sistema,
        'messages': [{'role': 'user', 'content': mensaje}],
    }).encode()
    req = urllib.request.Request(URL, data=cuerpo, method='POST', headers={
        'x-api-key': settings.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            datos = json.loads(r.read())
        return ''.join(b.get('text', '') for b in datos.get('content', []) if b.get('type') == 'text').strip() or None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log.warning('La API de Claude no respondió: %s', e)
        return None
