from django.utils import timezone
from rest_framework import serializers

from .models import SERVICIOS, MovimientoComercial, Oportunidad, SolicitudServicio
from .permisos import puede_cambiar_solicitud


def nombre(u):
    return (u.get_full_name() or u.username) if u else None


class MovimientoSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = MovimientoComercial
        fields = ['id', 'tipo', 'tipo_nombre', 'estado_antes', 'estado_despues', 'texto', 'cambios', 'usuario_nombre', 'fecha']

    def get_usuario_nombre(self, o):
        return nombre(o.usuario)


class SolicitudSerializer(serializers.ModelSerializer):
    servicio_nombre = serializers.CharField(read_only=True)
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    departamento_nombre = serializers.CharField(source='departamento.nombre', read_only=True)
    responsable_nombre = serializers.SerializerMethodField()
    creado_por_nombre = serializers.SerializerMethodField()
    oportunidad_codigo = serializers.CharField(source='oportunidad.codigo', read_only=True, default=None)
    oportunidad_titulo = serializers.CharField(source='oportunidad.titulo', read_only=True, default=None)
    proyecto_codigo = serializers.CharField(source='proyecto.codigo', read_only=True, default=None)
    orden_codigo = serializers.CharField(source='orden.codigo', read_only=True, default=None)
    puedo_cambiar = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudServicio
        fields = ['id', 'codigo', 'cliente', 'cliente_nombre', 'oportunidad', 'oportunidad_codigo', 'oportunidad_titulo', 'servicio',
                  'servicio_detalle', 'servicio_nombre', 'departamento', 'departamento_nombre', 'descripcion', 'responsable',
                  'responsable_nombre', 'estado', 'estado_nombre', 'proyecto', 'proyecto_codigo', 'orden', 'orden_codigo',
                  'creado_por_nombre', 'fecha_creacion', 'fecha_modificacion', 'puedo_cambiar']
        read_only_fields = ['codigo', 'proyecto', 'orden', 'cliente']
        extra_kwargs = {'departamento': {'required': False}}

    def get_responsable_nombre(self, o):
        return nombre(o.responsable)

    def get_creado_por_nombre(self, o):
        return nombre(o.creado_por)

    def get_puedo_cambiar(self, o):
        r = self.context.get('request')
        return bool(r and puede_cambiar_solicitud(r.user, o))


class OportunidadSerializer(serializers.ModelSerializer):
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    departamento_nombre = serializers.CharField(source='departamento.nombre', read_only=True, default=None)
    responsable_nombre = serializers.SerializerMethodField()
    creado_por_nombre = serializers.SerializerMethodField()
    servicios = serializers.SerializerMethodField()
    seguimiento_vencido = serializers.SerializerMethodField()

    class Meta:
        model = Oportunidad
        fields = ['id', 'codigo', 'cliente', 'cliente_nombre', 'titulo', 'necesidades', 'departamento', 'departamento_nombre',
                  'responsable', 'responsable_nombre', 'estado', 'estado_nombre', 'fecha_contacto', 'proximo_seguimiento',
                  'motivo_no_concretado', 'creado_por_nombre', 'fecha_creacion', 'fecha_modificacion', 'fecha_cierre', 'servicios',
                  'seguimiento_vencido']
        read_only_fields = ['codigo', 'fecha_cierre']

    def get_responsable_nombre(self, o):
        return nombre(o.responsable)

    def get_creado_por_nombre(self, o):
        return nombre(o.creado_por)

    def get_servicios(self, o):
        return [{'id': s.id, 'codigo': s.codigo, 'servicio': s.servicio_nombre, 'estado': s.estado, 'estado_nombre': s.get_estado_display(),
                 'departamento': s.departamento.nombre} for s in o.solicitudes.all()]

    def get_seguimiento_vencido(self, o):
        return bool(o.abierta and o.proximo_seguimiento and o.proximo_seguimiento <= timezone.localdate())

    def validate(self, datos):
        estado = datos.get('estado', getattr(self.instance, 'estado', 'NUEVO'))
        motivo = datos.get('motivo_no_concretado', getattr(self.instance, 'motivo_no_concretado', ''))
        if estado == 'NO_CONCRETADA' and not (motivo or '').strip():
            raise serializers.ValidationError({'motivo_no_concretado': "Explica por qué no se concretó."})
        return datos


SERVICIOS_LISTA = [{'codigo': k, 'nombre': v[0], 'departamento': v[1]} for k, v in SERVICIOS.items()]
