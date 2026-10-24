from rest_framework import serializers

from apps.organizacion.serializers import PuestoDeTrabajoSerializer
from .models import KPIAsignado, PlantillaKPI


class PlantillaKPISerializer(serializers.ModelSerializer):
    puestos_asignados = serializers.SerializerMethodField()

    class Meta:
        model = PlantillaKPI
        fields = ['id', 'nombre', 'descripcion', 'unidad_medida', 'menor_es_mejor', 'puestos_asignados',
                  'fecha_creacion', 'fecha_modificacion']

    def get_puestos_asignados(self, obj):
        return obj.asignaciones.count()

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Escribe qué mide el KPI.")
        return value


class KPIAsignadoSerializer(serializers.ModelSerializer):
    puesto_trabajo_detalle = PuestoDeTrabajoSerializer(source='puesto_trabajo', read_only=True)
    plantilla_kpi_detalle = PlantillaKPISerializer(source='plantilla_kpi', read_only=True)
    nombre = serializers.CharField(source='plantilla_kpi.nombre', read_only=True)

    class Meta:
        model = KPIAsignado
        fields = [
            'id', 'nombre',
            'puesto_trabajo', 'puesto_trabajo_detalle',
            'plantilla_kpi', 'plantilla_kpi_detalle',
            'ponderacion', 'objetivo_meta', 'periodicidad_objetivo',
            'es_entrada_manual', 'meta_numerica', 'activo',
            'fecha_asignacion', 'fecha_modificacion_asignacion',
        ]
        extra_kwargs = {
            'puesto_trabajo': {'required': True},
            'plantilla_kpi': {'required': True},
            'objetivo_meta': {'required': False, 'allow_blank': True},
        }

    def validate_ponderacion(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError("La ponderación debe estar entre 0 y 100.")
        return value

    def validate(self, data):
        manual = data.get('es_entrada_manual', getattr(self.instance, 'es_entrada_manual', True))
        meta = data.get('meta_numerica', getattr(self.instance, 'meta_numerica', None))
        if not manual and not meta:
            raise serializers.ValidationError(
                {"meta_numerica": "Un KPI automático necesita una meta numérica mensual (p. ej. 20 publicaciones)."})
        if meta is not None and meta < 0:
            raise serializers.ValidationError({"meta_numerica": "No puede ser negativa."})
        if not data.get('objetivo_meta', getattr(self.instance, 'objetivo_meta', '')) and meta is not None:
            data['objetivo_meta'] = f"{meta:g}"
        return data
