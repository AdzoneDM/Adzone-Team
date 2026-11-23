import os
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from apps.core.permisos import tiene
from apps.desempeno.permisos import es_administrador

from .models import Conversacion, Lectura, Mensaje

MAX_POR_MINUTO = 20   # contra spam y ráfagas accidentales
PAGINA = 40
PAGINA_MAX = 100
MAX_ARCHIVO = 15 * 1024 * 1024
EXT_IMAGEN = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
EXT_DOCUMENTO = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv', '.zip', '.odt', '.ods')


def sala_global():
    return Conversacion.objects.get_or_create(tipo=Conversacion.GLOBAL)[0]


def conversaciones_de(usuario):
    return Conversacion.objects.filter(Q(tipo=Conversacion.GLOBAL) | Q(a=usuario) | Q(b=usuario) | Q(miembros=usuario)).distinct()


def conversacion_de(usuario, pk):
    """La conversación solo si la persona participa (los chats privados no los ve nadie más, ni Dirección)."""
    return conversaciones_de(usuario).filter(pk=pk).select_related('a', 'b').first()


def privado_con(usuario, otro):
    a, b = sorted([usuario, otro], key=lambda u: u.id)
    return Conversacion.objects.get_or_create(tipo=Conversacion.DIRECTA, a=a, b=b)[0]


def puede_crear_grupos(usuario):
    """Solo las jefaturas (permiso «Grupos de chat»): gerentes de departamento, administradores y quien Dirección autorice."""
    return tiene(usuario, 'chat.grupos')


def departamentos_para_grupos(usuario):
    """Las áreas entre las que una jefatura elige al crear un grupo (vacío para quien no puede crear grupos)."""
    if not puede_crear_grupos(usuario):
        return []
    from apps.core.models import Departamento
    return [{'id': d.id, 'nombre': d.nombre} for d in Departamento.objects.order_by('nombre')]


def puede_gestionar_grupo(usuario, conv):
    """Editar o eliminar un grupo: quien lo creó (si sigue teniendo el permiso) o Dirección. Los demás solo participan."""
    return conv.tipo == Conversacion.GRUPO and puede_crear_grupos(usuario) and (conv.creado_por_id == usuario.id or es_administrador(usuario))


def puede_borrar(usuario, mensaje):
    if mensaje.eliminado:
        return False
    if mensaje.autor_id == usuario.id:
        return True
    # Dirección modera la sala de la empresa y quien administra un grupo, el suyo; nunca una conversación privada
    if mensaje.conversacion.tipo == Conversacion.GLOBAL:
        return es_administrador(usuario)
    return puede_gestionar_grupo(usuario, mensaje.conversacion)


def revisar_archivo(archivo):
    """Documento o imagen de hasta 15 MB. Devuelve si es una imagen. Un archivo ejecutable o de otro tipo se rechaza."""
    ext = os.path.splitext(archivo.name)[1].lower()
    if ext not in EXT_IMAGEN + EXT_DOCUMENTO:
        raise ValidationError({'archivo': ['Solo se pueden enviar imágenes y documentos (PDF, Word, Excel, PowerPoint, texto, CSV o ZIP).']})
    if archivo.size > MAX_ARCHIVO:
        raise ValidationError({'archivo': ['El archivo pesa más de 15 MB.']})
    es_imagen = ext in EXT_IMAGEN
    if es_imagen:
        from PIL import Image
        try:
            Image.open(archivo).verify()
        except Exception:  # noqa: BLE001 (si no se puede abrir como imagen, no lo es)
            raise ValidationError({'archivo': ['Ese archivo no es una imagen válida.']})
        finally:
            archivo.seek(0)
    return es_imagen


