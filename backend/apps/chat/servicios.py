from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.utils import timezone

from apps.desempeno.permisos import es_administrador

from .models import Conversacion, Lectura, Mensaje

MAX_POR_MINUTO = 20   # contra spam y ráfagas accidentales
PAGINA = 40
PAGINA_MAX = 100


def sala_global():
    return Conversacion.objects.get_or_create(tipo=Conversacion.GLOBAL)[0]


def conversaciones_de(usuario):
    return Conversacion.objects.filter(Q(tipo=Conversacion.GLOBAL) | Q(a=usuario) | Q(b=usuario))


def conversacion_de(usuario, pk):
    """La conversación solo si la persona participa (los chats privados no los ve nadie más, ni Dirección)."""
    return conversaciones_de(usuario).filter(pk=pk).select_related('a', 'b').first()


def privado_con(usuario, otro):
    a, b = sorted([usuario, otro], key=lambda u: u.id)
    return Conversacion.objects.get_or_create(tipo=Conversacion.DIRECTA, a=a, b=b)[0]


def puede_borrar(usuario, mensaje):
    if mensaje.eliminado:
        return False
    if mensaje.autor_id == usuario.id:
        return True
    # Dirección modera solo la sala de la empresa, nunca una conversación privada
    return mensaje.conversacion.tipo == Conversacion.GLOBAL and es_administrador(usuario)


def excede_ritmo(usuario):
    desde = timezone.now() - timedelta(minutes=1)
    return Mensaje.objects.filter(autor=usuario, creado__gte=desde).count() >= MAX_POR_MINUTO


def registrar(mensaje):
    c = mensaje.conversacion
    c.ultimo_id, c.ultimo_texto, c.ultimo_autor_id, c.ultima_actividad = mensaje.id, mensaje.texto[:140], mensaje.autor_id, mensaje.creado
    c.save(update_fields=['ultimo_id', 'ultimo_texto', 'ultimo_autor', 'ultima_actividad'])


def al_borrar(mensaje):
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
