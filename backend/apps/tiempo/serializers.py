from datetime import datetime, time, timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import MAX_MINUTOS, RegistroTiempo


class RegistroSerializer(serializers.ModelSerializer):
    tarea_titulo = serializers.CharField(source='tarea.titulo', read_only=True, default=None)
    orden_numero = serializers.CharField(source='orden.numero', read_only=True, default=None)
    orden_titulo = serializers.CharField(source='orden.titulo', read_only=True, default=None)
    proyecto_nombre = serializers.CharField(source='proyecto.nombre', read_only=True, default=None)
    cliente = serializers.SerializerMethodField()
    corriendo = serializers.BooleanField(read_only=True)
    minutos = serializers.IntegerField(required=False, min_value=1, max_value=MAX_MINUTOS)
    fecha = serializers.DateField(write_only=True, required=False)
    hora = serializers.TimeField(write_only=True, required=False)
    dia = serializers.SerializerMethodField()

    class Meta:
        model = RegistroTiempo
        fields = ['id', 'tarea', 'tarea_titulo', 'orden', 'orden_numero', 'orden_titulo', 'proyecto', 'proyecto_nombre',
                  'cliente', 'descripcion', 'inicio', 'fin', 'minutos', 'corriendo', 'facturable', 'fecha', 'hora', 'dia']
        read_only_fields = ['inicio', 'fin']

    def get_cliente(self, r):
        if r.orden_id:
            return r.orden.cliente.nombre
        if r.proyecto_id:
            return r.proyecto.cliente.nombre
        return r.tarea.cliente if r.tarea_id else None

    def get_dia(self, r):
        return timezone.localtime(r.inicio).date().isoformat()

    def to_representation(self, r):
        d = super().to_representation(r)
        d['minutos'] = r.minutos_hasta_ahora()
        return d

    def validate(self, attrs):
        if self.instance is None:
            if not attrs.get('minutos'):
                raise serializers.ValidationError({'minutos': "Anota cuánto tiempo trabajaste."})
            fecha = attrs.pop('fecha', None) or timezone.localdate()
            if fecha > timezone.localdate():
                raise serializers.ValidationError({'fecha': "No se anota tiempo de días que no han llegado."})
            if fecha < timezone.localdate() - timedelta(days=31):
                raise serializers.ValidationError({'fecha': "Solo se anota tiempo del último mes."})
            hora = attrs.pop('hora', None) or time(8, 0)
            attrs['inicio'] = timezone.make_aware(datetime.combine(fecha, hora))
            attrs['fin'] = attrs['inicio'] + timedelta(minutes=attrs['minutos'])
        else:
            attrs.pop('fecha', None)
            attrs.pop('hora', None)
            if 'minutos' in attrs and self.instance.fin:
                attrs['fin'] = self.instance.inicio + timedelta(minutes=attrs['minutos'])
            elif 'minutos' in attrs:
                attrs.pop('minutos')  # el cronómetro corriendo no se edita a mano
        return attrs
