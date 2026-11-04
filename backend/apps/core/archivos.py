"""Entrega segura de los archivos que sube la gente (artes, documentos, evidencias)."""
from django.http import FileResponse

EN_LINEA = {'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'application/pdf'}


def entregar(f, nombre, tipo):
    """Solo se muestran en el navegador imágenes comunes y PDF; lo demás (SVG, HTML…) se descarga.
    Con «sandbox», aunque un archivo traiga código, el navegador no lo ejecuta con la sesión de nadie."""
    tipo = (tipo or '').lower().split(';')[0].strip()
    r = FileResponse(f, as_attachment=tipo not in EN_LINEA, filename=nombre,
                     content_type=tipo if tipo in EN_LINEA else 'application/octet-stream')
    r['Content-Security-Policy'] = "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"
    r['X-Content-Type-Options'] = 'nosniff'
    return r

