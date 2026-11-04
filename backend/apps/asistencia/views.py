import csv
from datetime import datetime

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.desempeno.permisos import EsAdministrador, LecturaOAdministrador, equipo_gestionable, es_administrador, puede_gestionar, revisores_de
from apps.desempeno.servicios import avisar
from apps.desempeno.views import periodo_desde_mes
from . import servicios
from .models import AsignacionHorario, Ausencia, Feriado, Horario, Marcaje


def _nombre(u):
    return u.get_full_name() or u.username


def _ip(request):
    return (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')) or None


def _persona(u):
    perfil = getattr(u, 'perfil', None)
    puesto = getattr(perfil, 'puesto_trabajo', None)
    return {'id': u.id, 'nombre': _nombre(u), 'puesto': puesto.nombre if puesto else None,
            'departamento': puesto.departamento.nombre if puesto else None}


def _rango(request):
    inicio, fin = servicios.mes(periodo_desde_mes(request.query_params.get('mes')))
    return inicio, fin


def _ver_persona(request, usuario):
    if usuario.pk != request.user.pk and not puede_gestionar(request.user, usuario, 'asistencia.ver'):
        raise PermissionDenied("Solo ves la asistencia de tu equipo.")


# ------------------------------------------------------------------ Mi jornada
@api_view(['GET'])
def estado_view(request):
    estado, ultimo = servicios.estado_actual(request.user)
    horario, _ = servicios.horario_de(request.user)
    return Response({
        'estado': estado, 'siguientes': servicios.SIGUIENTES[estado],
        'ultimo': {'tipo': ultimo.tipo, 'momento': ultimo.momento} if ultimo else None,
        'hoy': servicios.jornada(request.user, timezone.localdate()),
        'horario': {'id': horario.id, 'nombre': horario.nombre} if horario else None,
        'donde_marca': _donde(request.user),
    })


def _donde(user):
    from .lugar import donde_marca
    return donde_marca(user)


@api_view(['POST'])
def marcar_view(request):
    tipo = request.data.get('tipo')
    if tipo not in dict(Marcaje.TIPOS):
        return Response({'detail': 'Marcaje no válido.'}, status=400)
    from .lugar import validar
    lugar, error = validar(request.user, request.data)
    if error:
        return Response({'detail': error, 'lugar': True}, status=400)
    origen = lugar.pop('origen') or ('MOVIL' if request.data.get('movil') else 'WEB')
    marcaje, error = servicios.marcar(request.user, tipo, origen, _ip(request), request.data.get('motivo') or '', request.data.get('nota') or '',
                                      lugar=lugar)
    if error:
        return Response({'detail': error}, status=400)
    return Response({'ok': True, 'tipo': marcaje.tipo, 'momento': marcaje.momento,
                     'sitio': marcaje.sitio.nombre if marcaje.sitio_id else None}, status=201)


@api_view(['GET'])
def mi_mes_view(request):
    desde, hasta = _rango(request)
    usuario = request.user
    if request.query_params.get('usuario'):
        if not str(request.query_params['usuario']).isdigit():
            return Response({'usuario': 'Debe ser un número.'}, status=400)
        usuario = get_object_or_404(User, pk=request.query_params['usuario'])
        _ver_persona(request, usuario)
    res = servicios.resumen(usuario, desde, hasta)
    return Response({'persona': _persona(usuario), 'resumen': res, 'adherencia': servicios.adherencia(res),
                     'dias': servicios.jornadas(usuario, desde, hasta)})


# ------------------------------------------------------------------ Equipo
def _equipo(request):
    qs = equipo_gestionable(request.user, 'asistencia.ver').select_related('perfil__puesto_trabajo__departamento').order_by('first_name', 'last_name')
    if not es_administrador(request.user) and not qs.exists():
        raise PermissionDenied("Esta vista es para quien ve la asistencia de su equipo.")
    return qs


@api_view(['GET'])
def hoy_view(request):
    """Quién llegó, quién está tarde, en pausa o ausente hoy."""
    from apps.monitoreo.servicios import ultimo_contacto_por_usuario
    hoy = timezone.localdate()
    personas = list(_equipo(request))
    from apps.desempeno.permisos import tiene
    # lo que hace la computadora en este momento es monitoreo: solo Dirección y Tecnología
    contactos = ultimo_contacto_por_usuario([p.pk for p in personas]) if tiene(request.user, 'monitoreo.ver') else {}
    filas = []
    for u in personas:
        j = servicios.jornada(u, hoy)
        filas.append({**_persona(u), **{k: j[k] for k in ('estado', 'llegada', 'entrada', 'salida', 'tardanza', 'trabajados', 'pausa', 'turno', 'ausencia')},
                      'pc': contactos.get(u.pk)})
    orden = {'TARDE_SIN_MARCAR': 0, 'AUSENTE': 1, 'EN_PAUSA': 2, 'TRABAJANDO': 3, 'PRESENTE': 4, 'PENDIENTE': 5, 'PERMISO': 6}
    filas.sort(key=lambda f: (orden.get(f['estado'], 9), f['nombre']))
    conteo = {}
    for f in filas:
        conteo[f['estado']] = conteo.get(f['estado'], 0) + 1
    return Response({'fecha': hoy, 'conteo': conteo, 'tardes': sum(1 for f in filas if f['llegada'] == 'TARDE'), 'personas': filas})


def _reporte(request):
    desde, hasta = _rango(request)
    filas = []
    for u in _equipo(request):
        res = servicios.resumen(u, desde, hasta)
        filas.append({**_persona(u), **res, 'adherencia': servicios.adherencia(res)})
    return desde, filas


@api_view(['GET'])
def reporte_view(request):
    desde, filas = _reporte(request)
    if request.query_params.get('formato') == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="asistencia-{desde:%Y-%m}.csv"'
        resp.write('﻿')
        w = csv.writer(resp)
        w.writerow(['Colaborador', 'Puesto', 'Departamento', 'Días laborables', 'Días presentes', 'A tiempo', 'Tardanzas',
                    'Minutos tarde', 'Ausencias', 'Permisos', 'Salidas tempranas', 'Días sin marcar salida',
                    'Horas programadas', 'Horas trabajadas', 'Horas extra', 'Puntualidad %', 'Asistencia %', 'Adherencia %'])
        for f in filas:
            w.writerow([f['nombre'], f['puesto'] or '', f['departamento'] or '', f['dias_laborables'], f['dias_presentes'], f['dias_a_tiempo'],
                        f['tardanzas'], f['minutos_tarde'], f['ausencias'], f['permisos'], f['salidas_tempranas'], f['sin_salida'],
                        round(f['minutos_programados'] / 60, 1), round(f['minutos_trabajados'] / 60, 1), round(f['minutos_extra'] / 60, 1),
                        f['puntualidad'] if f['puntualidad'] is not None else '', f['asistencia'] if f['asistencia'] is not None else '',
                        f['adherencia'] if f['adherencia'] is not None else ''])
        return resp
    return Response({'mes': f'{desde:%Y-%m}', 'personas': filas})


# ------------------------------------------------------------------ Correcciones
class MarcajeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marcaje
        fields = ['id', 'usuario', 'tipo', 'momento', 'origen', 'motivo_pausa', 'nota', 'corregido_por', 'fecha_creacion']
        read_only_fields = ['origen', 'corregido_por', 'fecha_creacion']


class MarcajeViewSet(viewsets.ModelViewSet):
    """Corrección manual de marcajes (olvidó marcar). Lo hace su supervisor o la administración; queda registrado."""
    serializer_class = MarcajeSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        qs = Marcaje.objects.filter(usuario__in=equipo_gestionable(self.request.user, 'asistencia.ver'))
        if str(self.request.query_params.get('usuario', '')).isdigit():
            qs = qs.filter(usuario_id=self.request.query_params['usuario'])
        return qs

    def _revisar(self, usuario):
        if usuario.pk == self.request.user.pk or not puede_gestionar(self.request.user, usuario, 'asistencia.corregir'):
            raise PermissionDenied("Corrige marcajes quien tiene ese permiso sobre la persona, nunca uno mismo.")

    def perform_create(self, serializer):
        self._revisar(serializer.validated_data['usuario'])
        if not serializer.validated_data.get('nota'):
            raise serializers.ValidationError({'nota': 'Explica la corrección (p. ej. «olvidó marcar la salida»).'})
        serializer.save(origen='MANUAL', corregido_por=self.request.user)

    def perform_update(self, serializer):
        self._revisar(serializer.instance.usuario)
        nuevo = serializer.validated_data.get('usuario')
        if nuevo and nuevo.pk != serializer.instance.usuario_id:
            raise PermissionDenied("Un marcaje no se pasa a otra persona: bórralo y créalo en la persona correcta.")
        serializer.save(origen='MANUAL', corregido_por=self.request.user)

    def perform_destroy(self, instance):
        self._revisar(instance.usuario)
        instance.delete()


# ------------------------------------------------------------------ Horarios y feriados
class HorarioSerializer(serializers.ModelSerializer):
    personas = serializers.SerializerMethodField()

    class Meta:
        model = Horario
        fields = ['id', 'nombre', 'dias', 'almuerzo_minutos', 'tolerancia_minutos', 'por_defecto', 'activo', 'personas']

    def get_personas(self, obj):
        return obj.asignaciones.count()

    def validate_dias(self, dias):
        limpio = {}
        for dia, horas in (dias or {}).items():
            if str(dia) not in {str(i) for i in range(7)} or not horas:
                continue
            try:
                a, b = (datetime.strptime(h, '%H:%M').time() for h in horas)
            except (TypeError, ValueError):
                raise serializers.ValidationError('Usa horas como «08:00».')
            if b <= a:
                raise serializers.ValidationError('La salida debe ser después de la entrada.')
            limpio[str(dia)] = [a.strftime('%H:%M'), b.strftime('%H:%M')]
        if not limpio:
            raise serializers.ValidationError('El horario necesita al menos un día.')
        return limpio

    def save(self, **kwargs):
        obj = super().save(**kwargs)
        if obj.por_defecto:
            Horario.objects.exclude(pk=obj.pk).update(por_defecto=False)
        return obj


class HorarioViewSet(viewsets.ModelViewSet):
    queryset = Horario.objects.all()
    serializer_class = HorarioSerializer
    permission_classes = [LecturaOAdministrador]

    def perform_destroy(self, instance):
        if instance.asignaciones.exists():
            raise PermissionDenied("Hay personas con este horario: cámbialas antes de borrarlo.")
        instance.delete()


class FeriadoViewSet(viewsets.ModelViewSet):
    queryset = Feriado.objects.all()
    permission_classes = [LecturaOAdministrador]

    class _S(serializers.ModelSerializer):
        class Meta:
            model = Feriado
            fields = ['id', 'fecha', 'nombre']
    serializer_class = _S


@api_view(['GET', 'POST'])
@permission_classes([EsAdministrador])
def asignaciones_view(request):
    """GET: horario de cada persona. POST {usuarios: [ids], horario, marca_obligatoria}: asigna en bloque."""
    if request.method == 'POST':
        horario = get_object_or_404(Horario, pk=request.data.get('horario'))
        ids = request.data.get('usuarios') or []
        for u in User.objects.filter(pk__in=ids):
            defaults = {'horario': horario, 'marca_obligatoria': bool(request.data.get('marca_obligatoria', True))}
            if request.data.get('donde_marca') in dict(AsignacionHorario.LUGARES):
                defaults['donde_marca'] = request.data['donde_marca']
            AsignacionHorario.objects.update_or_create(usuario=u, defaults=defaults)
        return Response({'asignados': len(ids)})
    asign = {a.usuario_id: a for a in AsignacionHorario.objects.select_related('horario')}
    defecto = Horario.objects.filter(por_defecto=True).first()
    filas = []
    for u in User.objects.filter(is_active=True).select_related('perfil__puesto_trabajo__departamento').order_by('first_name'):
        a = asign.get(u.pk)
        h = a.horario if a else defecto
        filas.append({**_persona(u), 'horario': h.id if h else None, 'horario_nombre': h.nombre if h else None,
                      'propio': bool(a), 'marca_obligatoria': a.marca_obligatoria if a else True,
                      'donde_marca': a.donde_marca if a else 'LIBRE'})
    return Response(filas)


# ------------------------------------------------------------------ Permisos y vacaciones
class AusenciaSerializer(serializers.ModelSerializer):
    persona = serializers.SerializerMethodField()
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    revisada_por_nombre = serializers.SerializerMethodField()
    puede_revisar = serializers.SerializerMethodField()
    dias = serializers.SerializerMethodField()

    class Meta:
        model = Ausencia
        fields = ['id', 'usuario', 'persona', 'tipo', 'tipo_nombre', 'desde', 'hasta', 'dias', 'motivo', 'estado',
                  'revisada_por_nombre', 'comentario_revision', 'puede_revisar', 'fecha_creacion']
        read_only_fields = ['usuario', 'estado', 'comentario_revision']

    def get_persona(self, obj):
        return _nombre(obj.usuario)

    def get_revisada_por_nombre(self, obj):
        return _nombre(obj.revisada_por) if obj.revisada_por else None

    def get_dias(self, obj):
        return (obj.hasta - obj.desde).days + 1

    def get_puede_revisar(self, obj):
        u = self.context['request'].user
        return obj.estado == 'PENDIENTE' and obj.usuario_id != u.pk and puede_gestionar(u, obj.usuario, 'asistencia.ver')

    def validate(self, data):
        if data.get('hasta') and data.get('desde') and data['hasta'] < data['desde']:
            raise serializers.ValidationError({'hasta': 'La fecha final es antes de la inicial.'})
        return data


class AusenciaViewSet(viewsets.ModelViewSet):
    serializer_class = AusenciaSerializer
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        u = self.request.user
        from django.db.models import Q
        qs = Ausencia.objects.select_related('usuario', 'revisada_por')
        if self.request.query_params.get('ver') == 'equipo':
            return qs.filter(usuario__in=equipo_gestionable(u, 'asistencia.ver')).exclude(usuario=u)
        return qs.filter(Q(usuario=u))

    def perform_create(self, serializer):
        a = serializer.save(usuario=self.request.user)
        avisar(revisores_de(self.request.user, 'asistencia.ver'), 'ASISTENCIA', f'{_nombre(self.request.user)} pide {a.get_tipo_display().lower()}',
               f'Del {a.desde:%d/%m} al {a.hasta:%d/%m}. {a.motivo}'.strip(), enlace='/asistencia?ver=permisos', excepto=self.request.user)

    def perform_destroy(self, instance):
        if instance.usuario_id != self.request.user.pk or instance.estado != 'PENDIENTE':
            raise PermissionDenied("Solo puedes retirar tus solicitudes pendientes.")
        instance.delete()


@api_view(['POST'])
def revisar_ausencia_view(request, pk):
    a = get_object_or_404(Ausencia, pk=pk)
    if a.usuario_id == request.user.pk or not puede_gestionar(request.user, a.usuario, 'asistencia.ver'):
        raise PermissionDenied("La aprueba su supervisor o la administración.")
    if a.estado != 'PENDIENTE':
        return Response({'detail': 'Esa solicitud ya fue revisada.'}, status=400)
    aprobar = bool(request.data.get('aprobar'))
    a.estado = 'APROBADA' if aprobar else 'RECHAZADA'
    a.revisada_por = request.user
    a.comentario_revision = (request.data.get('comentario') or '')[:255]
    a.save()
    avisar([a.usuario], 'ASISTENCIA', f'Tu solicitud de {a.get_tipo_display().lower()} fue {"aprobada" if aprobar else "rechazada"}',
           a.comentario_revision, enlace='/asistencia?ver=permisos', excepto=request.user)
    return Response(AusenciaSerializer(a, context={'request': request}).data)


# ------------------------------------------------------------------ Lugares de marcaje y pantalla del QR
class SitioSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import SitioMarcaje
        model = SitioMarcaje
        fields = ['id', 'nombre', 'latitud', 'longitud', 'radio_m', 'clave_pantalla', 'activo']
        read_only_fields = ['clave_pantalla']

    def validate_radio_m(self, v):
        if not 30 <= v <= 2000:
            raise serializers.ValidationError('Entre 30 y 2000 metros.')
        return v


class SitioViewSet(viewsets.ModelViewSet):
    serializer_class = SitioSerializer
    permission_classes = [EsAdministrador]

    def get_queryset(self):
        from .models import SitioMarcaje
        return SitioMarcaje.objects.all()

    def perform_create(self, serializer):
        import secrets
        serializer.save(clave_pantalla=secrets.token_urlsafe(24))


@api_view(['POST'])
@permission_classes([EsAdministrador])
def sitio_nueva_clave_view(request, pk):
    """Si el enlace de la pantalla se compartió por error: uno nuevo (el anterior deja de servir)."""
    import secrets
    from .models import SitioMarcaje
    s = get_object_or_404(SitioMarcaje, pk=pk)
    s.clave_pantalla = secrets.token_urlsafe(24)
    s.save(update_fields=['clave_pantalla'])
    return Response(SitioSerializer(s).data)


@api_view(['GET'])
@permission_classes([])
@authentication_classes([])
def pantalla_qr_view(request, clave):
    """La pantalla de la recepción (sin sesión, con su enlace secreto): el QR del momento, que cambia cada 30 s."""
    from .lugar import VENTANA, token
    from .models import SitioMarcaje
    from apps.core.seguridad import qr_svg
    import time as _t
    s = SitioMarcaje.objects.filter(clave_pantalla=clave, activo=True).first()
    if s is None:
        return Response({'detail': 'Este enlace ya no sirve.'}, status=404)
    url = request.build_absolute_uri(f'/marcar?s={s.pk}&t={token(s)}')
    return Response({'sitio': s.nombre, 'qr': qr_svg(url), 'cambia_en': VENTANA - int(_t.time()) % VENTANA})
