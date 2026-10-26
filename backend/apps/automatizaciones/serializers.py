from urllib.parse import urlparse

from rest_framework import serializers

from apps.operaciones.formularios import TIPOS
from apps.operaciones.models import OrdenTrabajo
from .models import Ejecucion, Regla

DESTINOS = ['responsable', 'solicitante', 'jefes', 'finanzas', 'administradores']


class ReglaSerializer(serializers.ModelSerializer):
    evento_nombre = serializers.CharField(source='get_evento_display', read_only=True)
    accion_nombre = serializers.CharField(source='get_accion_display', read_only=True)

    class Meta:
        model = Regla
        fields = ['id', 'nombre', 'activa', 'evento', 'evento_nombre', 'condiciones', 'accion', 'accion_nombre',
                  'parametros', 'veces', 'ultima_vez', 'fecha_creacion']
        read_only_fields = ['veces', 'ultima_vez']

    def validate(self, attrs):
        cond = attrs.get('condiciones', getattr(self.instance, 'condiciones', {})) or {}
        if cond.get('tipo') and cond['tipo'] not in TIPOS:
            raise serializers.ValidationError({'condiciones': "Tipo de orden desconocido."})
        if cond.get('estado') and cond['estado'] not in dict(OrdenTrabajo.ESTADOS):
            raise serializers.ValidationError({'condiciones': "Estado desconocido."})
        accion = attrs.get('accion', getattr(self.instance, 'accion', None))
        p = attrs.get('parametros', getattr(self.instance, 'parametros', {})) or {}
        if accion == 'AVISAR':
            if not p.get('a') and not p.get('usuario_id'):
                raise serializers.ValidationError({'parametros': "Elige a quién avisar."})
            if any(a not in DESTINOS for a in p.get('a', [])):
                raise serializers.ValidationError({'parametros': "Destinatario desconocido."})
        elif accion == 'CREAR_TAREA':
            if not (p.get('titulo') or '').strip():
                raise serializers.ValidationError({'parametros': "Escribe el título de la tarea."})
            try:
                if not 0 <= int(p.get('dias', 2)) <= 90:
                    raise ValueError
            except (TypeError, ValueError):
                raise serializers.ValidationError({'parametros': "El plazo va de 0 a 90 días."})
        elif accion == 'WEBHOOK':
            url = urlparse(p.get('url') or '')
            if url.scheme not in ('https', 'http') or not url.netloc:
                raise serializers.ValidationError({'parametros': "Pega la dirección del webhook de n8n (https://…)."})
        attrs['condiciones'] = {k: v for k, v in cond.items() if v not in (None, '', [])}
        return attrs


class EjecucionSerializer(serializers.ModelSerializer):
    regla_nombre = serializers.CharField(source='regla.nombre', read_only=True)

    class Meta:
        model = Ejecucion
        fields = ['id', 'regla', 'regla_nombre', 'objeto', 'resultado', 'exito', 'fecha']
