"""Subida por partes de archivos grandes (ZIP y videos de cientos de MB) para adjuntarlos a las tareas.

Por qué: el nginx de Plesk corta cada petición en 64 MB (`client_max_body_size`, no se puede cambiar). El navegador corta el archivo en
partes de SUBIDA_PARTE_BYTES (8 MB) y manda cada una en su propia petición:

    POST   /api/subidas/                        {nombre, tamano}  → {id, tamano_parte, partes}
    PUT    /api/subidas/<id>/partes/<n>/        cuerpo crudo (application/octet-stream) con la parte n (en orden; repetir una ya recibida no hace nada)
    POST   /api/subidas/<id>/completar/         junta y revisa (contenido, ZIP como en el chat con antivirus) → {estado: COMPLETA}
    GET    /api/subidas/<id>/                   cuánto lleva (para retomar)
    DELETE /api/subidas/<id>/                   cancela y borra lo recibido

Las partes se escriben en streaming (de a 1 MB, nunca el archivo entero en memoria) en MEDIA_ROOT/subidas_tmp/<id>/datos: es el único lugar con
escritura del contenedor y está en el mismo disco que los adjuntos, así que al adjuntarlo el archivo se MUEVE (no se copia). Solo el dueño usa
su subida, y una sola vez. Las que quedan a medias (o completas sin usar) se borran a las 24 h (`limpiar_vencidas`, comando diario).
"""
import math
import mimetypes
import os
import shutil
import uuid
import zipfile
from datetime import timedelta

from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .archivos import es_video, revisar_contenido
from .models import SubidaPorPartes

MB = 1024 * 1024
TROZO = MB                      # se lee y escribe de a 1 MB
MAX_ACTIVAS = 20                # subidas abiertas a la vez por persona
MARGEN_DISCO = 2 * 1024 * MB    # siempre quedan al menos 2 GB libres
CARPETA = 'subidas_tmp'


# ---------------------------------------------------------------------------
# Reglas (las mismas que los adjuntos de tareas; el tope de ZIP y video es el grande)
# ---------------------------------------------------------------------------
def _reglas():
    from apps.desempeno.serializers import EXTENSIONES_DOCUMENTO, FIRMAS_DOCUMENTO, EntregaSerializer
    return EntregaSerializer.EXTENSIONES, EXTENSIONES_DOCUMENTO, FIRMAS_DOCUMENTO


def tope_mb(nombre):
    """Máximo permitido para este archivo (MB): ZIP y videos, el de adjuntos grandes; documentos y fotos, el de siempre."""
    ext = os.path.splitext(nombre)[1].lower()
    _, documentos, _ = _reglas()
    if ext == '.zip':
        return settings.ADJUNTO_GRANDE_MAX_MB
    if es_video(nombre):
        return settings.EVIDENCIA_VIDEO_GRANDE_MAX_MB
    return settings.EVIDENCIA_DOC_MAX_MB if ext in documentos else settings.EVIDENCIA_MAX_MB


def _ruta_carpeta(subida_id):
    return os.path.join(settings.MEDIA_ROOT, CARPETA, str(subida_id))


def ruta_datos(subida):
    return os.path.join(_ruta_carpeta(subida.pk), 'datos')


def _borrar_archivos(subida_id):
    shutil.rmtree(_ruta_carpeta(subida_id), ignore_errors=True)


