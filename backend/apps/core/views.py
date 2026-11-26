from django.conf import settings
from django.contrib.auth import authenticate, login as django_login, logout as django_logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle

from apps.callcenter.permisos import es_agente, gestiona_call_center
from apps.desempeno.permisos import LecturaOAdministrador, es_administrador, puede_validar, puesto_de
from apps.operaciones.permisos import areas_que_supervisa, es_almacen, es_coordinacion, es_finanzas, gestiona_algo
from apps.organizacion.models import PerfilUsuario, PuestoDeTrabajo
import time  # noqa: E402

from . import accesos
from . import seguridad as seg
from .acceso import SESION_EQUIPO, clave_configurada, clave_valida, equipo_abierto, fijar_clave
from .models import Departamento
from .serializers import DepartamentoSerializer


class DepartamentoViewSet(viewsets.ModelViewSet):
    """Todos pueden consultar los departamentos; solo el administrador los cambia."""
    queryset = Departamento.objects.all().order_by('nombre')
    serializer_class = DepartamentoSerializer
    permission_classes = [LecturaOAdministrador]

    def destroy(self, request, *args, **kwargs):
        depto = self.get_object()
        if depto.puestos_de_trabajo.exists():
            return Response({"detail": f"«{depto.nombre}» tiene puestos. Muévelos a otro departamento antes de borrarlo."},
                            status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)



def _activos(user):
    from apps.activos.servicios import gestiona_activos
    return gestiona_activos(user)


def _rrhh(user):
    from apps.talento.politicas import es_rrhh
    return es_rrhh(user)


def _pendientes(user):
    from apps.talento.politicas import pendientes
    return len(pendientes(user))


def _permisos(user):
    from apps.core.permisos import efectivos
    return efectivos(user)


def _equipo_con(user, permiso):
    from apps.desempeno.permisos import equipo_gestionable
    return equipo_gestionable(user, permiso).exists()


def _puede_asignar(user):
    from apps.desempeno.permisos import equipo_gestionable
    return equipo_gestionable(user, 'tareas.asignar').exists()


def _tiene_permiso(user, codigo):
    from apps.core.permisos import tiene
    return tiene(user, codigo)


def _comercial(user):
    from apps.comercial.permisos import es_comercial
    return es_comercial(user)


def _ve_solicitudes(user):
    from apps.comercial.permisos import ve_solicitudes
    return ve_solicitudes(user)


def _es_tecnologia(user):
    from apps.core.permisos import tiene
    return tiene(user, 'activos.gestionar')


def datos_usuario(user):
    puesto = puesto_de(user)
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'nombre': user.get_full_name() or user.username,
        'roles': list(user.groups.values_list('name', flat=True)),
        'es_administrador': es_administrador(user),
        'puede_validar': puede_validar(user),
        'puesto': puesto.nombre if puesto else None,
        'departamento': puesto.departamento.nombre if puesto else None,
        'departamento_id': puesto.departamento_id if puesto else None,
        'es_finanzas': es_finanzas(user),
        'es_tecnologia': _es_tecnologia(user),
        'permisos': sorted(_permisos(user)),
        'limite_zip_mb': settings.CHAT_ZIP_MAX_MB,  # el chat avisa antes de subir un ZIP demasiado pesado
        'limite_video_mb': settings.EVIDENCIA_VIDEO_MAX_MB,  # la pantalla avisa antes de subir un video demasiado pesado
        # Adjuntos de tareas que se suben por partes (/api/subidas/): ZIP y videos grandes
        'limite_adjunto_grande_mb': settings.ADJUNTO_GRANDE_MAX_MB,
        'limite_video_grande_mb': settings.EVIDENCIA_VIDEO_GRANDE_MAX_MB,
        'puede_asignar': _puede_asignar(user),
        'puede_autoasignar': _tiene_permiso(user, 'tareas.propias'),
        've_asistencia_equipo': _equipo_con(user, 'asistencia.ver'),
        'es_rrhh': _rrhh(user),
        'gestiona_activos': _activos(user),
        'politicas_pendientes': _pendientes(user),
        'gestiona': gestiona_algo(user),
        'edita_clientes': bool(gestiona_algo(user) or es_finanzas(user) or _tiene_permiso(user, 'clientes.gestionar') or _tiene_permiso(user, 'clientes.completo')),
        'clientes_completo': bool(gestiona_algo(user) or es_finanzas(user) or _tiene_permiso(user, 'clientes.completo')),
        'es_coordinacion': es_coordinacion(user),
        'es_almacen': es_almacen(user),
        'mis_areas': areas_que_supervisa(user),
        'es_agente': es_agente(user),
        'gestiona_call_center': gestiona_call_center(user),
        'es_comercial': _comercial(user),
        've_solicitudes': _ve_solicitudes(user),
    }


