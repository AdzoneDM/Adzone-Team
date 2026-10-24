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
from rest_framework.throttling import AnonRateThrottle

from apps.desempeno.permisos import LecturaOAdministrador, es_administrador, puede_validar, puesto_de
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
    }


class LoginThrottle(AnonRateThrottle):
    scope = 'login'


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login_view(request):
    """Entrar con usuario o correo. Máximo 10 intentos por minuto desde una misma conexión."""
    identificador = (request.data.get('username') or '').strip()
    password = request.data.get('password') or ''
    remember_me = bool(request.data.get('remember_me', False))

    username = identificador
    if '@' in identificador:
        coincidencia = User.objects.filter(email__iexact=identificador, is_active=True).first()
        if coincidencia:
            username = coincidencia.username
    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response({'error': 'Usuario o contraseña incorrectos.'}, status=status.HTTP_400_BAD_REQUEST)

    django_login(request, user)
    request.session.set_expiry(settings.SESSION_COOKIE_AGE if remember_me else 0)
    return Response({'message': 'Inicio de sesión exitoso.', 'user': datos_usuario(user)}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    django_logout(request)
    return Response({'message': 'Cierre de sesión exitoso.'}, status=status.HTTP_200_OK)


@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([AllowAny])
def session_view(request):
    """Datos del usuario con sesión, o isAuthenticated=false. También entrega la cookie CSRF."""
    if not request.user.is_authenticated:
        return Response({'isAuthenticated': False, 'user': None}, status=status.HTTP_200_OK)
    return Response({'isAuthenticated': True, 'user': datos_usuario(request.user)}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cambiar_clave_view(request):
    actual = request.data.get('actual') or ''
    nueva = request.data.get('nueva') or ''
    if not request.user.check_password(actual):
        return Response({'actual': ['La contraseña actual no es correcta.']}, status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_password(nueva, request.user)
    except ValidationError as e:
        return Response({'nueva': list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
    request.user.set_password(nueva)
    request.user.save()
    update_session_auth_hash(request, request.user)  # no lo saca de la sesión
    return Response({'message': 'Contraseña cambiada.'})
