"""Compresión de las respuestas de la API (JSON). Una lista de personas o de puestos pasa de cientos de KB a decenas."""
from django.middleware.gzip import GZipMiddleware


class CompresionDeLaApi(GZipMiddleware):
    """Solo JSON y texto de /api/: nunca archivos (fotos, PDF) ni las respuestas en flujo, que no ganan nada y gastan procesador."""

    def process_response(self, request, response):
        tipo = response.get('Content-Type', '')
        if not request.path.startswith('/api/') or response.streaming or not tipo.startswith(('application/json', 'text/')):
            return response
        return super().process_response(request, response)
