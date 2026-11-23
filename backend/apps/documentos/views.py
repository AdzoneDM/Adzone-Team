import mimetypes
import os

from django.contrib.auth.models import User
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.models import Departamento
from . import servicios
from .models import DocumentoCompartido


def _valores(datos, clave):
    """Lo enviado en `clave`: lista repetida en un formulario (varias veces la misma clave), lista JSON o «1,2,3»."""
    if hasattr(datos, 'getlist'):
        lista = datos.getlist(clave)
        return lista[0] if len(lista) == 1 else lista
    return datos.get(clave)


def _ids(valor):
    if isinstance(valor, str):
        valor = [v for v in valor.split(',') if v.strip()]
    salida = []
    for v in valor or []:
        try:
            salida.append(int(v))
        except (TypeError, ValueError):
            continue
    return salida


def _nombre(u):
    return (u.get_full_name() or u.username) if u else 'Persona eliminada'


def _ficha(doc, usuario, personas_total=None):
    return {
        'id': doc.id, 'titulo': doc.titulo, 'nota': doc.nota, 'carpeta': doc.carpeta, 'nombre_archivo': doc.nombre_archivo,
        'tamano': doc.tamano, 'es_imagen': doc.es_imagen, 'creado': doc.creado,
        'subido_por': doc.subido_por_id, 'subido_por_nombre': _nombre(doc.subido_por),
        'mio': doc.subido_por_id == usuario.id,
        'nuevo': doc.subido_por_id != usuario.id and not any(v.pk == usuario.id for v in doc.vistos.all()),
        'destinatarios': [{'id': u.id, 'nombre': _nombre(u)} for u in doc.destinatarios.all()],
        'areas': [{'id': a.id, 'nombre': a.nombre} for a in doc.areas.all()],
        'personal': not doc.destinatarios.all() and not doc.areas.all(),
    }


def _lista(usuario, qs):
    return [_ficha(d, usuario) for d in qs.select_related('subido_por').prefetch_related('destinatarios', 'areas', 'vistos')]


def _elegir_destinos(doc, datos):
    """Aplica personas y áreas elegidas. Devuelve las personas que antes no lo recibían (para avisarles)."""
    antes = {u.pk for u in servicios.personas_que_reciben(doc)} if doc.pk else set()
    doc.destinatarios.set(User.objects.filter(pk__in=_ids(_valores(datos, 'destinatarios')), is_active=True).exclude(pk=doc.subido_por_id))
    doc.areas.set(Departamento.objects.filter(pk__in=_ids(_valores(datos, 'areas'))))
    return [u for u in servicios.personas_que_reciben(doc) if u.pk not in antes]


@api_view(['GET', 'POST'])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def documentos_view(request):
    """GET: ?vista=recibidos|enviados|todos (por defecto, todos) · ?carpeta= · ?q= . POST (formulario): sube y envía un documento."""
    u = request.user
    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if not archivo:
            raise ValidationError({'archivo': ['Elige el archivo que quieres subir.']})
        es_imagen = servicios.revisar_archivo(archivo)
        titulo = (request.data.get('titulo') or os.path.splitext(archivo.name)[0]).strip()[:150]
        doc = DocumentoCompartido.objects.create(
            titulo=titulo or archivo.name[:150], nota=(request.data.get('nota') or '').strip()[:300], carpeta=(request.data.get('carpeta') or '').strip()[:60],
            archivo=archivo, nombre_archivo=archivo.name[:150], tamano=archivo.size, es_imagen=es_imagen, subido_por=u)
        nuevos = _elegir_destinos(doc, request.data)
        servicios.avisar_envio(doc, nuevos, u)
        doc = DocumentoCompartido.objects.prefetch_related('destinatarios', 'areas', 'vistos').select_related('subido_por').get(pk=doc.pk)
        return Response(_ficha(doc, u), status=status.HTTP_201_CREATED)
    qs = servicios.visibles_para(u)
    vista = request.query_params.get('vista')
    if vista == 'recibidos':
        qs = qs.exclude(subido_por=u)
    elif vista == 'enviados':
        qs = qs.filter(subido_por=u)
    carpeta = (request.query_params.get('carpeta') or '').strip()
    if carpeta:
        qs = qs.filter(carpeta__iexact=carpeta)
    texto = (request.query_params.get('q') or '').strip()
    for palabra in texto.split():
        qs = qs.filter(Q(titulo__icontains=palabra) | Q(nombre_archivo__icontains=palabra) | Q(nota__icontains=palabra))
    todos = servicios.visibles_para(u)
    carpetas = sorted({c for c in todos.values_list('carpeta', flat=True) if c}, key=str.lower)
    return Response({'documentos': _lista(u, qs.distinct()), 'carpetas': carpetas,
                     'nuevos': sum(1 for d in todos.exclude(subido_por=u).exclude(vistos=u)),
                     'areas': [{'id': a.id, 'nombre': a.nombre} for a in Departamento.objects.order_by('nombre')]})


def _doc_visible(request, pk):
    doc = servicios.visibles_para(request.user).filter(pk=pk).first()
    if doc is None:
        raise Http404  # igual que si no existiera: no se revela un documento ajeno
    return doc


@api_view(['PATCH', 'DELETE'])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def documento_view(request, pk):
    """Solo quien lo subió lo cambia (título, nota, carpeta, con quién se comparte) o lo elimina."""
    doc = _doc_visible(request, pk)
    if doc.subido_por_id != request.user.id:
        return Response({'detail': 'Solo quien subió el documento puede cambiarlo o eliminarlo.'}, status=status.HTTP_403_FORBIDDEN)
    if request.method == 'DELETE':
        doc.archivo.delete(save=False)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    for campo, tope in (('titulo', 150), ('nota', 300), ('carpeta', 60)):
        if campo in request.data:
            valor = (request.data.get(campo) or '').strip()[:tope]
            if campo == 'titulo' and not valor:
                raise ValidationError({'titulo': ['El documento necesita un título.']})
            setattr(doc, campo, valor)
    doc.save()
    if 'destinatarios' in request.data or 'areas' in request.data:
        datos = {'destinatarios': _valores(request.data, 'destinatarios') if 'destinatarios' in request.data else [u.pk for u in doc.destinatarios.all()],
                 'areas': _valores(request.data, 'areas') if 'areas' in request.data else [a.pk for a in doc.areas.all()]}
        servicios.avisar_envio(doc, _elegir_destinos(doc, datos), request.user)
    doc = DocumentoCompartido.objects.prefetch_related('destinatarios', 'areas', 'vistos').select_related('subido_por').get(pk=doc.pk)
    return Response(_ficha(doc, request.user))


@api_view(['GET'])
def archivo_view(request, pk):
    """Ver (imagen o PDF) o descargar el archivo. Al abrirlo, el documento deja de ser «nuevo» para quien lo recibió."""
    doc = _doc_visible(request, pk)
    if doc.subido_por_id != request.user.id:
        doc.vistos.add(request.user)
    tipo = mimetypes.guess_type(doc.archivo.name)[0] or 'application/octet-stream'
    descargar = request.query_params.get('descargar') == '1' or not (doc.es_imagen or tipo == 'application/pdf')
    resp = FileResponse(doc.archivo.open('rb'), filename=doc.nombre_archivo or os.path.basename(doc.archivo.name), content_type=tipo, as_attachment=descargar)
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp


@api_view(['GET'])
def resumen_view(request):
    """Liviano: cuántos documentos nuevos tiene la persona (para el menú)."""
    u = request.user
    return Response({'nuevos': servicios.visibles_para(u).exclude(subido_por=u).exclude(vistos=u).count()})
