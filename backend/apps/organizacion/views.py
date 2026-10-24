from django.contrib.auth.models import User
from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.desempeno.permisos import EsAdministrador, LecturaOAdministrador, administradores
from .models import PerfilUsuario, PuestoDeTrabajo
from .serializers import PuestoDeTrabajoSerializer, UserSerializer


def _puestos():
    return PuestoDeTrabajo.objects.select_related('departamento', 'supervisor').prefetch_related(
        Prefetch('perfiles_usuarios', queryset=PerfilUsuario.objects.select_related('user'))
    ).order_by('departamento__nombre', 'nombre')


class PuestoDeTrabajoViewSet(viewsets.ModelViewSet):
    """Todos pueden ver los puestos (el organigrama); solo el administrador los cambia."""
    serializer_class = PuestoDeTrabajoSerializer
    permission_classes = [LecturaOAdministrador]
    filterset_fields = ['departamento']

    def get_queryset(self):
        return _puestos()

    def destroy(self, request, *args, **kwargs):
        puesto = self.get_object()
        if puesto.perfiles_usuarios.filter(user__is_active=True).exists():
            return Response({"detail": "Hay personas en este puesto. Cámbialas de puesto antes de borrarlo."},
                            status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)


class UserViewSet(viewsets.ModelViewSet):
    """Usuarios: solo el administrador. Protecciones para no quedarse sin administradores."""
    queryset = User.objects.select_related('perfil__puesto_trabajo__departamento').prefetch_related('groups').order_by(
        'first_name', 'last_name', 'username')
    serializer_class = UserSerializer
    permission_classes = [EsAdministrador]

    def _proteger(self, usuario, roles=None, activo=None):
        yo = self.request.user
        admins = administradores()
        if usuario.pk == yo.pk:
            if activo is False:
                return "No puedes desactivar tu propia cuenta."
            if roles is not None and 'Administrador' not in roles:
                return "No puedes quitarte a ti mismo el rol de Administrador."
        quita_admin = (roles is not None and 'Administrador' not in roles) or activo is False
        if quita_admin and admins.filter(pk=usuario.pk).exists() and admins.count() <= 1:
            return "Debe quedar al menos un administrador activo."
        return None

    def update(self, request, *args, **kwargs):
        usuario = self.get_object()
        motivo = self._proteger(usuario, request.data.get('roles_asignados'), request.data.get('is_active'))
        if motivo:
            return Response({"detail": motivo}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        usuario = self.get_object()
        if usuario.pk == request.user.pk:
            return Response({"detail": "No puedes borrar tu propia cuenta."}, status=status.HTTP_400_BAD_REQUEST)
        motivo = self._proteger(usuario, activo=False)
        if motivo:
            return Response({"detail": motivo}, status=status.HTTP_400_BAD_REQUEST)
        if usuario.tareas.exists():
            return Response({"detail": "Esta persona tiene tareas y resultados guardados. Desactívala en vez de borrarla."},
                            status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)


@api_view(['GET'])
def organigrama_view(request):
    """Árbol de puestos (quién reporta a quién) con las personas de cada puesto."""
    puestos = list(_puestos())
    nodos = {p.id: {
        'id': p.id, 'nombre': p.nombre, 'departamento': p.departamento.nombre, 'departamento_id': p.departamento_id,
        'personas': [{'id': pf.user_id, 'nombre': pf.user.get_full_name() or pf.user.username}
                     for pf in p.perfiles_usuarios.all() if pf.user.is_active],
        'hijos': [],
    } for p in puestos}
    raices = []
    for p in puestos:
        if p.supervisor_id and p.supervisor_id in nodos:
            nodos[p.supervisor_id]['hijos'].append(nodos[p.id])
        else:
            raices.append(nodos[p.id])
    sin_puesto = User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=True).count()
    return Response({'raices': raices, 'sin_puesto': sin_puesto})
