"""Mi cuenta → Verificación en dos pasos: activar con la app, códigos de respaldo y desactivar (si no es obligatoria)."""
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import seguridad as seg
from .models import DosPasos

NUEVO = 'dos_pasos_nuevo'


def _estado(request):
    u = request.user
    dp = DosPasos.objects.filter(usuario=u, activo=True).first()
    return {'activo': bool(dp), 'exige': seg.exige_dos_pasos(u), 'activado': dp.activado if dp else None,
            'respaldo_restantes': len(dp.respaldo) if dp else 0}


@api_view(['GET'])
def estado_view(request):
    return Response(_estado(request))


@api_view(['POST'])
def iniciar_view(request):
    """Genera un secreto nuevo (aún sin activar) y su código QR para escanear con la app."""
    if DosPasos.objects.filter(usuario=request.user, activo=True).exists() and \
            not request.user.check_password(request.data.get('clave') or ''):
        raise exceptions.ValidationError({'clave': 'Para cambiar de celular, escribe tu contraseña.'})
    secreto = seg.nuevo_secreto()
    request.session[NUEVO] = secreto
    texto = seg.uri(request.user, secreto)
    return Response({'secreto': secreto, 'uri': texto, 'qr': seg.qr_svg(texto)})


@api_view(['POST'])
def confirmar_view(request):
    """Activa la verificación cuando el primer código de la app es correcto. Devuelve los códigos de respaldo una sola vez."""
    secreto = request.session.get(NUEVO)
    if not secreto:
        raise exceptions.ValidationError({'codigo': 'Primero escanea el código QR.'})
    paso = seg.paso_valido(secreto, request.data.get('codigo'))
    if paso is None:
        raise exceptions.ValidationError({'codigo': 'Ese código no coincide. Revisa que la hora del celular esté en automático.'})
    codigos, hashes = seg.nuevos_respaldo()
    cambio = DosPasos.objects.filter(usuario=request.user, activo=True).exists()
    DosPasos.objects.update_or_create(usuario=request.user, defaults={'fallos': 0, 'bloqueado_hasta': None,
        'secreto': secreto, 'activo': True, 'ultimo_paso': paso, 'respaldo': hashes, 'activado': timezone.now()})
    request.session.pop(NUEVO, None)
    request.session[seg.SESION_OK] = True
    from apps.talento.auditoria import auditar
    auditar('Cambió el celular de la verificación' if cambio else 'Activó la verificación en dos pasos',
            request.user.get_full_name() or request.user.username)
    if cambio:
        from apps.desempeno.servicios import avisar
        avisar([request.user], 'SEGURIDAD', 'Tu verificación en dos pasos ahora usa otro celular',
               'Si no fuiste tú, avisa de inmediato a la Dirección.', enlace='/mi-cuenta')
        seg.cerrar_sesiones(request.user, excepto=request.session.session_key)
    return Response({**_estado(request), 'codigos_respaldo': codigos})


@api_view(['POST'])
def respaldo_view(request):
    """Códigos de respaldo nuevos (los anteriores dejan de servir). Pide un código de la app."""
    dp = DosPasos.objects.filter(usuario=request.user, activo=True).first()
    if dp is None or not seg.verificar(dp, request.data.get('codigo')):
        raise exceptions.ValidationError({'codigo': 'Código incorrecto.'})
    codigos, hashes = seg.nuevos_respaldo()
    dp.respaldo = hashes
    dp.save(update_fields=['respaldo'])
    return Response({**_estado(request), 'codigos_respaldo': codigos})


@api_view(['POST'])
def desactivar_view(request):
    if seg.exige_dos_pasos(request.user):
        raise exceptions.PermissionDenied("Tu cuenta maneja datos de la empresa: la verificación en dos pasos es obligatoria.")
    if not request.user.check_password(request.data.get('clave') or ''):
        raise exceptions.ValidationError({'clave': 'Contraseña incorrecta.'})
    DosPasos.objects.filter(usuario=request.user).delete()
    return Response(_estado(request))
