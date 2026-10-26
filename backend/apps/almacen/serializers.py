from rest_framework import serializers

from apps.operaciones.permisos import es_almacen, es_coordinacion, es_finanzas
from .models import LineaVale, Material, MovimientoInventario, ValeMaterial


def _nombre(u):
    return (u.get_full_name() or u.username) if u else None


def _ve_costos(ser):
    request = ser.context.get('request')
    u = getattr(request, 'user', None)
    return bool(u and (es_almacen(u) or es_finanzas(u) or es_coordinacion(u)))


class MaterialSerializer(serializers.ModelSerializer):
    bajo_minimo = serializers.BooleanField(read_only=True)

    class Meta:
        model = Material
        fields = ['id', 'codigo', 'nombre', 'unidad', 'existencia', 'punto_reposicion', 'costo_unitario', 'proveedor', 'activo',
                  'bajo_minimo']
        read_only_fields = ['existencia']

    def to_representation(self, m):
        d = super().to_representation(m)
        if not _ve_costos(self):
            d['costo_unitario'] = None
        return d


class LineaValeSerializer(serializers.ModelSerializer):
    material_nombre = serializers.CharField(source='material.nombre', read_only=True)
    material_codigo = serializers.CharField(source='material.codigo', read_only=True)
    unidad = serializers.CharField(source='material.unidad', read_only=True)
    existencia = serializers.DecimalField(source='material.existencia', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = LineaVale
        fields = ['id', 'material', 'material_nombre', 'material_codigo', 'unidad', 'existencia', 'cantidad_solicitada',
                  'cantidad_despachada', 'lote', 'costo_unitario', 'cantidad_devuelta', 'desperdicio', 'causa_desperdicio']


class ValeSerializer(serializers.ModelSerializer):
    lineas = LineaValeSerializer(many=True, read_only=True)
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    orden_codigo = serializers.CharField(source='orden.codigo', read_only=True)
    oa_numero = serializers.CharField(source='oa.numero', read_only=True, default=None)
    area = serializers.CharField(source='oa.area', read_only=True, default=None)
    cliente = serializers.CharField(source='orden.cliente.nombre', read_only=True)
    solicitado_por_nombre = serializers.SerializerMethodField()
    autorizado_por_nombre = serializers.SerializerMethodField()
    despachado_por_nombre = serializers.SerializerMethodField()
    recibido_por_nombre = serializers.SerializerMethodField()
    costo_total = serializers.SerializerMethodField()

    class Meta:
        model = ValeMaterial
        fields = ['id', 'numero', 'orden', 'orden_codigo', 'oa', 'oa_numero', 'area', 'cliente', 'estado', 'estado_nombre',
                  'solicitado_por_nombre', 'autorizado_por_nombre', 'despachado_por_nombre', 'recibido_por_nombre', 'fecha',
                  'fecha_autorizado', 'fecha_despacho', 'fecha_cierre', 'notas', 'lineas', 'costo_total']

    def get_solicitado_por_nombre(self, v):
        return _nombre(v.solicitado_por)

    def get_autorizado_por_nombre(self, v):
        return _nombre(v.autorizado_por)

    def get_despachado_por_nombre(self, v):
        return _nombre(v.despachado_por)

    def get_recibido_por_nombre(self, v):
        return _nombre(v.recibido_por)

    def get_costo_total(self, v):
        return v.costo_total if _ve_costos(self) else None

    def to_representation(self, v):
        d = super().to_representation(v)
        if not _ve_costos(self):
            for linea in d['lineas']:
                linea['costo_unitario'] = None
        return d


class MovimientoSerializer(serializers.ModelSerializer):
    material_nombre = serializers.CharField(source='material.nombre', read_only=True)
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    usuario_nombre = serializers.SerializerMethodField()
    vale_numero = serializers.CharField(source='vale.numero', read_only=True, default=None)

    class Meta:
        model = MovimientoInventario
        fields = ['id', 'material', 'material_nombre', 'tipo', 'tipo_nombre', 'cantidad', 'costo_unitario', 'vale', 'vale_numero',
                  'nota', 'usuario_nombre', 'fecha']

    def get_usuario_nombre(self, m):
        return _nombre(m.usuario)
