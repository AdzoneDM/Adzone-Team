import os

from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from .models import DocumentoCompartido

MAX_ARCHIVO = 25 * 1024 * 1024
EXT_IMAGEN = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
EXT_DOCUMENTO = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv', '.zip', '.odt', '.ods')


def revisar_archivo(archivo):
    """Documento o imagen de hasta 25 MB (devuelve si es imagen). Ejecutables y otros tipos se rechazan."""
    ext = os.path.splitext(archivo.name)[1].lower()
    if ext not in EXT_IMAGEN + EXT_DOCUMENTO:
        raise ValidationError({'archivo': ['Solo se pueden compartir imágenes y documentos (PDF, Word, Excel, PowerPoint, texto, CSV o ZIP).']})
    if archivo.size > MAX_ARCHIVO:
        raise ValidationError({'archivo': ['El archivo pesa más de 25 MB.']})
    es_imagen = ext in EXT_IMAGEN
    if es_imagen:
        from PIL import Image
        try:
            Image.open(archivo).verify()
        except Exception:  # noqa: BLE001
            raise ValidationError({'archivo': ['Ese archivo no es una imagen válida.']})
        finally:
            archivo.seek(0)
    return es_imagen


def visibles_para(usuario):
    """Lo que la persona puede ver: lo que subió, lo que le enviaron a ella y lo enviado a su área (el área de su puesto)."""
    depto = getattr(getattr(getattr(usuario, 'perfil', None), 'puesto_trabajo', None), 'departamento_id', None)
    filtro = Q(subido_por=usuario) | Q(destinatarios=usuario)
    if depto:
        filtro |= Q(areas=depto)
    return DocumentoCompartido.objects.filter(filtro).distinct()


def personas_que_reciben(doc):
    """Las personas activas a las que llega el documento: las elegidas y todo el personal de las áreas elegidas."""
    ids = set(doc.destinatarios.values_list('pk', flat=True))
    areas = list(doc.areas.values_list('pk', flat=True))
    if areas:
        ids |= set(User.objects.filter(is_active=True, perfil__puesto_trabajo__departamento__in=areas).values_list('pk', flat=True))
    ids.discard(doc.subido_por_id)
    return list(User.objects.filter(pk__in=ids, is_active=True))


def avisar_envio(doc, personas, por):
    from apps.desempeno.servicios import avisar, nombre
    avisar(personas, 'DOCUMENTO', f'{nombre(por)} te compartió un documento', f'«{doc.titulo}»' + (f' · {doc.nota}' if doc.nota else ''),
           enlace=f'/documentos?id={doc.pk}', excepto=por)