class LoginUsuarioThrottle(SimpleRateThrottle):
    """Por conexión y por cuenta: un intento cada ~5 s (12 por minuto). Quien se equivoca puede reintentar enseguida y varias
    personas de la misma oficina entran a la vez, pero nadie puede probar contraseñas de una cuenta a ritmo de máquina."""
    scope = 'login_usuario'

    def get_cache_key(self, request, view):
        # La cuenta ya resuelta (por user_id, correo o usuario): mandar otro «username» junto al user_id no salta el límite
        quien = cuenta_de(request)
        return self.cache_format % {'scope': self.scope, 'ident': f'{self.get_ident(request)}|{quien}'}


def exigir_csrf(request):
    """CSRF también antes de tener sesión (entrada, clave general y segundo paso): otra web no puede iniciar sesión en el
    navegador de alguien. DRF solo lo exige con sesión iniciada, y `csrf_protect` no sirve sobre una vista de DRF."""
    from rest_framework.authentication import CSRFCheck
    from rest_framework.exceptions import PermissionDenied
    verificador = CSRFCheck(lambda r: None)
    verificador.process_request(request._request)
    motivo = verificador.process_view(request._request, None, (), {})
    if motivo:
        raise PermissionDenied('Recarga la página e inténtalo de nuevo (falta el token de seguridad).')


def cuenta_de(request):
    """La cuenta a la que apunta un intento de entrada, resuelta igual que la usa el login (minúsculas)."""
    user_id = request.data.get('user_id')
    if user_id:
        try:
            nombre = User.objects.filter(pk=int(user_id)).values_list('username', flat=True).first()
        except (TypeError, ValueError):
            nombre = None
        return (nombre or f'id:{str(user_id)[:20]}').lower()
    ident = str(request.data.get('username') or '').strip()[:150]
    if '@' in ident:
        nombre = User.objects.filter(email__iexact=ident, is_active=True).values_list('username', flat=True).first()
        if nombre:
            return nombre.lower()
    return ident.lower()


class EquipoThrottle(SimpleRateThrottle):
    """La clave general del equipo: pocos intentos por conexión (adivinarla abriría el directorio del personal)."""
    scope = 'equipo'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class LoginThrottle(AnonRateThrottle):
    """Por conexión, haya o no sesión abierta (si no, alguien con cuenta propia se saltaría el límite)."""
    scope = 'login'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle, LoginUsuarioThrottle])
