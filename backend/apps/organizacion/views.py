from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from apps.desempeno.permisos import EsAdministrador, LecturaOAdministrador, TienePermiso, administradores
from .models import PerfilUsuario, PuestoDeTrabajo
from .serializers import PuestoDeTrabajoSerializer, UserSerializer


def _puestos():
    return PuestoDeTrabajo.objects.select_related('departamento', 'supervisor').prefetch_related(
        Prefetch('perfiles_usuarios', queryset=PerfilUsuario.objects.select_related('user').prefetch_related('puestos_adicionales')), 'subordinados',
        Prefetch('perfiles_adicionales', queryset=PerfilUsuario.objects.select_related('user')), 'coordina_con'
    ).order_by('departamento__nombre', 'nombre')


def prefetch_puesto(prefijo):
    """Todo lo que necesita PuestoDeTrabajoSerializer, precargado, para listas de cosas que cuelgan de un puesto (usuarios, KPIs…)."""
    return [
        f'{prefijo}__supervisor',
        Prefetch(f'{prefijo}__perfiles_usuarios', queryset=PerfilUsuario.objects.select_related('user')),
        f'{prefijo}__subordinados',
        f'{prefijo}__coordina_con',
    ]


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
        from .estructura import registrar
        registrar(request.user, None, {'nombre': puesto.nombre}, {'nombre': puesto.nombre, 'baja': puesto.nombre})
        return super().destroy(request, *args, **kwargs)

    # Registro de cambios del organigrama (nomenclatura, ubicación y dependencia), pendiente hasta que Dirección apruebe una versión
    def perform_create(self, serializer):
        from .estructura import foto, registrar
        p = serializer.save()
        registrar(self.request.user, p, {'nombre': p.nombre, 'alta': ''}, {**foto(p), 'alta': p.nombre})

    def perform_update(self, serializer):
        from .estructura import foto, registrar
        antes = foto(serializer.instance)
        p = serializer.save()
        registrar(self.request.user, p, antes, foto(p))


