import os
from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import SITUACIONES, AdjuntoFactura, Cotizacion, Factura, Gasto, LineaCotizacion, LineaFactura, Pago


class LineaSerializer(serializers.Serializer):
    descripcion = serializers.CharField(max_length=255)
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    precio = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'))
    aplica_itbis = serializers.BooleanField(default=True)
    importe = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)


class DocumentoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    cliente_rnc = serializers.CharField(source='cliente.rnc', read_only=True)
    proyecto_nombre = serializers.CharField(source='proyecto.nombre', read_only=True, default=None)
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    creada_por_nombre = serializers.SerializerMethodField()
    lineas = LineaSerializer(many=True)

    MODELO_LINEA = None
    BASE = ['id', 'numero', 'cliente', 'cliente_nombre', 'cliente_rnc', 'proyecto', 'proyecto_nombre', 'titulo', 'fecha',
            'moneda', 'notas', 'subtotal', 'itbis', 'total', 'estado', 'estado_nombre', 'lineas', 'creada_por_nombre',
            'fecha_creacion', 'cashflow_id', 'cashflow_numero', 'cashflow_estado', 'cashflow_sincronizado']

    def get_creada_por_nombre(self, o):
        return (o.creada_por.get_full_name() or o.creada_por.username) if o.creada_por else None

    def validate_lineas(self, v):
        if not v:
            raise serializers.ValidationError("Agrega al menos una línea.")
        return v

    def validate(self, attrs):
        if self.instance and self.instance.estado != 'BORRADOR' and set(attrs) - {'notas', 'ncf', 'vencimiento', 'valida_hasta'}:
            raise serializers.ValidationError("Solo se cambia un documento en borrador.")
        return attrs

    def _guardar_lineas(self, doc, lineas):
        if lineas is None:
            return
        doc.lineas.all().delete()
        for i, l in enumerate(lineas):
            self.MODELO_LINEA.objects.create(documento=doc, orden=i, **l)
        doc.recalcular()

    @transaction.atomic
    def create(self, validated_data):
        lineas = validated_data.pop('lineas', [])
        doc = super().create(validated_data)
        self._guardar_lineas(doc, lineas)
        return doc

    @transaction.atomic
    def update(self, instance, validated_data):
        lineas = validated_data.pop('lineas', None)
        doc = super().update(instance, validated_data)
        self._guardar_lineas(doc, lineas)
        return doc


class CotizacionSerializer(DocumentoSerializer):
    MODELO_LINEA = LineaCotizacion

    class Meta:
        model = Cotizacion
        fields = DocumentoSerializer.BASE + ['valida_hasta', 'condiciones']
        read_only_fields = ['numero', 'subtotal', 'itbis', 'total', 'estado', 'cashflow_id', 'cashflow_numero', 'cashflow_estado',
                            'cashflow_sincronizado']


class PagoSerializer(serializers.ModelSerializer):
    metodo_nombre = serializers.CharField(source='get_metodo_display', read_only=True)
    tiene_comprobante = serializers.SerializerMethodField()
    comprobante_es_imagen = serializers.SerializerMethodField()

    class Meta:
        model = Pago
        fields = ['id', 'fecha', 'monto', 'metodo', 'metodo_nombre', 'referencia', 'tiene_comprobante', 'comprobante_es_imagen']

    def get_tiene_comprobante(self, p):
        return bool(p.comprobante)

    def get_comprobante_es_imagen(self, p):
        return bool(p.comprobante) and not p.comprobante.name.lower().endswith('.pdf')

    def validate_monto(self, v):
        if v <= 0:
            raise serializers.ValidationError("El monto tiene que ser mayor que cero.")
        return v


class AdjuntoSerializer(serializers.ModelSerializer):
    subido_por_nombre = serializers.SerializerMethodField()
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    extension = serializers.SerializerMethodField()
    vista_previa = serializers.SerializerMethodField()

    class Meta:
        model = AdjuntoFactura
        fields = ['id', 'nombre', 'es_imagen', 'tipo', 'tipo_nombre', 'extension', 'vista_previa', 'nota', 'subido_por_nombre', 'fecha_creacion']

    def get_extension(self, a):
        return os.path.splitext(a.nombre or a.archivo.name)[1].lower().lstrip('.')

    def get_vista_previa(self, a):
        """Qué se puede mostrar en el navegador: la imagen, el PDF; los demás documentos solo se descargan."""
        return 'imagen' if a.es_imagen else 'pdf' if self.get_extension(a) == 'pdf' else None

    def get_subido_por_nombre(self, a):
        return (a.subido_por.get_full_name() or a.subido_por.username) if a.subido_por else None


class FacturaSerializer(DocumentoSerializer):
    MODELO_LINEA = LineaFactura
    saldo = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    vencida = serializers.BooleanField(read_only=True)
    dias_para_vencer = serializers.IntegerField(read_only=True)
    situacion = serializers.CharField(read_only=True)
    situacion_nombre = serializers.SerializerMethodField()
    pagos = PagoSerializer(many=True, read_only=True)
    adjuntos = AdjuntoSerializer(many=True, read_only=True)
    orden_numero = serializers.CharField(source='orden.codigo', read_only=True, default=None)
    cotizacion_numero = serializers.CharField(source='cotizacion.numero', read_only=True, default=None)

    def get_situacion_nombre(self, f):
        return SITUACIONES[f.situacion]

    class Meta:
        model = Factura
        fields = DocumentoSerializer.BASE + ['vencimiento', 'ncf', 'orden', 'orden_numero', 'cotizacion', 'cotizacion_numero',
                                             'pagado', 'saldo', 'vencida', 'dias_para_vencer', 'situacion', 'situacion_nombre', 'pagos', 'adjuntos', 'es_anticipo']
        read_only_fields = ['numero', 'subtotal', 'itbis', 'total', 'estado', 'pagado', 'cotizacion', 'cashflow_id',
                            'cashflow_numero', 'cashflow_estado', 'cashflow_sincronizado']


class GastoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='get_categoria_display', read_only=True)
    proyecto_nombre = serializers.CharField(source='proyecto.nombre', read_only=True, default=None)
    orden_numero = serializers.CharField(source='orden.codigo', read_only=True, default=None)
    tiene_comprobante = serializers.SerializerMethodField()

    class Meta:
        model = Gasto
        fields = ['id', 'fecha', 'concepto', 'categoria', 'categoria_nombre', 'monto', 'moneda', 'proveedor', 'proyecto',
                  'proyecto_nombre', 'orden', 'orden_numero', 'tiene_comprobante', 'fecha_creacion']

    def get_tiene_comprobante(self, g):
        return bool(g.comprobante)

    def validate_monto(self, v):
        if v <= 0:
            raise serializers.ValidationError("El monto tiene que ser mayor que cero.")
        return v