def login_view(request):
    """Entrar con usuario o correo, o con la persona elegida en el directorio (user_id) si el
    dispositivo ya pasó la clave general. Máximo 10 intentos por minuto desde una misma conexión."""
    exigir_csrf(request)
    identificador = (request.data.get('username') or '').strip()
    user_id = request.data.get('user_id')
    password = request.data.get('password') or ''
    remember_me = bool(request.data.get('remember_me', False))

    cuenta = cuenta_de(request)
    if cuenta and accesos.cuenta_bloqueada(cuenta):
        accesos.registrar('BLOQUEO', request, texto=cuenta, motivo='Intento mientras la cuenta estaba bloqueada')
        return Response({'error': 'Demasiados intentos con contraseña equivocada en esta cuenta. Espera 15 minutos e inténtalo de nuevo.'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS)
    username = identificador
    if user_id:
        if not equipo_abierto(request):
            return Response({'error': 'Primero escribe la clave general del equipo.'}, status=status.HTTP_403_FORBIDDEN)
        username = User.objects.filter(pk=user_id, is_active=True).values_list('username', flat=True).first() or ''
    elif '@' in identificador:
        coincidencia = User.objects.filter(email__iexact=identificador, is_active=True).first()
        if coincidencia:
            username = coincidencia.username
    user = authenticate(request, username=username, password=password)

    if user is None:
        victima = User.objects.filter(username__iexact=cuenta).first() if cuenta else None
        if cuenta and accesos.anotar_fallo(request, cuenta, victima):
            return Response({'error': 'Demasiados intentos con contraseña equivocada en esta cuenta. Espera 15 minutos e inténtalo de nuevo.'},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        error = 'Contraseña incorrecta.' if user_id else 'Usuario o contraseña incorrectos.'
        return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

    # Cuentas de empresa: si hay lista de IPs permitidas (IPS_ADMIN), solo desde esas redes
    redes = accesos.redes_admin()
    if redes and seg.cuenta_de_empresa(user) and not accesos.ip_permitida(accesos.ip_de(request), redes):
        accesos.registrar('IP_BLOQUEADA', request, user, motivo='Cuenta de empresa desde una red no permitida', riesgo=3)
        accesos.alertar_seguridad(user, 'Intento de entrar a tu cuenta desde una red no permitida',
                                  f'Desde {accesos.ip_de(request) or "IP desconocida"}. La contraseña era correcta: si no fuiste tú, cámbiala ya.',
                                  a_seguridad=f'Cuenta de empresa desde red no permitida: {user.get_full_name() or user.username}')
        return Response({'error': 'Tu cuenta solo puede entrar desde la red de la empresa.'}, status=status.HTTP_403_FORBIDDEN)

    if request.user.is_authenticated and request.user.pk != user.pk:
        django_logout(request)  # otra cuenta en este navegador: se cierra antes de seguir
    # Contraseña base de las cuentas nuevas: mientras la tenga, la app le pide cambiarla (se sabe al entrar, sin guardar nada más)
    # …o una contraseña temporal que le puso otra persona (cuenta nueva o restablecida): también la cambia antes de usar nada
    temporal = bool(getattr(getattr(user, 'perfil', None), 'debe_cambiar_clave', False))
    request.session[SESION_CLAVE_BASE] = password == CLAVE_BASE or temporal
    if seg.tiene_dos_pasos(user):
        # La contraseña estuvo bien: falta el código de la app. La sesión aún no se abre.
        request.session[PENDIENTE] = {'id': user.pk, 't': int(time.time()), 'recordar': remember_me, 'intentos': 0}
        return Response({'dos_pasos': True, 'message': 'Escribe el código de 6 dígitos de tu app de verificación.'})
    return _abrir_sesion(request, user, remember_me, dos_pasos_ok=False)


PENDIENTE = 'dos_pasos_pendiente'
SESION_CLAVE_BASE = 'clave_base'
CLAVE_BASE = 'usuarios'


def _abrir_sesion(request, user, remember_me, dos_pasos_ok):
    django_login(request, user)
    request.session[SESION_EQUIPO] = True
    request.session[seg.SESION_OK] = dos_pasos_ok
    request.session[seg.SESION_ACTIVIDAD] = int(time.time())
    request.session.set_expiry(settings.SESSION_COOKIE_AGE if remember_me else 0)
    request.session.save()   # que la sesión tenga su clave ya (queda en la bitácora para listarla y cerrarla)
    r = Response({'message': 'Inicio de sesión exitoso.', 'user': datos_sesion(request, user)}, status=status.HTTP_200_OK)
    nuevo = seg.registrar_dispositivo(request, r, user)
    accesos.al_entrar(request, user, nuevo)
    return r


def datos_sesion(request, user):
    d = datos_usuario(user)
    exige, activo = seg.exige_dos_pasos(user), seg.tiene_dos_pasos(user)
    # «recomendada»: Gerencia, Administración y Tecnología que aún no la activaron (si no es obligatoria)
    d['dos_pasos'] = {'activo': activo, 'exige': exige, 'recomendada': not activo and seg.usa_dos_pasos(user)}
    d['debe_activar_dos_pasos'] = exige and not request.session.get(seg.SESION_OK)
    d['inactividad_min'] = seg.minutos_inactividad(user)
    d['debe_cambiar_clave'] = bool(request.session.get(SESION_CLAVE_BASE))
    return d


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def dos_pasos_login_view(request):
    """Segundo paso de la entrada: el código de la app (o uno de respaldo). Cinco intentos y cinco minutos."""
    exigir_csrf(request)
    from .models import DosPasos
    p = request.session.get(PENDIENTE)
    if not p or time.time() - p['t'] > 300 or p['intentos'] >= 5:
        request.session.pop(PENDIENTE, None)
        return Response({'error': 'Vuelve a escribir tu usuario y contraseña.', 'reiniciar': True}, status=status.HTTP_400_BAD_REQUEST)
    user = User.objects.filter(pk=p['id'], is_active=True).first()
    dp = DosPasos.objects.filter(usuario=user, activo=True).first() if user else None
    if dp is not None and seg.bloqueado(dp):
        request.session.pop(PENDIENTE, None)
        return Response({'error': 'Demasiados códigos equivocados: espera 15 minutos e inténtalo de nuevo.', 'reiniciar': True},
                        status=status.HTTP_429_TOO_MANY_REQUESTS)
    if dp is None or not seg.verificar(dp, request.data.get('codigo')):
        accesos.registrar('FALLO_CODIGO', request, user)
        p['intentos'] += 1
        request.session[PENDIENTE] = p
        return Response({'error': 'Código incorrecto o vencido.'}, status=status.HTTP_400_BAD_REQUEST)
    request.session.pop(PENDIENTE, None)
    return _abrir_sesion(request, user, p['recordar'], dos_pasos_ok=True)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Cierra la sesión de la persona; el dispositivo vuelve al directorio sin pedir otra vez la clave general."""
    seguia_abierto = bool(request.session.get(SESION_EQUIPO))
    endpoint = str(request.data.get('push_endpoint') or '')
    if endpoint:  # este dispositivo deja de recibir los avisos de esta persona
        from .models import SuscripcionPush
        SuscripcionPush.objects.filter(usuario=request.user, endpoint=endpoint).delete()
    accesos.registrar('SALIDA', request, request.user, sesion=request.session.session_key or '')
    django_logout(request)
    if seguia_abierto:
        request.session[SESION_EQUIPO] = True
    return Response({'message': 'Cierre de sesión exitoso.'}, status=status.HTTP_200_OK)


@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([AllowAny])
def session_view(request):
    """Datos del usuario con sesión, o isAuthenticated=false. También entrega la cookie CSRF."""
    if not request.user.is_authenticated:
        return Response({'isAuthenticated': False, 'user': None}, status=status.HTTP_200_OK)
    return Response({'isAuthenticated': True, 'user': datos_sesion(request, request.user)}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle, EquipoThrottle])
def equipo_view(request):
    """Primer paso de la entrada: la clave general del equipo. Desbloquea el directorio en este dispositivo."""
    exigir_csrf(request)
    if not clave_configurada():
        return Response({'error': 'El administrador todavía no definió la clave general del equipo.'},
                        status=status.HTTP_400_BAD_REQUEST)
    if not clave_valida(request.data.get('clave') or ''):
        accesos.registrar('FALLO', request, texto='(clave general del equipo)')
        return Response({'error': 'Clave del equipo incorrecta.'}, status=status.HTTP_400_BAD_REQUEST)
    request.session[SESION_EQUIPO] = True
    return Response({'areas': directorio()})


@api_view(['GET'])
@permission_classes([AllowAny])
def directorio_view(request):
    """Áreas con su personal, para elegir quién entra. Solo tras la clave general del equipo."""
    if not equipo_abierto(request):
        return Response({'detail': 'Escribe la clave general del equipo.', 'configurada': clave_configurada()},
                        status=status.HTTP_403_FORBIDDEN)
    return Response({'areas': directorio()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clave_equipo_view(request):
    """El administrador define o cambia la clave general del equipo."""
    from apps.core.permisos import tiene
    if not tiene(request.user, 'personal.usuarios'):
        return Response({'detail': 'Solo quien administra personas y accesos puede cambiar la clave del equipo.'}, status=status.HTTP_403_FORBIDDEN)
    nueva = request.data.get('nueva') or ''
    if len(nueva) < 8:
        return Response({'nueva': ['Necesita al menos 8 caracteres.']}, status=status.HTTP_400_BAD_REQUEST)
    fijar_clave(nueva)
    return Response({'message': 'Clave del equipo guardada.'})


def directorio():
    """Cada área (en el orden oficial) con sus personas activas, de la cabeza del área hacia abajo
    según el organigrama: primero el nivel, luego el puesto y el nombre."""
    puestos = {p.id: p for p in PuestoDeTrabajo.objects.select_related('supervisor')}

    def nivel(puesto):
        n, visto, actual = 0, set(), puesto
        while actual.supervisor_id and actual.supervisor_id not in visto and actual.supervisor_id in puestos:
            visto.add(actual.id)
            actual = puestos[actual.supervisor_id]
            n += 1
        return n

    personas = {}
    perfiles = PerfilUsuario.objects.filter(user__is_active=True, puesto_trabajo__isnull=False).select_related('user')
    for perfil in perfiles:
        puesto = puestos[perfil.puesto_trabajo_id]
        personas.setdefault(puesto.departamento_id, []).append({
            'id': perfil.user_id,
            'nombre': perfil.user.get_full_name() or perfil.user.username,
            'puesto': puesto.nombre,
            'reporta_a': puesto.supervisor.nombre if puesto.supervisor else None,
            'nivel': nivel(puesto),
        })

    areas = []
    for depto in Departamento.objects.all():
        lista = sorted(personas.get(depto.id, []), key=lambda p: (p['nivel'], p['puesto'].lower(), p['nombre'].lower()))
        areas.append({'id': depto.id, 'nombre': depto.nombre, 'descripcion': depto.descripcion,
                      'color': depto.color, 'color_fondo': depto.color_fondo, 'personas': lista})
    return areas


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cambiar_clave_view(request):
    actual = request.data.get('actual') or ''
    nueva = request.data.get('nueva') or ''
    if not request.user.check_password(actual):
        return Response({'actual': ['La contraseña actual no es correcta.']}, status=status.HTTP_400_BAD_REQUEST)
    if nueva == CLAVE_BASE:
        return Response({'nueva': ['Elige una contraseña distinta de la contraseña base.']}, status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_password(nueva, request.user)
    except ValidationError as e:
        return Response({'nueva': list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
    request.user.set_password(nueva)
    request.user.save()
    update_session_auth_hash(request, request.user)  # no lo saca de la sesión; las demás sesiones quedan cerradas
    request.session[SESION_CLAVE_BASE] = False
    from apps.organizacion.models import PerfilUsuario
    PerfilUsuario.objects.filter(user=request.user).update(debe_cambiar_clave=False)
    accesos.registrar('CLAVE', request, request.user, motivo='Cambió su contraseña (se cerraron sus otras sesiones)')
    from apps.talento.auditoria import auditar
    auditar('Cambió su contraseña', request.user, usuario=request.user)
    return Response({'message': 'Contraseña cambiada.'})
