"""Entrega segura de los archivos que sube la gente (artes, documentos, evidencias, videos)."""
import os
import re

from django.http import FileResponse, HttpResponse, StreamingHttpResponse

EN_LINEA = {'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'application/pdf'}
# Videos que el navegador reproduce dentro de la página; los demás formatos (AVI, MKV, 3GP…) se descargan
VIDEO_EN_LINEA = {'video/mp4', 'video/webm', 'video/quicktime', 'video/x-m4v', 'video/ogg'}
EXTENSIONES_VIDEO = ('.mp4', '.mov', '.m4v', '.webm', '.avi', '.mkv', '.3gp', '.mpg', '.mpeg')
CSP = "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"
_RANGO = re.compile(r'bytes=(\d*)-(\d*)$')


def es_video(nombre='', tipo=''):
    return (tipo or '').lower().startswith('video/') or (nombre or '').lower().endswith(EXTENSIONES_VIDEO)


def _trozos(f, inicio, fin, tam=1024 * 512):
    f.seek(inicio)
    restante = fin - inicio + 1
    try:
        while restante > 0:
            dato = f.read(min(tam, restante))
            if not dato:
                break
            restante -= len(dato)
            yield dato
    finally:
        f.close()


def _video(f, nombre, tipo, request):
    """Un video se entrega por tramos (cabecera Range): así el reproductor avanza, retrocede y empieza sin bajar todo el archivo
    (Safari y los celulares lo exigen)."""
    total = os.fstat(f.fileno()).st_size if hasattr(f, 'fileno') else f.size
    cabecera = (request.headers.get('Range') if request is not None else '') or ''
    m = _RANGO.match(cabecera.strip())
    if m and (m.group(1) or m.group(2)):
        if m.group(1):
            inicio = int(m.group(1))
            fin = min(int(m.group(2)) if m.group(2) else total - 1, total - 1)
        else:  # «bytes=-500»: los últimos 500
            inicio, fin = max(total - int(m.group(2)), 0), total - 1
        if inicio >= total or inicio > fin:
            f.close()
            r = HttpResponse(status=416)
            r['Content-Range'] = f'bytes */{total}'
            return r
        r = StreamingHttpResponse(_trozos(f, inicio, fin), status=206, content_type=tipo)
        r['Content-Range'] = f'bytes {inicio}-{fin}/{total}'
        r['Content-Length'] = str(fin - inicio + 1)
    else:
        r = StreamingHttpResponse(_trozos(f, 0, total - 1), content_type=tipo)
        r['Content-Length'] = str(total)
    r['Accept-Ranges'] = 'bytes'
    r['Content-Disposition'] = f'inline; filename="{os.path.basename(nombre)}"'
    r['Content-Security-Policy'] = CSP
    r['X-Content-Type-Options'] = 'nosniff'
    return r


def entregar(f, nombre, tipo, request=None):
    """Solo se muestran en el navegador imágenes comunes, PDF y videos reproducibles; lo demás (SVG, HTML…) se descarga.
    Con «sandbox», aunque un archivo traiga código, el navegador no lo ejecuta con la sesión de nadie."""
    tipo = (tipo or '').lower().split(';')[0].strip()
    if tipo in VIDEO_EN_LINEA and request is not None and request.query_params.get('descargar') != '1':
        return _video(f, nombre, tipo, request)
    r = FileResponse(f, as_attachment=tipo not in EN_LINEA, filename=nombre,
                     content_type=tipo if tipo in EN_LINEA else 'application/octet-stream')
    r['Content-Security-Policy'] = CSP
    r['X-Content-Type-Options'] = 'nosniff'
    return r