class UserViewSet(viewsets.ModelViewSet):
    """Usuarios: solo el administrador. Protecciones para no quedarse sin administradores."""
    queryset = User.objects.select_related('perfil__puesto_trabajo__departamento').prefetch_related(
        'groups', *prefetch_puesto('perfil__puesto_trabajo'),
        Prefetch('perfil__puestos_adicionales', queryset=PuestoDeTrabajo.objects.select_related('departamento')),
    ).order_by('first_name', 'last_name', 'username')
    serializer_class = UserSerializer
    # «Personas y accesos» lo maneja todo; «Personas» (directorio) solo ve, crea y desactiva: ver _limitado y _bloqueo_limitado
    permission_classes = [TienePermiso.de_alguno('personal.usuarios', 'personal.directorio')]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # quien hace el cambio, para la auditoría y para que el organigrama no reparta permisos que esa persona no puede dar
        from apps.talento.auditoria import _usuario
        if request.user.is_authenticated:
            self._token_auditoria = _usuario.set(request.user)

    def finalize_response(self, request, response, *args, **kwargs):
        token = getattr(self, '_token_auditoria', None)
        if token is not None:
            from apps.talento.auditoria import _usuario
            _usuario.reset(token)
            self._token_auditoria = None
        return super().finalize_response(request, response, *args, **kwargs)

    def _proteger(self, usuario, roles=None, activo=None):
        yo = self.request.user
        admins = administradores()
        from apps.core.permisos import efectivos
        if usuario.pk != yo.pk and usuario.is_superuser and not yo.is_superuser:
            return "La cuenta de superusuario solo la cambia otro superusuario."
        if usuario.pk != yo.pk and not yo.is_superuser and not efectivos(usuario) <= efectivos(yo):
            return "Esta persona tiene permisos que tú no tienes: su cuenta (contraseña, estado y perfiles) la cambia la Dirección."
        if usuario.pk == yo.pk:
            if activo is False:
                return "No puedes desactivar tu propia cuenta."
            if roles is not None and 'Administrador' not in roles and 'Administrador' in usuario.groups.values_list('name', flat=True):
                return "No puedes quitarte a ti mismo el rol de Administrador."
        quita_admin = (roles is not None and 'Administrador' not in roles) or activo is False
        if quita_admin and admins.filter(pk=usuario.pk).exists() and admins.count() <= 1:
            return "Debe quedar al menos un administrador activo."
        return None

    def _limitado(self):
        """Tiene «Personas» (directorio) pero no «Personas y accesos»: ve, crea y desactiva, nada de correos, claves ni accesos."""
        from apps.core.permisos import tiene
        yo = self.request.user
        return not yo.is_superuser and tiene(yo, 'personal.directorio') and not tiene(yo, 'personal.usuarios')

    MENSAJE_LIMITADO = ("Con el permiso «Personas» no puedes cambiar correos, contraseñas, perfiles de acceso ni permisos: "
                        "eso lo hace quien tiene «Personas y accesos».")

    def _bloqueo_limitado(self, usuario, datos):
        """Qué cambios de una persona existente no se permiten con «Personas» (se ignoran los valores que no cambian)."""
        if datos.get('password'):
            return self.MENSAJE_LIMITADO
        if 'email' in datos and (datos.get('email') or '').strip().lower() != (usuario.email or '').strip().lower():
            return self.MENSAJE_LIMITADO
        if 'username' in datos and (datos.get('username') or '').strip().lower() != usuario.username:
            return self.MENSAJE_LIMITADO
        if datos.get('roles_asignados') is not None and set(datos.get('roles_asignados')) != set(usuario.groups.values_list('name', flat=True)):
            return self.MENSAJE_LIMITADO
        puesto = getattr(getattr(usuario, 'perfil', None), 'puesto_trabajo_id', None)
        if 'puesto_trabajo_id' in datos and str(datos.get('puesto_trabajo_id') or '') != str(puesto or ''):
            return "Con el permiso «Personas» no puedes cambiar el puesto: define el equipo y los permisos de la persona."
        if datos.get('puestos_adicionales_ids') is not None:
            actuales = {str(i) for i in usuario.perfil.puestos_adicionales.values_list('pk', flat=True)} if hasattr(usuario, 'perfil') else set()
            if {str(i) for i in datos.get('puestos_adicionales_ids')} != actuales:
                return "Con el permiso «Personas» no puedes cambiar los puestos adicionales."
        return None

    def create(self, request, *args, **kwargs):
        if self._limitado():
            if set(request.data.get('roles_asignados') or ['Colaborador']) != {'Colaborador'} or request.data.get('puestos_adicionales_ids'):
                return Response({"detail": "Con el permiso «Personas» las cuentas nuevas entran como Colaborador y sin puestos adicionales."},
                                status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        usuario = self.get_object()
        if self._limitado():
            bloqueo = self._bloqueo_limitado(usuario, request.data)
            if bloqueo:
                return Response({"detail": bloqueo}, status=status.HTTP_403_FORBIDDEN)
        motivo = self._proteger(usuario, request.data.get('roles_asignados'), request.data.get('is_active'))
        puesto_actual = getattr(getattr(usuario, 'perfil', None), 'puesto_trabajo_id', None)
        if (not motivo and usuario.pk == request.user.pk and 'puesto_trabajo_id' in request.data
                and str(request.data.get('puesto_trabajo_id') or '') != str(puesto_actual or '')):
            from apps.core.permisos import tiene
            if not tiene(request.user, 'direccion'):
                motivo = 'No puedes cambiar tu propio puesto: el organigrama decide sobre quién tienes permisos. Lo cambia la Dirección.'
        if motivo:
            return Response({"detail": motivo}, status=status.HTTP_400_BAD_REQUEST)
        antes = usuario.is_active
        nueva_clave = bool(request.data.get('password'))
        respuesta = super().update(request, *args, **kwargs)
        usuario.refresh_from_db()
        if nueva_clave and respuesta.status_code < 300 and usuario.pk != request.user.pk:
            usuario.perfil.debe_cambiar_clave = True   # contraseña temporal: al entrar crea la suya
            usuario.perfil.save(update_fields=['debe_cambiar_clave'])
        if nueva_clave and respuesta.status_code < 300:
            # Contraseña restablecida por otra persona: queda en la bitácora (sin la clave) y la persona se entera
            from apps.core import accesos
            from apps.talento.auditoria import auditar
            auditar('Restableció la contraseña', f'{usuario.get_full_name() or usuario.username} ({usuario.username})', usuario=request.user)
            accesos.registrar('CLAVE', request, usuario, motivo=f'Restablecida por {request.user.get_full_name() or request.user.username}')
            if usuario.pk != request.user.pk:
                from apps.desempeno.servicios import avisar
                avisar([usuario], 'SEGURIDAD', 'Tu contraseña fue restablecida',
                       f'{request.user.get_full_name() or request.user.username} te puso una contraseña nueva el {timezone.localtime():%d/%m a las %H:%M}. '
                       'Si no lo pediste, avísale a la Dirección.', enlace='/mi-cuenta')
        if usuario.is_active != antes:  # la casilla «Cuenta activa» del formulario: mismo registro (quién, cuándo) y cierre de sesiones
            from . import cuentas
            cuentas.cambiar_estado(usuario, 'ACTIVA' if usuario.is_active else 'INACTIVA', request.user, motivo='Cambio desde «Editar persona»')
            respuesta.data['estado_cuenta'] = usuario.perfil.estado_cuenta
        return respuesta

    @action(detail=True, methods=['get'])
    def pendientes(self, request, pk=None):
        """Lo que la persona tiene a medias (tareas, compañera de tareas, revisiones, recurrentes, equipos): para decidir antes de apartarla."""
        from . import cuentas
        return Response(cuentas.pendientes(self.get_object()))

    @action(detail=True, methods=['post'])
    def estado(self, request, pk=None):
        """Suspender (temporal), dar de baja (inactiva), eliminar (oculta, sin borrar nada) o reactivar una cuenta.
        Con pendientes, hay que decir a quién pasarlos (`reasignar_a`) o confirmar que se quedan donde están (`dejar_pendientes`)."""
        from . import cuentas
        usuario = self.get_object()
        nuevo = (request.data.get('estado') or '').upper()
        if nuevo not in cuentas.ESTADOS:
            return Response({"estado": ["Elige: activa, suspendida, inactiva o eliminada."]}, status=status.HTTP_400_BAD_REQUEST)
        actual = usuario.perfil.estado_cuenta
        if nuevo == actual:
            return Response({"detail": f"La cuenta ya está {cuentas.ETIQUETA[actual].lower()}."}, status=status.HTTP_400_BAD_REQUEST)
        # «Personas» (directorio) suspende y da de baja; eliminar y reactivar una cuenta eliminada es de «Personas y accesos»
        if self._limitado() and (nuevo == 'ELIMINADA' or actual == 'ELIMINADA'):
            return Response({"detail": "Con el permiso «Personas» puedes suspender, dar de baja o reactivar; eliminar lo hace «Personas y accesos»."},
                            status=status.HTTP_403_FORBIDDEN)
        if usuario.pk == request.user.pk:
            return Response({"detail": "No puedes cambiar el estado de tu propia cuenta."}, status=status.HTTP_400_BAD_REQUEST)
        if nuevo != 'ACTIVA':
            motivo_bloqueo = self._proteger(usuario, activo=False)
            if motivo_bloqueo:
                return Response({"detail": motivo_bloqueo}, status=status.HTTP_400_BAD_REQUEST)
            motivo = (request.data.get('motivo') or '').strip()
            if len(motivo) < 3:
                return Response({"motivo": ["Escribe el motivo (queda en el historial)."]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            motivo = ''
        hasta = None
        if nuevo == 'SUSPENDIDA' and request.data.get('hasta'):
            from django.utils.dateparse import parse_date
            hasta = parse_date(str(request.data['hasta']))
            if hasta is None or hasta <= timezone.localdate():
                return Response({"hasta": ["Elige una fecha futura (o déjala vacía para suspender sin fecha de fin)."]}, status=status.HTTP_400_BAD_REQUEST)
        reasignado = None
        if actual == 'ACTIVA' and nuevo != 'ACTIVA':
            p = cuentas.pendientes(usuario)
            destino = None
            if request.data.get('reasignar_a'):
                destino = User.objects.filter(pk=request.data['reasignar_a'], is_active=True).exclude(pk=usuario.pk).first()
                if destino is None:
                    return Response({"reasignar_a": ["Elige a una persona activa para recibir sus pendientes."]}, status=status.HTTP_400_BAD_REQUEST)
            if cuentas.hay_pendientes(p) and destino is None and not request.data.get('dejar_pendientes'):
                return Response({"detail": "Esta persona tiene pendientes. Pásalos a otra persona o confirma que se queden como están.",
                                 "pendientes": p, "requiere_decision": True}, status=status.HTTP_409_CONFLICT)
            if destino is not None:
                reasignado = cuentas.reasignar(usuario, destino, request.user)
        cuentas.cambiar_estado(usuario, nuevo, request.user, motivo=motivo, hasta=hasta)
        usuario.refresh_from_db()
        datos = self.get_serializer(usuario).data
        return Response({**datos, 'reasignado': reasignado})

    def destroy(self, request, *args, **kwargs):
        usuario = self.get_object()
        if self._limitado():
            return Response({"detail": "Con el permiso «Personas» solo puedes desactivar cuentas, no borrarlas."}, status=status.HTTP_403_FORBIDDEN)
        # El borrado definitivo es solo de la Dirección, y solo de una cuenta que ya está «Eliminada» (dos pasos) y sin historial
        from apps.desempeno.permisos import es_administrador
        if not (request.user.is_superuser or es_administrador(request.user)):
            return Response({"detail": "El borrado definitivo es solo de la Dirección. Puedes dejar la cuenta como eliminada (oculta, sin perder su historial)."},
                            status=status.HTTP_403_FORBIDDEN)
        if usuario.perfil.estado_cuenta != 'ELIMINADA':
            return Response({"detail": "Primero deja la cuenta como «Eliminada»; el borrado definitivo es el último paso."}, status=status.HTTP_400_BAD_REQUEST)
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
    from apps.core.permisos import areas_ocultas
    ocultas = areas_ocultas(request.user)
    puestos = list(_puestos())
    from .estructura import situacion
    nodos = {p.id: {
        'id': p.id, 'nombre': p.nombre, 'departamento': p.departamento.nombre, 'departamento_id': p.departamento_id,
        'funciones': (p.funciones_principales or '').strip()[:260], 'unidad': p.unidad,
        'coordina_con': [x.id for x in p.coordina_con.all()], 'situacion': situacion(p),
        'cubre': [pf.user.get_full_name() or pf.user.username for pf in p.perfiles_adicionales.all() if pf.user.is_active and p.departamento_id not in ocultas],
        'personas': [{'id': pf.user_id, 'nombre': pf.user.get_full_name() or pf.user.username}
                     for pf in p.perfiles_usuarios.all() if pf.user.is_active and p.departamento_id not in ocultas],
        'hijos': [],
    } for p in puestos}
    raices = []
    for p in puestos:
        if p.supervisor_id and p.supervisor_id in nodos:
            nodos[p.supervisor_id]['hijos'].append(nodos[p.id])
        else:
            raices.append(nodos[p.id])
    sin_puesto = User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=True).count()
    from apps.desempeno.permisos import es_administrador
    from .estructura import estado_version
    return Response({'raices': raices, 'sin_puesto': sin_puesto, **estado_version(), 'puede_aprobar': es_administrador(request.user)})


@api_view(['GET'])
def matriz_view(request):
    """Matriz de reporte y coordinación (todos la consultan: «¿a quién le reporto?, ¿con quién coordino?, ¿por dónde escalo?»).
    ?formato=xlsx la descarga en Excel (editable), con el registro de cambios."""
    from django.http import HttpResponse
    from apps.core.permisos import areas_ocultas
    from .estructura import estado_version, excel, matriz, revision
    filas = matriz()
    if areas_ocultas(request.user):   # las personas de áreas que no ve quedan fuera (los cargos sí se ven)
        ocultas = {d for d in PuestoDeTrabajo.objects.filter(departamento_id__in=areas_ocultas(request.user)).values_list('nombre', flat=True)}
        for f in filas:
            if f['puesto'] in ocultas:
                f['personas'], f['cubre'] = [], []
    estado = estado_version()
    if request.query_params.get('formato') == 'xlsx':
        r = HttpResponse(excel(filas, estado['version']), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        r['Content-Disposition'] = 'attachment; filename="matriz-reporte-coordinacion.xlsx"'
        return r
    return Response({'filas': filas, 'revision': revision(filas), **estado})


@api_view(['GET', 'POST'])
def versiones_view(request):
    """GET: versiones y registro de cambios. POST {vigente_desde, notas}: Dirección General aprueba la versión que se comunica."""
    from datetime import date
    from apps.desempeno.permisos import es_administrador
    from .estructura import CAMPOS, aprobar
    from .models import CambioOrganigrama, VersionOrganigrama
    if request.method == 'POST':
        if not es_administrador(request.user):
            return Response({'detail': 'Solo Dirección General aprueba una versión del organigrama.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            vigente = date.fromisoformat(request.data.get('vigente_desde')) if request.data.get('vigente_desde') else None
        except ValueError:
            return Response({'vigente_desde': ['Fecha no válida.']}, status=status.HTTP_400_BAD_REQUEST)
        v = aprobar(request.user, vigente, (request.data.get('notas') or '')[:2000])
        return Response({'numero': v.numero, 'vigente_desde': v.vigente_desde}, status=status.HTTP_201_CREATED)
    nombre = lambda u: (u.get_full_name() or u.username) if u else None  # noqa: E731
    return Response({
        'versiones': [{'numero': v.numero, 'vigente_desde': v.vigente_desde, 'aprobada_por': nombre(v.aprobada_por), 'aprobada_en': v.aprobada_en,
                       'notas': v.notas, 'cambios': v.cambios.count()} for v in VersionOrganigrama.objects.select_related('aprobada_por')],
        'cambios': [{'id': c.id, 'fecha': c.fecha, 'puesto': c.puesto_nombre, 'campo': CAMPOS.get(c.campo, c.campo), 'antes': c.antes,
                     'despues': c.despues, 'usuario': nombre(c.usuario), 'version': c.version.numero if c.version_id else None}
                    for c in CambioOrganigrama.objects.select_related('usuario', 'version')[:500]],
    })
