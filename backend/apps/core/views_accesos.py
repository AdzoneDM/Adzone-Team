"""Pantalla «Accesos y permisos»: perfiles, perfiles de cada persona, excepciones y equipo adicional."""
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import exceptions, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.talento.auditoria import auditar
from .models import EquipoExtra, ExcepcionPermiso, PermisosDePerfil
from .permisos import CODIGOS, DE_EQUIPO, PERFILES, PERMISOS, efectivos, permisos, permisos_de_perfiles, revisar_cambio, tiene

BASE = set(PERFILES)  # perfiles que trae la plataforma: se pueden ajustar, no borrar


def _gestiona(user):
    if not tiene(user, 'personal.usuarios'):
        raise exceptions.PermissionDenied("Los accesos los maneja quien tiene el permiso «Personas y accesos».")


def _direccion(user):
    if not tiene(user, 'direccion'):
        raise exceptions.PermissionDenied("Los perfiles los define la Dirección.")


def _nombre(u):
    return (u.get_full_name() or u.username) if u else None


def _perfil(p, cuantos):
    return {'id': p.grupo_id, 'nombre': p.grupo.name, 'descripcion': p.descripcion, 'permisos': sorted(p.permisos or []),
            'orden': p.orden, 'personas': cuantos.get(p.grupo_id, 0), 'de_la_plataforma': p.grupo.name in BASE}


def _rechazar(motivo):
    if motivo:
        raise exceptions.PermissionDenied(motivo)


@api_view(['GET'])
def catalogo_view(request):
    _gestiona(request.user)
    from django.db.models import Count
    cuantos = dict(Group.objects.filter(user__is_active=True).annotate(n=Count('user')).values_list('pk', 'n'))
    return Response({
        'permisos': [{'codigo': c, 'nombre': n, 'grupo': g, 'alcance': a, 'descripcion': d} for c, n, g, a, d in PERMISOS],
        'perfiles': [_perfil(p, cuantos) for p in PermisosDePerfil.objects.select_related('grupo').order_by('-orden', 'grupo__name')],
        'mios': sorted(permisos(request.user)),
        'edita_perfiles': tiene(request.user, 'direccion'),
    })


def _validar_permisos(lista):
    if not isinstance(lista, list) or any(c not in CODIGOS for c in lista):
        raise exceptions.ValidationError({'permisos': 'Lista de permisos no válida.'})
    return sorted(set(lista))


@api_view(['POST'])
def perfil_crear_view(request):
    _direccion(request.user)
    nombre = (request.data.get('nombre') or '').strip()[:80]
    if len(nombre) < 3:
        raise exceptions.ValidationError({'nombre': 'Escribe un nombre de al menos 3 letras.'})
    if Group.objects.filter(name__iexact=nombre).exists():
        raise exceptions.ValidationError({'nombre': 'Ya existe un perfil con ese nombre.'})
    lista = _validar_permisos(request.data.get('permisos') or [])
    _rechazar(revisar_cambio(request.user, None, lista))
    with transaction.atomic():
        g = Group.objects.create(name=nombre)
        p = PermisosDePerfil.objects.create(grupo=g, descripcion=(request.data.get('descripcion') or '')[:200], permisos=lista, orden=50)
    auditar('Perfil de acceso creado', nombre, None, {'permisos': lista})
    return Response(_perfil(p, {}), status=status.HTTP_201_CREATED)


@api_view(['PATCH', 'DELETE'])
def perfil_view(request, pk):
    _direccion(request.user)
    p = get_object_or_404(PermisosDePerfil.objects.select_related('grupo'), grupo_id=pk)
    miembros = p.grupo.user_set.filter(is_active=True).count()
    if request.method == 'DELETE':
        if p.grupo.name in BASE:
            raise exceptions.ValidationError('Este perfil viene con la plataforma: ajusta sus permisos en vez de borrarlo.')
        if p.grupo.user_set.exists():
            raise exceptions.ValidationError('Tiene personas asignadas: cámbialas de perfil antes de borrarlo.')
        auditar('Perfil de acceso borrado', p.grupo.name, {'permisos': p.permisos}, None)
        p.grupo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    antes = sorted(p.permisos or [])
    if 'permisos' in request.data:
        nuevos = _validar_permisos(request.data['permisos'])
        if p.grupo.name == 'Administrador' and 'direccion' not in nuevos:
            raise exceptions.ValidationError('El perfil de Dirección no puede perder el permiso «Dirección».')
        _rechazar(revisar_cambio(request.user, None, set(antes) ^ set(nuevos)))
        if request.user.groups.filter(pk=p.grupo_id).exists() and set(antes) - set(nuevos) and not request.user.is_superuser:
            raise exceptions.PermissionDenied("No puedes quitar permisos a un perfil que tú mismo tienes.")
        p.permisos = nuevos
    if 'descripcion' in request.data:
        p.descripcion = (request.data.get('descripcion') or '')[:200]
    p.save()
    if antes != sorted(p.permisos):
        auditar('Permisos de un perfil', p.grupo.name, {'permisos': antes}, {'permisos': p.permisos})
    return Response(_perfil(p, {p.grupo_id: miembros}))


