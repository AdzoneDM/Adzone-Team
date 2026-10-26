from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from apps.core.models import Departamento
from .formularios import TIPOS, validar_detalles
from .models import ArchivoOrden, Cliente, Comentario, EventoOrden, OrdenTrabajo, Proyecto
from .permisos import es_finanzas, gestiona_algo, puede_gestionar_orden, puede_gestionar_proyecto, ve_montos


def nombre(u):
    return (u.get_full_name() or u.username) if u else None


def _usuario(ser):
    request = ser.context.get('request')
    return getattr(request, 'user', None)


class UsuarioMini(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.SerializerMethodField()
    username = serializers.CharField()

    def get_nombre(self, u):
        return nombre(u)


class ClienteSerializer(serializers.ModelSerializer):
    ordenes_abiertas = serializers.IntegerField(read_only=True, default=0)
    proyectos_activos = serializers.IntegerField(read_only=True, default=0)
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = Cliente
        fields = ['id', 'nombre', 'tipo', 'tipo_nombre', 'rnc', 'contacto', 'telefono', 'correo', 'direccion', 'notas',
                  'activo', 'ordenes_abiertas', 'proyectos_activos', 'fecha_creacion']

    def validate_nombre(self, v):
        v = ' '.join(v.split())
        qs = Cliente.objects.filter(nombre__iexact=v)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un cliente con ese nombre.")
        return v


class ProyectoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    departamento_nombre = serializers.CharField(source='departamento.nombre', read_only=True, default=None)
    color = serializers.CharField(source='departamento.color', read_only=True, default=None)
    color_fondo = serializers.CharField(source='departamento.color_fondo', read_only=True, default=None)
    responsable_nombre = serializers.SerializerMethodField()
    miembros = serializers.PrimaryKeyRelatedField(many=True, required=False, queryset=User.objects.filter(is_active=True))
    miembros_nombres = serializers.SerializerMethodField()
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    progreso = serializers.SerializerMethodField()
    puedo_gestionar = serializers.SerializerMethodField()

    class Meta:
        model = Proyecto
        fields = ['id', 'codigo', 'nombre', 'cliente', 'cliente_nombre', 'departamento', 'departamento_nombre', 'color',
                  'color_fondo', 'responsable', 'responsable_nombre', 'miembros', 'miembros_nombres', 'estado',
                  'estado_nombre', 'prioridad', 'fecha_inicio', 'fecha_fin', 'presupuesto', 'descripcion', 'progreso',
                  'puedo_gestionar', 'fecha_creacion']
        read_only_fields = ['codigo']

    def get_responsable_nombre(self, o):
        return nombre(o.responsable)

    def get_miembros_nombres(self, o):
        return [nombre(u) for u in o.miembros.all()]

    def get_progreso(self, o):
        tareas = [t for t in o.tareas.all() if t.estado != 'CANCELADA']
        hoy = timezone.localdate()
        return {'tareas': len(tareas), 'validadas': sum(t.estado == 'COMPLETADA' for t in tareas),
                'vencidas': sum(t.estado in ('PENDIENTE', 'EN_PROGRESO') and t.fecha_limite < hoy for t in tareas),
                'ordenes_abiertas': sum(x.estado in OrdenTrabajo.ABIERTAS for x in o.ordenes.all())}

    def get_puedo_gestionar(self, o):
        u = _usuario(self)
        return bool(u and puede_gestionar_proyecto(u, o))

    def to_representation(self, o):
        d = super().to_representation(o)
        u = _usuario(self)
        if not (u and ve_montos(u, o)):
            d['presupuesto'] = None
        return d

    def validate(self, attrs):
        inicio = attrs.get('fecha_inicio', getattr(self.instance, 'fecha_inicio', None))
        fin = attrs.get('fecha_fin', getattr(self.instance, 'fecha_fin', None))
        if inicio and fin and fin < inicio:
            raise serializers.ValidationError({'fecha_fin': "La entrega no puede ser antes del inicio."})
        u = _usuario(self)
        if 'presupuesto' in attrs and u and not (es_finanzas(u) or gestiona_algo(u)):
            attrs.pop('presupuesto')
        return attrs


class ArchivoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    subido_por_nombre = serializers.SerializerMethodField()
    es_imagen = serializers.SerializerMethodField()

    class Meta:
        model = ArchivoOrden
        fields = ['id', 'nombre_original', 'tipo', 'tamano', 'url', 'es_imagen', 'subido_por_nombre', 'fecha']

    def get_url(self, a):
        return f"/api/operaciones/archivos/{a.pk}/"

    def get_subido_por_nombre(self, a):
        return nombre(a.subido_por)

    def get_es_imagen(self, a):
        return (a.tipo or '').startswith('image/')


class EventoSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = EventoOrden
        fields = ['id', 'texto', 'detalle', 'usuario_nombre', 'fecha']

    def get_usuario_nombre(self, e):
        return nombre(e.usuario) or 'La plataforma'


class ComentarioSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.SerializerMethodField()
    es_mio = serializers.SerializerMethodField()

    class Meta:
        model = Comentario
        fields = ['id', 'texto', 'autor', 'autor_nombre', 'es_mio', 'fecha']
        read_only_fields = ['autor']

    def get_autor_nombre(self, c):
        return nombre(c.autor)

    def get_es_mio(self, c):
        u = _usuario(self)
        return bool(u and c.autor_id == u.pk)

    def validate_texto(self, v):
        v = v.strip()
        if not v:
            raise serializers.ValidationError("Escribe el comentario.")
        return v[:4000]


class OrdenSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    prioridad_nombre = serializers.CharField(source='get_prioridad_display', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    proyecto_nombre = serializers.CharField(source='proyecto.nombre', read_only=True, default=None)
    departamento_nombre = serializers.CharField(source='departamento.nombre', read_only=True)
    color = serializers.CharField(source='departamento.color', read_only=True)
    color_fondo = serializers.CharField(source='departamento.color_fondo', read_only=True)
    solicitada_por_nombre = serializers.SerializerMethodField()
    responsable_nombre = serializers.SerializerMethodField()
    aprobada_por_nombre = serializers.SerializerMethodField()
    equipo_nombres = serializers.SerializerMethodField()
    departamento = serializers.PrimaryKeyRelatedField(queryset=Departamento.objects.all(), required=False)
    vencida = serializers.BooleanField(read_only=True)
    a_tiempo = serializers.BooleanField(read_only=True, allow_null=True)
    progreso = serializers.SerializerMethodField()
    puedo_gestionar = serializers.SerializerMethodField()
    puedo_editar = serializers.SerializerMethodField()
    soy_responsable = serializers.SerializerMethodField()
    siguientes = serializers.SerializerMethodField()
    facturada = serializers.SerializerMethodField()

    class Meta:
        model = OrdenTrabajo
        fields = ['id', 'numero', 'tipo', 'tipo_nombre', 'titulo', 'descripcion', 'cliente', 'cliente_nombre', 'proyecto',
                  'proyecto_nombre', 'departamento', 'departamento_nombre', 'color', 'color_fondo', 'detalles', 'prioridad',
                  'prioridad_nombre', 'estado', 'estado_nombre', 'solicitada_por', 'solicitada_por_nombre', 'responsable',
                  'responsable_nombre', 'equipo', 'equipo_nombres', 'aprobada_por_nombre', 'fecha_requerida',
                  'fecha_compromiso', 'fecha_aprobacion', 'fecha_lista', 'fecha_entrega', 'recibido_por', 'monto',
                  'motivo_cancelacion', 'vencida', 'a_tiempo', 'progreso', 'puedo_gestionar', 'puedo_editar',
                  'soy_responsable', 'siguientes', 'facturada', 'fecha_creacion', 'fecha_modificacion']
        read_only_fields = ['numero', 'estado', 'solicitada_por', 'responsable', 'equipo', 'fecha_compromiso',
                            'fecha_aprobacion', 'fecha_lista', 'fecha_entrega', 'recibido_por', 'motivo_cancelacion']

    def get_solicitada_por_nombre(self, o):
        return nombre(o.solicitada_por)

    def get_responsable_nombre(self, o):
        return nombre(o.responsable)

    def get_aprobada_por_nombre(self, o):
        return nombre(o.aprobada_por)

    def get_equipo_nombres(self, o):
        return [nombre(u) for u in o.equipo.all()]

    def get_progreso(self, o):
        tareas = [t for t in o.tareas.all() if t.estado != 'CANCELADA']
        if not tareas:
            return None
        pasos = [p for t in tareas for p in t.pasos.all()]
        return {'tareas': len(tareas), 'validadas': sum(t.estado == 'COMPLETADA' for t in tareas),
                'pasos': len(pasos), 'pasos_hechos': sum(p.hecho for p in pasos)}

    def get_puedo_gestionar(self, o):
        u = _usuario(self)
        return bool(u and puede_gestionar_orden(u, o))

    def get_puedo_editar(self, o):
        u = _usuario(self)
        if not u or o.estado in ('ENTREGADA', 'CANCELADA'):
            return False
        return puede_gestionar_orden(u, o) or (o.estado == 'SOLICITADA' and o.solicitada_por_id == u.pk)

    def get_soy_responsable(self, o):
        u = _usuario(self)
        return bool(u and u.pk in o.participantes_ids())

    def get_siguientes(self, o):
        return OrdenTrabajo.TRANSICIONES.get(o.estado, [])

    def get_facturada(self, o):
        u = _usuario(self)
        if not (u and es_finanzas(u)):
            return None
        return any(f.estado != 'ANULADA' for f in o.facturas.all())

    def to_representation(self, o):
        d = super().to_representation(o)
        u = _usuario(self)
        if not (u and ve_montos(u, o)):
            d['monto'] = None
        return d

    def validate(self, attrs):
        tipo = attrs.get('tipo', getattr(self.instance, 'tipo', None))
        if self.instance and 'tipo' in attrs and attrs['tipo'] != self.instance.tipo:
            raise serializers.ValidationError({'tipo': "El tipo de una orden no se cambia. Cancélala y crea otra."})
        if 'detalles' in attrs or not self.instance:
            limpios, errores = validar_detalles(tipo, attrs.get('detalles', {}))
            if errores:
                raise serializers.ValidationError({'detalles': errores})
            attrs['detalles'] = limpios
        if not attrs.get('departamento') and not self.instance:
            depto = Departamento.objects.filter(nombre=TIPOS.get(tipo, {}).get('departamento')).first()
            if depto is None:
                raise serializers.ValidationError({'departamento': "Elige el departamento que hará el trabajo."})
            attrs['departamento'] = depto
        cliente = attrs.get('cliente', getattr(self.instance, 'cliente', None))
        proyecto = attrs.get('proyecto', getattr(self.instance, 'proyecto', None))
        if proyecto and cliente and proyecto.cliente_id != cliente.pk:
            raise serializers.ValidationError({'proyecto': "Ese proyecto es de otro cliente."})
        u = _usuario(self)
        if 'monto' in attrs and u and not (es_finanzas(u) or gestiona_algo(u)):
            attrs.pop('monto')
        return attrs


class AprobarSerializer(serializers.Serializer):
    responsable = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    equipo = serializers.PrimaryKeyRelatedField(many=True, required=False, queryset=User.objects.filter(is_active=True))
    fecha_compromiso = serializers.DateField()
    pasos = serializers.ListField(child=serializers.CharField(max_length=255, allow_blank=True), required=False)
    crear_tarea = serializers.BooleanField(default=True)

    def validate_fecha_compromiso(self, v):
        if v < timezone.localdate():
            raise serializers.ValidationError("La fecha comprometida no puede estar en el pasado.")
        return v
