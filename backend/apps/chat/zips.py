"""Validación de archivos ZIP del chat: que sean un ZIP de verdad (no solo la extensión), que no sean una bomba de compresión, que no
traigan ejecutables de Windows ni contraseña (no se podrían revisar) y que el antivirus los dé por limpios. Nunca se extrae nada."""
import zipfile

from django.conf import settings
from rest_framework.exceptions import ValidationError

from . import antivirus

FIRMAS = (b'PK\x03\x04', b'PK\x05\x06')            # ZIP normal y ZIP vacío
MAX_ELEMENTOS = 5000                                # archivos dentro del ZIP
MAX_DESCOMPRIMIDO = 4 * 1024 ** 3                   # 4 GB ya descomprimido
MAX_RAZON = 200                                     # descomprimido / comprimido: más es típico de una bomba ZIP
EJECUTABLES = ('.exe', '.scr', '.com', '.bat', '.cmd', '.msi', '.vbs', '.vbe', '.lnk', '.pif', '.cpl', '.hta', '.dll', '.jar')


def _error(texto):
    return ValidationError({'archivo': [texto]})


def revisar_zip(archivo):
    """Valida un ZIP y devuelve {'items': n, 'escaneo': LIMPIO|NO_REVISADO}. Lanza ValidationError con un mensaje claro si no se acepta."""
    tope = settings.CHAT_ZIP_MAX_MB
    if archivo.size > tope * 1024 * 1024:
        raise _error(f'El ZIP pesa más de {tope} MB. Para uno más grande, súbelo a Drive y pega el enlace.')
    archivo.seek(0)
    if archivo.read(4) not in FIRMAS:
        archivo.seek(0)
        raise _error('Ese archivo no es un ZIP válido (aunque termine en .zip).')
    archivo.seek(0)
    try:
        with zipfile.ZipFile(archivo) as z:
            infos = z.infolist()
    except (zipfile.BadZipFile, OSError, EOFError, ValueError, NotImplementedError):
        archivo.seek(0)
        raise _error('El ZIP está dañado o incompleto: vuelve a comprimirlo y envíalo otra vez.')
    archivo.seek(0)
    if len(infos) > MAX_ELEMENTOS:
        raise _error(f'El ZIP trae demasiados archivos ({len(infos)}; máximo {MAX_ELEMENTOS}). Divídelo en varios.')
    descomprimido = sum(i.file_size for i in infos)
    comprimido = max(1, sum(i.compress_size for i in infos))
    if descomprimido > MAX_DESCOMPRIMIDO or (descomprimido > 50 * 1024 * 1024 and descomprimido / comprimido > MAX_RAZON):
        raise _error('El ZIP no se acepta: su contenido descomprimido es desproporcionado (posible bomba de compresión).')
    if any(i.flag_bits & 0x1 for i in infos):
        raise _error('El ZIP tiene contraseña: no se puede revisar. Envíalo sin contraseña o compártelo por otro medio.')
    if settings.CHAT_ZIP_BLOQUEAR_EJECUTABLES:
        malos = sorted({i.filename.rsplit('.', 1)[-1].lower() for i in infos if '.' in i.filename and ('.' + i.filename.rsplit('.', 1)[-1].lower()) in EJECUTABLES})
        if malos:
            raise _error(f'El ZIP trae archivos ejecutables (.{", .".join(malos)}) y no se permite por seguridad.')
    items = sum(1 for i in infos if not i.is_dir())
    if settings.CHAT_ANTIVIRUS == 'omitir':
        return {'items': items, 'escaneo': antivirus.NO_REVISADO}
    estado, detalle = antivirus.escanear(archivo)
    if estado == antivirus.INFECTADO:
        raise _error(f'El antivirus detectó una amenaza en el ZIP ({detalle}). No se envió.')
    if estado == antivirus.NO_DISPONIBLE:
        raise _error('No se pudo revisar el ZIP con el antivirus en este momento. Inténtalo de nuevo en unos minutos.')
    return {'items': items, 'escaneo': antivirus.LIMPIO}