def crear_grupo(usuario, nombre, departamento=None, miembros=()):
    nombre = (nombre or '').strip()
    if len(nombre) < 3:
        raise ValidationError({'nombre': ['Ponle un nombre al grupo (mínimo 3 letras).']})
    ids = {usuario.pk, *[m for m in miembros if m]}
    if departamento is not None:  # un grupo por área: entra todo el personal activo de esa área
        ids |= set(User.objects.filter(is_active=True, perfil__puesto_trabajo__departamento=departamento).values_list('pk', flat=True))
    personas = list(User.objects.filter(pk__in=ids, is_active=True))
    if len(personas) < 2:
        raise ValidationError({'miembros': ['Agrega al menos a una persona al grupo.']})
    c = Conversacion.objects.create(tipo=Conversacion.GRUPO, nombre=nombre[:80], departamento=departamento, creado_por=usuario)
    c.miembros.set(personas)
    return c


def excede_ritmo(usuario):
    desde = timezone.now() - timedelta(minutes=1)
    return Mensaje.objects.filter(autor=usuario, creado__gte=desde).count() >= MAX_POR_MINUTO


def registrar(mensaje):
    c = mensaje.conversacion
    c.ultimo_id, c.ultimo_texto, c.ultimo_autor_id, c.ultima_actividad = mensaje.id, (mensaje.texto or f'📎 {mensaje.archivo_nombre}')[:140], mensaje.autor_id, mensaje.creado
    c.save(update_fields=['ultimo_id', 'ultimo_texto', 'ultimo_autor', 'ultima_actividad'])


def al_borrar(mensaje):
    if mensaje.archivo:  # el archivo de un mensaje borrado también se borra
        mensaje.archivo.delete(save=False)
        mensaje.archivo = None
        mensaje.save(update_fields=['archivo'])
    c = mensaje.conversacion
    if c.ultimo_id == mensaje.id:
        c.ultimo_texto = ''
        c.save(update_fields=['ultimo_texto'])


def _umbrales(usuario, convs):
    lecturas = {l.conversacion_id: l.ultimo_leido for l in Lectura.objects.filter(usuario=usuario, conversacion__in=convs)}
    ahora = timezone.now()
    for c in convs:
        if c.id not in lecturas and c.tipo == Conversacion.GLOBAL:
            # Primera vez en la sala: lo de antes de ayer no cuenta como pendiente.
            lecturas[c.id] = (Mensaje.objects.filter(conversacion=c, creado__lt=ahora - timedelta(days=1)).order_by('-id').values_list('id', flat=True).first() or 0)
    return lecturas


def no_leidos_por_conversacion(usuario, convs):
    """{id de conversación: mensajes de otras personas que aún no leyó}. Una sola consulta."""
    convs = list(convs)
    if not convs:
        return {}
    umbral = _umbrales(usuario, convs)
    filtro = Q()
    for c in convs:
        filtro |= Q(conversacion_id=c.id, id__gt=umbral.get(c.id, 0))
    filas = (Mensaje.objects.filter(filtro, eliminado=False).exclude(autor=usuario)
             .values('conversacion').annotate(n=Count('id')))
    return {f['conversacion']: f['n'] for f in filas}


def marcar_leido(usuario, conv, hasta):
    lectura, _ = Lectura.objects.get_or_create(usuario=usuario, conversacion=conv)
    tope = min(hasta, conv.ultimo_id)
    if tope > lectura.ultimo_leido:
        lectura.ultimo_leido = tope
        lectura.save(update_fields=['ultimo_leido', 'actualizado'])


def persona(u):
    perfil = getattr(u, 'perfil', None)
    puesto = getattr(perfil, 'puesto_trabajo', None)
    return {
        'id': u.id,
        'nombre': u.get_full_name() or u.username,
        'puesto': puesto.nombre if puesto else '',
        'departamento': puesto.departamento.nombre if puesto and puesto.departamento_id else '',
    }


def personas_para_chatear(usuario, texto=''):
    qs = User.objects.filter(is_active=True).exclude(pk=usuario.pk).select_related('perfil__puesto_trabajo__departamento')
    for palabra in texto.split():
        qs = qs.filter(Q(first_name__icontains=palabra) | Q(last_name__icontains=palabra) | Q(username__icontains=palabra)
                       | Q(perfil__puesto_trabajo__nombre__icontains=palabra) | Q(perfil__puesto_trabajo__departamento__nombre__icontains=palabra))
    return qs.order_by('first_name', 'last_name', 'username')[:100]
