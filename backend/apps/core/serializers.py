from rest_framework import serializers

from .models import Departamento


class DepartamentoSerializer(serializers.ModelSerializer):
    puestos = serializers.SerializerMethodField()
    personas = serializers.SerializerMethodField()

    class Meta:
        model = Departamento
        fields = ['id', 'nombre', 'descripcion', 'color', 'color_fondo', 'orden', 'puestos', 'personas', 'fecha_creacion', 'fecha_modificacion']

    def get_puestos(self, obj):
        return obj.puestos_de_trabajo.count()

    def get_personas(self, obj):
        return obj.puestos_de_trabajo.filter(perfiles_usuarios__user__is_active=True).values('perfiles_usuarios').count()

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Escribe el nombre del departamento.")
        qs = Departamento.objects.filter(nombre__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un departamento con ese nombre.")
        return value