def _persona(u, jefes):
    perfil = getattr(u, 'perfil', None)
    puesto = perfil.puesto_trabajo if perfil else None
    return {
        'id': u.pk, 'nombre': _nombre(u), 'usuario': u.username,
        'puesto': puesto.nombre if puesto else None,
        'departamento': puesto.departamento.nombre if puesto and puesto.departamento_id else None,
        'jefe': jefes.get(puesto.supervisor_id) if puesto else None,
        'perfiles': sorted(g.name for g in u.groups.all()),
        'excepciones': [{'id': e.pk, 'permiso': e.permiso, 'conceder': e.conceder, 'motivo': e.motivo} for e in u.excepciones_permiso.all()],
        'equipo_extra': [{'id': x.pk, 'colaborador': x.colaborador_id, 'nombre': _nombre(x.colaborador), 'hasta': x.hasta, 'motivo': x.motivo}
                         for x in u.equipo_extra.all()],
        'permisos': sorted(efectivos(u)),
        'superusuario': u.is_superuser,
        'dos_pasos': hasattr(u, 'dos_pasos') and u.dos_pasos.activo,
    }


def _jefes():
    salida = {}
    for u in User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=False).select_related('perfil'):
        salida.setdefault(u.perfil.puesto_trabajo_id, _nombre(u))
    return salida


def _usuarios():
    return (User.objects.filter(is_active=True).select_related('perfil__puesto_trabajo__departamento')
            .prefetch_related('groups', 'excepciones_permiso', 'equipo_extra__colaborador').order_by('first_name', 'last_name', 'username'))


@api_view(['GET'])
def personas_view(request):
    _gestiona(request.user)
    jefes = _jefes()
    return Response([_persona(u, jefes) for u in _usuarios()])


@api_view(['POST'])
def persona_perfiles_view(request, pk):
    _gestiona(request.user)
    persona = get_object_or_404(User, pk=pk, is_active=True)
    nombres = request.data.get('perfiles')
    if not isinstance(nombres, list) or not nombres:
        raise exceptions.ValidationError({'perfiles': 'Elige al menos un perfil (Colaborador si solo cumple sus tareas).'})
    grupos = list(Group.objects.filter(name__in=nombres, permisos_acceso__isnull=False))
    if len(grupos) != len(set(nombres)):
        raise exceptions.ValidationError({'perfiles': 'Hay un perfil que no existe.'})
    antes = sorted(g.name for g in persona.groups.all())
    en_juego = permisos_de_perfiles(antes) ^ permisos_de_perfiles(nombres)
    _rechazar(revisar_cambio(request.user, persona, en_juego))
    if 'Administrador' in antes and not any(g.name == 'Administrador' for g in grupos):
        from django.contrib.auth.models import User as U
        if U.objects.filter(is_active=True, groups__name='Administrador').exclude(pk=persona.pk).count() == 0:
            raise exceptions.ValidationError('Debe quedar al menos una persona en Dirección.')
    with transaction.atomic():
        persona.groups.remove(*persona.groups.filter(permisos_acceso__isnull=False))
        persona.groups.add(*grupos)
        es_dir = any(g.name == 'Administrador' for g in grupos)
        if persona.is_staff != es_dir and not persona.is_superuser:
            persona.is_staff = es_dir
            persona.save(update_fields=['is_staff'])
    despues = sorted(g.name for g in grupos)
    if antes != despues:
        auditar('Perfiles de acceso', _nombre(persona), {'perfiles': antes}, {'perfiles': despues})
    persona = _usuarios().get(pk=persona.pk)
    return Response(_persona(persona, _jefes()))


