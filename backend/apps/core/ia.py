"""
Cliente de la API de Claude (Anthropic) con el SDK oficial `anthropic`. La clave va solo en el entorno del servidor
(ANTHROPIC_API_KEY). Sin clave, o si la API falla, `preguntar` devuelve None y cada función usa su versión sin IA.
"""
import logging

from django.conf import settings

log = logging.getLogger(__name__)
BETA_FALLBACK = 'server-side-fallback-2026-07-01'   # si el modelo rechaza una solicitud, la API la reintenta con otro modelo


def activa():
    return bool(getattr(settings, 'ANTHROPIC_API_KEY', ''))


def cliente():
    import anthropic
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=2, timeout=120.0)


def preguntar(sistema, mensaje, max_tokens=1200, temperatura=None, esfuerzo='low'):
    """Texto de la respuesta, o None si no hay clave o la llamada falla. «temperatura» se acepta por compatibilidad,
    pero no se envía (los modelos actuales la rechazan)."""
    if not activa():
        return None
    import anthropic
    try:
        r = cliente().beta.messages.create(
            model=settings.IA_MODELO, max_tokens=max(max_tokens, 2000), system=sistema, output_config={'effort': esfuerzo},
            betas=[BETA_FALLBACK], fallbacks='default', messages=[{'role': 'user', 'content': mensaje}])
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        log.warning('La API de Claude no respondió: %s', e)
        return None
    if r.stop_reason not in ('end_turn', 'stop_sequence'):
        return None
    return '\n'.join(b.text for b in r.content if b.type == 'text').strip() or None
