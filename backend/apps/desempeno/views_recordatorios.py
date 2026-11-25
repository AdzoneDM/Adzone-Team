"""API de recordatorios personales: cada persona ve y maneja solo los suyos."""
from datetime import timedelta

from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Recordatorio

MAX_ACTIVOS = 200
MAX_POSPONER_MIN = 60 * 24 * 30


class RecordatorioSerializer(serializers.ModelSerializer):
    estado = serializers.SerializerMethodField()
    repetir_nombre = serializers.CharField(source='get_repetir_display', read_only=True)

    class Meta:
        model = Recordatorio
        fields = ['id', 'titulo', 'nota', 'recordar_en', 'repetir', 'repetir_nombre', 'estado', 'avisado', 'hecho', 'ultimo_aviso', 'creado']
        read_only_fields = ['avisado', 'hecho', 'ultimo_aviso', 'creado']
        extra_kwargs = {'titulo': {'max_length': 120}, 'nota': {'max_length': 1000, 'required': False, 'allow_blank': True}}

    def get_estado(self, r):
        return 'HECHO' if r.hecho else 'AVISADO' if r.avisado else 'PENDIENTE'

    def validate_titulo(self, v):
        v = (v or '').strip()
        if not v:
            raise serializers.ValidationError("Escribe de qué te vamos a recordar.")
        return v

    def validate_recordar_en(self, v):
        cambia = self.instance is None or v != self.instance.recordar_en
        if cambia and v < timezone.now() - timedelta(minutes=1):
            raise serializers.ValidationError("Elige una fecha y hora que todavía no hayan pasado.")
        return v


class RecordatorioViewSet(viewsets.ModelViewSet):
    """Solo los recordatorios de quien consulta: el resto de las personas (también Dirección) recibe «no encontrado»."""
    serializer_class = RecordatorioSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return Recordatorio.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        if self.get_queryset().filter(hecho=False).count() >= MAX_ACTIVOS:
            raise serializers.ValidationError({"titulo": f"Tienes {MAX_ACTIVOS} recordatorios activos: borra o marca como hechos algunos."})
        serializer.save(usuario=self.request.user)

    def perform_update(self, serializer):
        cambia_hora = 'recordar_en' in serializer.validated_data and serializer.validated_data['recordar_en'] != serializer.instance.recordar_en
        # Una nueva hora lo vuelve a activar (aunque ya hubiera sonado o estuviera hecho)
        serializer.save(**({'avisado': False, 'hecho': False} if cambia_hora else {}))

    @action(detail=True, methods=['post'])
    def hecho(self, request, pk=None):
        """Lo marcas como hecho (deja de aparecer entre los pendientes). Uno que se repite sigue su ritmo: se borra para cancelarlo."""
        r = self.get_object()
        if r.repetir == 'NO':
            r.hecho = True
            r.save(update_fields=['hecho'])
        return Response(self.get_serializer(r).data)

    @action(detail=True, methods=['post'])
    def reabrir(self, request, pk=None):
        """Un hecho vuelve a pendientes (si su hora ya pasó, avisará en el próximo minuto)."""
        r = self.get_object()
        r.hecho = False
        r.avisado = False
        r.save(update_fields=['hecho', 'avisado'])
        return Response(self.get_serializer(r).data)

    @action(detail=True, methods=['post'])
    def posponer(self, request, pk=None):
        """Lo vuelve a avisar dentro de `minutos` (de 1 minuto a 30 días). Los que se repiten no se posponen: se editan."""
        r = self.get_object()
        if r.repetir != 'NO':
            return Response({"detail": "Un recordatorio que se repite no se pospone: edita su hora."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            minutos = int(request.data.get('minutos'))
        except (TypeError, ValueError):
            minutos = 0
        if not 1 <= minutos <= MAX_POSPONER_MIN:
            return Response({"minutos": ["Elige entre 1 minuto y 30 días."]}, status=status.HTTP_400_BAD_REQUEST)
        r.recordar_en = timezone.now() + timedelta(minutes=minutos)
        r.avisado = False
        r.hecho = False
        r.save(update_fields=['recordar_en', 'avisado', 'hecho'])
        return Response(self.get_serializer(r).data)
