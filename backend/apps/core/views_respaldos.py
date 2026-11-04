"""Administración → Respaldos: la Dirección descarga las copias cifradas que deja servidor/respaldo.sh cada noche."""
import re
from datetime import datetime

from django.conf import settings
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.desempeno.permisos import TienePermiso

NOMBRE = re.compile(r'^(base|archivos|env)_(\d{4}-\d{2}-\d{2})_(\d{4})[\w.]*\.enc$')
TIPOS = {'base': 'Base de datos', 'archivos': 'Archivos privados', 'env': 'Configuración (.env)'}


def lista():
    carpeta = settings.RESPALDOS_DIR
    if not carpeta.is_dir():
        return []
    salida = []
    for f in carpeta.iterdir():
        m = NOMBRE.match(f.name)
        if f.is_file() and m:
            salida.append({'nombre': f.name, 'tipo': TIPOS[m.group(1)], 'fecha': m.group(2), 'tamano': f.stat().st_size,
                           'hora': f'{m.group(3)[:2]}:{m.group(3)[2:]}'})
    return sorted(salida, key=lambda x: (x['fecha'], x['hora'], x['nombre']), reverse=True)


@api_view(['GET'])
@permission_classes([TienePermiso.de('direccion')])
def respaldos_view(request):
    datos = lista()
    ultimo = datos[0]['fecha'] if datos else None
    atrasado = ultimo is None or (timezone.localdate() - datetime.strptime(ultimo, '%Y-%m-%d').date()).days > 1
    return Response({'respaldos': datos, 'ultimo': ultimo, 'atrasado': atrasado})


@api_view(['GET'])
@permission_classes([TienePermiso.de('direccion')])
def descargar_view(request, nombre):
    if not NOMBRE.match(nombre):
        raise Http404
    ruta = settings.RESPALDOS_DIR / nombre
    if not ruta.is_file():
        raise Http404
    from apps.talento.auditoria import auditar
    auditar('Descargó un respaldo', nombre)
    return FileResponse(open(ruta, 'rb'), as_attachment=True, filename=nombre, content_type='application/octet-stream')


def recordar_semanal(hoy=None):
    """Cada lunes, aviso a la Dirección para que descargue la copia de la semana (o alerta si no hay respaldos recientes)."""
    hoy = hoy or timezone.localdate()
    if hoy.weekday() != 0:
        return 0
    from apps.core.permisos import con_permiso
    from apps.desempeno.servicios import avisar
    datos = lista()
    if datos and (hoy - datetime.strptime(datos[0]['fecha'], '%Y-%m-%d').date()).days <= 1:
        titulo, texto = 'Descarga el respaldo de la semana', 'Guárdalo fuera del servidor (un disco o tu nube). Está cifrado: se abre con la clave de respaldos.'
    else:
        titulo, texto = 'Los respaldos no se están haciendo', 'No hay un respaldo de anoche. Revisa la tarea programada de las 2:30 en Plesk.'
    avisar(list(con_permiso('direccion')), 'SEGURIDAD', titulo, texto, enlace='/respaldos')
    return 1
