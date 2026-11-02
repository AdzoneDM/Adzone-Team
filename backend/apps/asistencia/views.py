import csv
from datetime import datetime

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import api_view, permission_classes
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
    if usuario.pk != request.user.pk and not puede_gestionar(request.user, usuario):
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
    })


@api_view(['POST'])
def marcar_view(request):
    tipo = request.data.get('tipo')
    if tipo not in dict(Marcaje.TIPOS):
        return Response({'detail': 'Marcaje no válido.'}, status=400)
    origen = 'MOVIL' if request.data.get('movil') else 'WEB'
    marcaje, error = servicios.marcar(request.user, tipo, origen, _ip(request), request.data.get('motivo') or '', request.data.get('nota') or '')
    if error:
        return Response({'detail': error}, status=400)
    return Response({'ok': True, 'tipo': marcaje.tipo, 'momento': marcaje.momento}, status=201)


@api_view(['GET'])
def mi_mes_view(request):
    desde, hasta = _rango(request)
    usuario = request.user
    if request.query_params.get('usuario'):
        usuario = get_object_or_404(User, pk=request.query_params['usuario'])
        _ver_persona(request, usuario)
    res = servicios.resumen(usuario, desde, hasta)
    return Response({'persona': _persona(usuario), 'resumen': res, 'adherencia': servicios.adherencia(res),
                     'dias': servicios.jornadas(usuario, desde, hasta)})


# ------------------------------------------------------------------ Equipo
def _equipo(request):
    qs = equipo_gestionable(request.user).select_related('perfil__puesto_trabajo__departamento').order_by('first_name', 'last_name')
    if not es_administrador(request.user) and not qs.exists():
        raise PermissionDenied("Esta vista es para supervisores y administración.")
    return qs


@api_view(['GET'])
def hoy_view(request):
    """Quién llegó, quién está tarde, en pausa o ausente hoy."""
    from apps.monitoreo.servicios import ultimo_contacto_por_usuario
    hoy = timezone.localdate()
    personas = list(_equipo(request))
    contactos = ultimo_contacto_por_usuario([p.pk for p in personas])
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
        qs = Marcaje.objects.filter(usuario__in=equipo_gestionable(self.request.user))
        if self.request.query_params.get('usuario'):
            qs = qs.filter(usuario_id=self.request.query_params['usuario'])
        return qs

    def _revisar(self, usuario):
        if usuario.pk == self.request.user.pk or not puede_gestionar(self.request.user, usuario):
            raise PermissionDenied("Las correcciones las hace el supervisor o la administración, nunca uno mismo.")

    def perform_create(self, serializer):
        self._revisar(serializer.validated_data['usuario'])
        if not serializer.validated_data.get('nota'):
            raise serializers.ValidationError({'nota': 'Explica la corrección (p. ej. «olvidó marcar la salida»).'})
        serializer.save(origen='MANUAL', corregido_por=self.request.user)

    def perform_update(self, serializer):
        self._revisar(serializer.instance.usuario)
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
            AsignacionHorario.objects.update_or_create(usuario=u, defaults={
                'horario': horario, 'marca_obligatoria': bool(request.data.get('marca_obligatoria', True))})
        return Response({'asignados': len(ids)})
    asign = {a.usuario_id: a for a in AsignacionHorario.objects.select_related('horario')}
    defecto = Horario.objects.filter(por_defecto=True).first()
    filas = []
    for u in User.objects.filter(is_active=True).select_related('perfil__puesto_trabajo__departamento').order_by('first_name'):
        a = asign.get(u.pk)
        h = a.horario if a else defecto
        filas.append({**_persona(u), 'horario': h.id if h else None, 'horario_nombre': h.nombre if h else None,
                      'propio': bool(a), 'marca_obligatoria': a.marca_obligatoria if a else True})
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
        return obj.estado == 'PENDIENTE' and obj.usuario_id != u.pk and puede_gestionar(u, obj.usuario)

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
            return qs.filter(usuario__in=equipo_gestionable(u)).exclude(usuario=u)
        return qs.filter(Q(usuario=u))

    def perform_create(self, serializer):
        a = serializer.save(usuario=self.request.user)
        avisar(revisores_de(self.request.user), 'ASISTENCIA', f'{_nombre(self.request.user)} pide {a.get_tipo_display().lower()}',
               f'Del {a.desde:%d/%m} al {a.hasta:%d/%m}. {a.motivo}'.strip(), enlace='/asistencia?ver=permisos', excepto=self.request.user)

    def perform_destroy(self, instance):
        if instance.usuario_id != self.request.user.pk or instance.estado != 'PENDIENTE':
            raise PermissionDenied("Solo puedes retirar tus solicitudes pendientes.")
        instance.delete()


@api_view(['POST'])
def revisar_ausencia_view(request, pk):
    a = get_object_or_404(Ausencia, pk=pk)
    if a.usuario_id == request.user.pk or not puede_gestionar(request.user, a.usuario):
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