@api_view(['POST'])
def excepcion_crear_view(request):
    _gestiona(request.user)
    persona = get_object_or_404(User, pk=request.data.get('usuario'), is_active=True)
    codigo = request.data.get('permiso')
    if codigo not in CODIGOS:
        raise exceptions.ValidationError({'permiso': 'Permiso desconocido.'})
    conceder = request.data.get('conceder', True)
    if not isinstance(conceder, bool):
        raise exceptions.ValidationError({'conceder': 'Debe ser verdadero o falso.'})
    motivo = (request.data.get('motivo') or '').strip()[:200]
    if not motivo:
        raise exceptions.ValidationError({'motivo': 'Explica por qué: queda en la auditoría.'})
    _rechazar(revisar_cambio(request.user, persona, {codigo}))
    e, _ = ExcepcionPermiso.objects.update_or_create(usuario=persona, permiso=codigo,
                                                     defaults={'conceder': conceder, 'motivo': motivo, 'creado_por': request.user})
    auditar('Excepción de permiso', _nombre(persona), None, {'permiso': codigo, 'conceder': conceder, 'motivo': motivo})
    return Response({'id': e.pk, 'permiso': codigo, 'conceder': conceder, 'motivo': motivo}, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
def excepcion_view(request, pk):
    _gestiona(request.user)
    e = get_object_or_404(ExcepcionPermiso.objects.select_related('usuario'), pk=pk)
    _rechazar(revisar_cambio(request.user, e.usuario, {e.permiso}))
    auditar('Excepción de permiso quitada', _nombre(e.usuario), {'permiso': e.permiso, 'conceder': e.conceder}, None)
    e.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
def equipo_extra_crear_view(request):
    _gestiona(request.user)
    jefe = get_object_or_404(User, pk=request.data.get('jefe'), is_active=True)
    colaborador = get_object_or_404(User, pk=request.data.get('colaborador'), is_active=True)
    if jefe.pk == colaborador.pk:
        raise exceptions.ValidationError('Nadie es parte de su propio equipo.')
    if request.user.pk in (jefe.pk, colaborador.pk) and not request.user.is_superuser:
        raise exceptions.PermissionDenied("No puedes cambiar tu propio equipo ni elegir quién te supervisa.")
    # Dar equipo es delegar autoridad: quien lo hace debe tener los permisos de equipo del jefe y más que el colaborador,
    # y nadie queda a cargo de alguien con más permisos que él.
    _rechazar(revisar_cambio(request.user, jefe, efectivos(jefe) & DE_EQUIPO))
    if not efectivos(colaborador) <= efectivos(request.user) or not efectivos(colaborador) <= efectivos(jefe):
        raise exceptions.PermissionDenied("Nadie queda a cargo de alguien con más permisos que él (ni que tú).")
    hasta = request.data.get('hasta') or None
    if hasta:
        from datetime import date
        try:
            hasta = date.fromisoformat(str(hasta))
        except ValueError:
            raise exceptions.ValidationError({'hasta': 'Fecha no válida (AAAA-MM-DD).'})
        from django.utils import timezone
        if hasta < timezone.localdate():
            raise exceptions.ValidationError({'hasta': 'La fecha de fin ya pasó.'})
    motivo = (request.data.get('motivo') or '').strip()[:200]
    x, _ = EquipoExtra.objects.update_or_create(jefe=jefe, colaborador=colaborador,
                                                defaults={'motivo': motivo, 'hasta': hasta, 'creado_por': request.user})
    auditar('Equipo adicional', _nombre(jefe), None, {'colaborador': _nombre(colaborador), 'hasta': str(hasta or ''), 'motivo': motivo})
    return Response({'id': x.pk, 'colaborador': colaborador.pk, 'nombre': _nombre(colaborador), 'hasta': hasta, 'motivo': motivo},
                    status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
def equipo_extra_view(request, pk):
    _gestiona(request.user)
    x = get_object_or_404(EquipoExtra.objects.select_related('jefe', 'colaborador'), pk=pk)
    if request.user.pk in (x.jefe_id, x.colaborador_id) and not request.user.is_superuser:
        raise exceptions.PermissionDenied("No puedes cambiar tu propio equipo.")
    auditar('Equipo adicional quitado', _nombre(x.jefe), {'colaborador': _nombre(x.colaborador)}, None)
    x.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['DELETE'])
def reiniciar_dos_pasos_view(request, pk):
    """Quien perdió el celular: se le borra la verificación y la vuelve a activar al entrar. Nunca la propia."""
    _gestiona(request.user)
    from .models import DosPasos
    persona = get_object_or_404(User, pk=pk)
    if persona.pk == request.user.pk:
        raise exceptions.PermissionDenied("La tuya la reinicia otra persona con el permiso «Personas y accesos».")
    if persona.is_superuser and not request.user.is_superuser:
        raise exceptions.PermissionDenied("La cuenta de superusuario solo la cambia otro superusuario.")
    _rechazar(revisar_cambio(request.user, persona, set()))
    borradas, _ = DosPasos.objects.filter(usuario=persona).delete()
    if borradas:
        from . import seguridad
        seguridad.cerrar_sesiones(persona)
        auditar('Reinició la verificación en dos pasos', _nombre(persona))
    return Response(status=status.HTTP_204_NO_CONTENT)
