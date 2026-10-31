from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Campana
from .permisos import GRUPO_AGENTE


class CampanaSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    idioma_nombre = serializers.CharField(source='get_idioma_display', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True, default=None)
    agentes = serializers.PrimaryKeyRelatedField(many=True, required=False, queryset=User.objects.filter(is_active=True))
    agentes_detalle = serializers.SerializerMethodField()

    class Meta:
        model = Campana
        fields = ['id', 'nombre', 'cliente', 'cliente_nombre', 'tipo', 'tipo_nombre', 'canales', 'idioma', 'idioma_nombre',
                  'horario', 'fecha_inicio', 'fecha_fin', 'meta_contactos_dia', 'meta_conversion', 'meta_calidad',
                  'guion', 'notas', 'activa', 'agentes', 'agentes_detalle', 'orden', 'fecha_creacion']
        read_only_fields = ['fecha_creacion']

    def get_agentes_detalle(self, obj):
        return [{'id': u.id, 'nombre': u.get_full_name() or u.username} for u in obj.agentes.all()]

    def validate_agentes(self, value):
        no_agentes = [u.get_full_name() or u.username for u in value if not u.groups.filter(name=GRUPO_AGENTE).exists()]
        if no_agentes:
            raise serializers.ValidationError(
                f"No tienen el acceso «Agente Call Center»: {', '.join(no_agentes)}. Se da en Personas → editar.")
        return value

    def validate_canales(self, value):
        desconocidos = [c for c in value if c not in Campana.CANALES]
        if desconocidos:
            raise serializers.ValidationError(f"Canal desconocido: {', '.join(desconocidos)}")
        return value

    def validate(self, data):
        inicio = data.get('fecha_inicio', getattr(self.instance, 'fecha_inicio', None))
        fin = data.get('fecha_fin', getattr(self.instance, 'fecha_fin', None))
        if inicio and fin and fin < inicio:
            raise serializers.ValidationError({'fecha_fin': "Termina antes de empezar."})
        for campo in ('meta_conversion', 'meta_calidad'):
            if campo in data and not 0 <= data[campo] <= 100:
                raise serializers.ValidationError({campo: "Debe estar entre 0 y 100."})
        return data
