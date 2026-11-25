"""Manejador de errores de la API: además de la respuesta de siempre, deja en la bitácora los accesos denegados (403)
de personas con sesión (como mucho uno por persona y ruta cada 10 minutos, para no llenarla)."""
from django.core.cache import cache
from rest_framework.views import exception_handler


def manejar(exc, context):
    respuesta = exception_handler(exc, context)
    try:
        request = context.get('request')
        user = getattr(request, 'user', None)
        if respuesta is not None and respuesta.status_code == 403 and user is not None and user.is_authenticated:
            clave = f'denegado:{user.pk}:{request.method}:{request.path}'[:200]
            if cache.add(clave, 1, 600):
                from .accesos import registrar
                registrar('DENEGADO', request, user, motivo=f'{request.method} {str(getattr(exc, "detail", ""))[:180]}')
    except Exception:  # la bitácora nunca rompe la respuesta
        pass
    return respuesta