def _error(texto, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': texto}, status=codigo)


def _revisar_zip(archivo):
    """La misma revisión que un ZIP del chat (apps/chat/zips.py), sin su tope de 50 MB: ZIP de verdad, sin bomba de compresión, sin contraseña,
    sin ejecutables y limpio según el antivirus (con la misma política `CHAT_ANTIVIRUS`). Devuelve el motivo del rechazo o None."""
    from apps.chat import antivirus
    from apps.chat.zips import EJECUTABLES, FIRMAS, MAX_DESCOMPRIMIDO, MAX_ELEMENTOS, MAX_RAZON
    archivo.seek(0)
    if archivo.read(4) not in FIRMAS:
        return 'no es un ZIP válido (aunque termine en .zip)'
    archivo.seek(0)
    try:
        with zipfile.ZipFile(archivo) as z:
            infos = z.infolist()
    except (zipfile.BadZipFile, OSError, EOFError, ValueError, NotImplementedError):
        return 'el ZIP está dañado o incompleto: vuelve a comprimirlo y súbelo otra vez'
    finally:
        archivo.seek(0)
    if len(infos) > MAX_ELEMENTOS:
        return f'el ZIP trae demasiados archivos ({len(infos)}; máximo {MAX_ELEMENTOS}). Divídelo en varios'
    descomprimido = sum(i.file_size for i in infos)
    comprimido = max(1, sum(i.compress_size for i in infos))
    if descomprimido > MAX_DESCOMPRIMIDO or (descomprimido > 50 * MB and descomprimido / comprimido > MAX_RAZON):
        return 'su contenido descomprimido es desproporcionado (posible bomba de compresión)'
    if any(i.flag_bits & 0x1 for i in infos):
        return 'el ZIP tiene contraseña y no se puede revisar. Súbelo sin contraseña'
    if settings.CHAT_ZIP_BLOQUEAR_EJECUTABLES:
        malos = sorted({i.filename.rsplit('.', 1)[-1].lower() for i in infos
                        if '.' in i.filename and ('.' + i.filename.rsplit('.', 1)[-1].lower()) in EJECUTABLES})
        if malos:
            return f'el ZIP trae archivos ejecutables (.{", .".join(malos)}) y no se permite por seguridad'
    if settings.CHAT_ANTIVIRUS == 'omitir':
        return None
    estado, detalle = antivirus.escanear(archivo)
    if estado == antivirus.INFECTADO:
        return f'el antivirus detectó una amenaza en el ZIP ({detalle})'
    if estado == antivirus.NO_DISPONIBLE:
        return 'no se pudo revisar el ZIP con el antivirus en este momento. Inténtalo de nuevo en unos minutos'
    return None


def revisar_archivo(ruta, nombre):
    """Revisa el archivo ya juntado. Devuelve el motivo del rechazo o None si está bien."""
    _, _, firmas = _reglas()
    ext = os.path.splitext(nombre)[1].lower()
    with open(ruta, 'rb') as f:
        problema = revisar_contenido(_ConNombre(f, nombre))
        if problema:
            return problema
        if ext == '.zip':
            return _revisar_zip(f)
        if ext in firmas:
            cabeza = f.read(8)
            if not any(cabeza.startswith(x) for x in firmas[ext]):
                return f'no es un archivo {ext[1:].upper()} válido (aunque tenga ese nombre)'
    return None


class _ConNombre:
    """Un archivo abierto que dice llamarse como el original (revisar_contenido decide por la extensión)."""
    def __init__(self, f, nombre):
        self._f, self.name = f, nombre

    def __getattr__(self, atributo):
        return getattr(self._f, atributo)


# ---------------------------------------------------------------------------
# Para quien adjunta (tareas): convierte ids de subidas completas en archivos listos para un FileField
# ---------------------------------------------------------------------------
class ArchivoEnsamblado(File):
    """El archivo juntado de una subida. Tiene `temporary_file_path`: el almacenamiento en disco lo MUEVE a su lugar definitivo (sin copiar)."""

    def __init__(self, subida):
        self.subida = subida
        self._ruta = ruta_datos(subida)
        super().__init__(open(self._ruta, 'rb'), name=subida.nombre)
        self.content_type = mimetypes.guess_type(subida.nombre)[0] or ''

    @property
    def size(self):
        return self.subida.tamano

    def temporary_file_path(self):
        return self._ruta


def ids_de_subidas(request):
    """Los ids de subidas que trae una petición (formulario: varios campos «subidas»; JSON: una lista)."""
    datos = request.data
    ids = datos.getlist('subidas') if hasattr(datos, 'getlist') else (datos.get('subidas') or [])
    if isinstance(ids, str):
        ids = [ids]
    return [str(i).strip() for i in ids if str(i).strip()]


def tomar(usuario, ids):
    """Las subidas completas (y sin usar) de esta persona, como archivos. Llamar dentro de una transacción: las bloquea para que no se usen
    dos veces. Lanza ValidationError si alguna no existe, es de otra persona o no terminó de subir."""
    ids = list(dict.fromkeys(ids))
    if not ids:
        return []
    if len(ids) > settings.EVIDENCIA_MAX_ARCHIVOS:
        raise ValidationError({'subidas': [f'Como máximo {settings.EVIDENCIA_MAX_ARCHIVOS} archivos cada vez.']})
    try:
        ids = [uuid.UUID(i) for i in ids]
    except ValueError:
        raise ValidationError({'subidas': ['Identificador de archivo no válido.']})
    encontradas = {s.pk: s for s in SubidaPorPartes.objects.select_for_update().filter(pk__in=ids, dueno=usuario)}
    archivos = []
    for i in ids:
        s = encontradas.get(i)
        if s is None:
            raise ValidationError({'subidas': ['Uno de los archivos no existe o no lo subiste tú. Vuelve a adjuntarlo.']})
        if s.estado == SubidaPorPartes.USADA:
            raise ValidationError({'subidas': [f'«{s.nombre}» ya se adjuntó. Vuelve a elegirlo para subirlo otra vez.']})
        if s.estado != SubidaPorPartes.COMPLETA or not os.path.isfile(ruta_datos(s)):
            raise ValidationError({'subidas': [f'«{s.nombre}» no terminó de subir. Vuelve a adjuntarlo.']})
        archivos.append(ArchivoEnsamblado(s))
    return archivos


def marcar_usadas(archivos):
    """Tras crear los adjuntos: la subida queda usada y su carpeta temporal se borra (el archivo ya se movió a su lugar)."""
    for a in archivos:
        a.close()
        SubidaPorPartes.objects.filter(pk=a.subida.pk).update(estado=SubidaPorPartes.USADA, actualizada=timezone.now())
        transaction.on_commit(lambda pk=a.subida.pk: _borrar_archivos(pk))


def limpiar_vencidas(horas=24):
    """Borra las subidas de hace más de `horas` (a medias, rechazadas o completas que nunca se adjuntaron) y sus temporales.
    También carpetas huérfanas en subidas_tmp/. Devuelve cuántas se borraron."""
    limite = timezone.now() - timedelta(hours=horas)
    viejas = list(SubidaPorPartes.objects.filter(creada__lt=limite).values_list('pk', flat=True))
    for pk in viejas:
        _borrar_archivos(pk)
    SubidaPorPartes.objects.filter(pk__in=viejas).delete()
    raiz = os.path.join(settings.MEDIA_ROOT, CARPETA)
    if os.path.isdir(raiz):
        vigentes = {str(pk) for pk in SubidaPorPartes.objects.values_list('pk', flat=True)}
        for nombre in os.listdir(raiz):
            ruta = os.path.join(raiz, nombre)
            if nombre not in vigentes and os.path.getmtime(ruta) < limite.timestamp():
                shutil.rmtree(ruta, ignore_errors=True)
    return len(viejas)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
def _estado(s):
    return {'id': str(s.pk), 'nombre': s.nombre, 'tamano': s.tamano, 'tamano_parte': s.tamano_parte,
            'partes': max(1, math.ceil(s.tamano / s.tamano_parte)), 'recibidos': s.recibidos, 'estado': s.estado}


def _propia(request, pk, bloquear=False):
    qs = SubidaPorPartes.objects.select_for_update() if bloquear else SubidaPorPartes.objects
    return qs.filter(pk=pk, dueno=request.user).first()   # la de otra persona: como si no existiera


@api_view(['POST'])
def iniciar_view(request):
    nombre = os.path.basename(str(request.data.get('nombre') or '').replace('\\', '/')).strip()[:255]
    try:
        tamano = int(request.data.get('tamano'))
    except (TypeError, ValueError):
        return _error('Falta el tamaño del archivo.')
    extensiones, _, _ = _reglas()
    ext = os.path.splitext(nombre)[1].lower()
    if not nombre or ext not in extensiones:
        return _error(f'«{nombre or "archivo"}»: solo se aceptan fotos, videos, PDF, documentos (Word, Excel, PowerPoint, CSV, texto) o ZIP.')
    if tamano <= 0:
        return _error(f'«{nombre}» está vacío.')
    tope = tope_mb(nombre)
    if tamano > tope * MB:
        return _error(f'«{nombre}» pesa más de lo permitido. Máximo {tope} MB.')
    if SubidaPorPartes.objects.filter(dueno=request.user, estado=SubidaPorPartes.SUBIENDO).count() >= MAX_ACTIVAS:
        return _error('Tienes demasiadas subidas a medias. Espera a que terminen o vuelve a intentarlo más tarde.', status.HTTP_429_TOO_MANY_REQUESTS)
    os.makedirs(os.path.join(settings.MEDIA_ROOT, CARPETA), exist_ok=True)
    if shutil.disk_usage(os.path.join(settings.MEDIA_ROOT, CARPETA)).free < tamano + MARGEN_DISCO:
        return _error('El servidor no tiene espacio suficiente para este archivo ahora. Avísale a Tecnología.', status.HTTP_507_INSUFFICIENT_STORAGE)
    s = SubidaPorPartes.objects.create(dueno=request.user, nombre=nombre, tamano=tamano, tamano_parte=settings.SUBIDA_PARTE_BYTES,
                                       tipo=(mimetypes.guess_type(nombre)[0] or '')[:100])
    os.makedirs(_ruta_carpeta(s.pk), exist_ok=True)
    open(ruta_datos(s), 'wb').close()
    return Response(_estado(s), status=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
def subida_view(request, pk):
    s = _propia(request, pk)
    if s is None:
        return _error('No se encontró esa subida.', status.HTTP_404_NOT_FOUND)
    if request.method == 'DELETE':
        if s.estado == SubidaPorPartes.USADA:
            return _error('Ese archivo ya está adjunto.', status.HTTP_409_CONFLICT)
        _borrar_archivos(s.pk)
        s.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(_estado(s))


@api_view(['PUT'])
def parte_view(request, pk, indice):
    """Recibe la parte `indice` (desde 0) como cuerpo crudo y la escribe en su lugar, de a 1 MB."""
    with transaction.atomic():
        s = _propia(request, pk, bloquear=True)
        if s is None:
            return _error('No se encontró esa subida.', status.HTTP_404_NOT_FOUND)
        if s.estado != SubidaPorPartes.SUBIENDO:
            return _error('Esta subida ya terminó.', status.HTTP_409_CONFLICT)
        partes = max(1, math.ceil(s.tamano / s.tamano_parte))
        if indice >= partes:
            return _error('Parte fuera de rango.')
        siguiente = s.recibidos // s.tamano_parte if s.recibidos < s.tamano else partes
        if indice < siguiente:   # ya la teníamos (un reintento): no se escribe de nuevo
            return Response(_estado(s))
        if indice > siguiente:
            return _error(f'Falta la parte {siguiente + 1}: las partes van en orden.', status.HTTP_409_CONFLICT)
        esperado = min(s.tamano_parte, s.tamano - s.recibidos)
        try:
            largo = int(request.META.get('CONTENT_LENGTH') or 0)
        except ValueError:
            largo = 0
        if largo != esperado:
            return _error(f'La parte debe traer {esperado} bytes y trae {largo}.')
        ruta = ruta_datos(s)
        if not os.path.isfile(ruta):
            return _error('Se perdió lo recibido de esta subida. Vuelve a adjuntar el archivo.', status.HTTP_409_CONFLICT)
        escritos = 0
        with open(ruta, 'r+b') as f:
            f.seek(s.recibidos)
            while escritos < esperado:
                trozo = request._request.read(min(TROZO, esperado - escritos))
                if not trozo:
                    break
                f.write(trozo)
                escritos += len(trozo)
            if escritos != esperado:   # la conexión se cortó: se descarta lo escrito a medias
                f.truncate(s.recibidos)
                return _error('La parte llegó incompleta. Vuelve a intentarlo.')
            f.truncate()
        s.recibidos += escritos
        s.save(update_fields=['recibidos', 'actualizada'])
    return Response(_estado(s))


@api_view(['POST'])
def completar_view(request, pk):
    """Junta (ya está junto: las partes se escribieron en su lugar), verifica el tamaño total y revisa el contenido."""
    with transaction.atomic():
        s = _propia(request, pk, bloquear=True)
        if s is None:
            return _error('No se encontró esa subida.', status.HTTP_404_NOT_FOUND)
        if s.estado == SubidaPorPartes.COMPLETA:
            return Response(_estado(s))
        if s.estado != SubidaPorPartes.SUBIENDO:
            return _error('Esta subida ya no se puede completar.', status.HTTP_409_CONFLICT)
        ruta = ruta_datos(s)
        real = os.path.getsize(ruta) if os.path.isfile(ruta) else -1
        if s.recibidos != s.tamano or real != s.tamano:
            return _error(f'Faltan partes de «{s.nombre}»: llegaron {max(real, 0)} de {s.tamano} bytes.')
        problema = revisar_archivo(ruta, s.nombre)
        if problema:
            s.estado = SubidaPorPartes.RECHAZADA
            s.save(update_fields=['estado', 'actualizada'])
            transaction.on_commit(lambda: _borrar_archivos(s.pk))
            return _error(f'«{s.nombre}» {problema}.')
        s.estado = SubidaPorPartes.COMPLETA
        s.save(update_fields=['estado', 'actualizada'])
    return Response(_estado(s))
