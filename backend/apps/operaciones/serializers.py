from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from apps.core.models import Departamento
from .formatos import AREAS, G0, validar_especificacion
from .models import (
    Acta, ArchivoOrden, AreaConfig, Cliente, Comentario, EventoOrden, Firma, Incidencia, OrdenArea, OrdenTrabajo, Proyecto,
    SolicitudCambio, TiempoEstandar, Traspaso,
)
from .permisos import (
    es_coordinacion, es_finanzas, gestiona_algo, puede_gestionar_orden, puede_gestionar_proyecto, supervisa_area, ve_montos,
)


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

    cashflow_id = serializers.CharField(read_only=True)

    class Meta:
        model = Cliente
        fields = ['id', 'nombre', 'tipo', 'tipo_nombre', 'rnc', 'cashflow_id', 'contacto', 'telefono', 'correo', 'direccion', 'notas',
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
        fields = ['id', 'nombre_original', 'tipo', 'tamano', 'url', 'es_imagen', 'subido_por_nombre', 'fecha', 'oa', 'categoria']

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


G0_TEXTOS = [t for _, t in G0]
G0_ANTICIPO = dict(G0)['anticipo']


def _dinero_visible(ser, o):
    u = _usuario(ser)
    return bool(u and ve_montos(u, o))


class OrdenSerializer(serializers.ModelSerializer):
    """OT Maestra (F-01)."""
    codigo = serializers.CharField(read_only=True)
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    prioridad_nombre = serializers.CharField(source='get_prioridad_display', read_only=True)
    tipo_cliente_nombre = serializers.CharField(source='get_tipo_cliente_display', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    cliente_rnc = serializers.CharField(source='cliente.rnc', read_only=True)
    proyecto_nombre = serializers.CharField(source='proyecto.nombre', read_only=True, default=None)
    departamento_nombre = serializers.CharField(source='departamento.nombre', read_only=True, default=None)
    color = serializers.CharField(source='departamento.color', read_only=True, default=None)
    color_fondo = serializers.CharField(source='departamento.color_fondo', read_only=True, default=None)
    solicitada_por_nombre = serializers.SerializerMethodField()
    asesor_comercial_nombre = serializers.SerializerMethodField()
    responsable_nombre = serializers.SerializerMethodField()
    aprobada_por_nombre = serializers.SerializerMethodField()
    excepcion_g0_por_nombre = serializers.SerializerMethodField()
    anticipo_confirmado_por_nombre = serializers.SerializerMethodField()
    vencida = serializers.BooleanField(read_only=True)
    a_tiempo = serializers.BooleanField(read_only=True, allow_null=True)
    areas_resumen = serializers.SerializerMethodField()
    progreso = serializers.SerializerMethodField()
    puedo_gestionar = serializers.SerializerMethodField()
    puedo_editar = serializers.SerializerMethodField()
    soy_responsable = serializers.SerializerMethodField()
    facturada = serializers.SerializerMethodField()
    g0_faltan = serializers.SerializerMethodField()

    class Meta:
        model = OrdenTrabajo
        fields = ['id', 'numero', 'solicitud', 'codigo', 'titulo', 'descripcion', 'exclusiones', 'cliente', 'cliente_nombre',
                  'cliente_rnc', 'proyecto', 'proyecto_nombre', 'departamento', 'departamento_nombre', 'color', 'color_fondo',
                  'contacto', 'telefono', 'correo', 'direccion_entrega', 'tipo_cliente', 'tipo_cliente_nombre',
                  'asesor_comercial', 'asesor_comercial_nombre', 'prioridad', 'prioridad_nombre', 'estado', 'estado_nombre',
                  'solicitada_por', 'solicitada_por_nombre', 'responsable', 'responsable_nombre', 'aprobada_por_nombre',
                  'cotizacion', 'numero_cotizacion', 'monto', 'anticipo_requerido', 'anticipo_confirmado', 'anticipo_fuente',
                  'anticipo_confirmado_por_nombre', 'anticipo_fecha', 'fecha_requerida', 'fecha_compromiso',
                  'tiempo_estandar_dias', 'cola_dias', 'aprobacion_dias', 'colchon_pct', 'rondas_incluidas', 'plan_areas',
                  'g0', 'g0_faltan', 'g0_entregada_fecha', 'g0_rechazo', 'excepcion_g0_por_nombre', 'excepcion_g0_motivo',
                  'excepcion_g0_regularizar', 'fecha_aprobacion', 'fecha_lista', 'fecha_entrega', 'recibido_por',
                  'fecha_cierre', 'costo_real', 'motivo_cancelacion', 'vencida', 'a_tiempo', 'areas_resumen', 'progreso',
                  'puedo_gestionar', 'puedo_editar', 'soy_responsable', 'facturada', 'fecha_creacion', 'fecha_modificacion']
        read_only_fields = ['numero', 'solicitud', 'estado', 'solicitada_por', 'responsable', 'fecha_compromiso',
                            'tiempo_estandar_dias', 'cola_dias', 'aprobacion_dias', 'colchon_pct', 'anticipo_confirmado',
                            'anticipo_fuente', 'anticipo_fecha', 'g0_entregada_fecha', 'g0_rechazo', 'excepcion_g0_motivo',
                            'excepcion_g0_regularizar', 'fecha_aprobacion', 'fecha_lista', 'fecha_entrega', 'recibido_por',
                            'fecha_cierre', 'costo_real', 'motivo_cancelacion', 'departamento']

    def get_solicitada_por_nombre(self, o):
        return nombre(o.solicitada_por)

    def get_asesor_comercial_nombre(self, o):
        return nombre(o.asesor_comercial)

    def get_responsable_nombre(self, o):
        return nombre(o.responsable)

    def get_aprobada_por_nombre(self, o):
        return nombre(o.aprobada_por)

    def get_excepcion_g0_por_nombre(self, o):
        return nombre(o.excepcion_g0_por)

    def get_anticipo_confirmado_por_nombre(self, o):
        return nombre(o.anticipo_confirmado_por) or ('Cashflow' if o.anticipo_fuente == 'CASHFLOW' else None)

    def get_areas_resumen(self, o):
        return [{'id': a.pk, 'numero': a.numero, 'area': a.area, 'nombre': a.get_area_display(), 'estado': a.estado,
                 'estado_nombre': a.get_estado_display(), 'secuencia': a.secuencia, 'vencida': a.vencida,
                 'responsable_nombre': nombre(a.responsable)} for a in o.areas.all()]

    def get_progreso(self, o):
        areas = [a for a in o.areas.all() if a.estado != 'CANCELADA']
        if not areas:
            return None
        return {'areas': len(areas), 'terminadas': sum(a.estado == 'TERMINADA' for a in areas)}

    def get_puedo_gestionar(self, o):
        u = _usuario(self)
        return bool(u and puede_gestionar_orden(u, o))

    def get_puedo_editar(self, o):
        u = _usuario(self)
        if not u or o.estado in ('ENTREGADA', 'CERRADA', 'CANCELADA'):
            return False
        if o.estado in ('SOLICITADA', 'DEVUELTA'):
            return es_coordinacion(u) or u.pk in (o.solicitada_por_id, o.asesor_comercial_id)
        return es_coordinacion(u)

    def get_soy_responsable(self, o):
        u = _usuario(self)
        return bool(u and u.pk in o.participantes_ids())

    def get_facturada(self, o):
        u = _usuario(self)
        if not (u and es_finanzas(u)):
            return None
        return any(f.estado != 'ANULADA' and not f.es_anticipo for f in o.facturas.all())

    def get_g0_faltan(self, o):
        from .servicios_ot import faltan_g0
        return faltan_g0(o)

    def to_representation(self, o):
        d = super().to_representation(o)
        if not _dinero_visible(self, o):
            for k in ('monto', 'anticipo_requerido', 'costo_real'):
                d[k] = None
        return d

    def validate_g0(self, v):
        if not isinstance(v, dict):
            raise serializers.ValidationError("Formato inválido.")
        limpio = {t: bool(v.get(t)) for t in G0_TEXTOS}
        u = _usuario(self)
        previo = (self.instance.g0 if self.instance else {}) or {}
        # La casilla del anticipo la marca Administración (o Cashflow al leer el pago), no Comercial.
        if not (u and es_finanzas(u)):
            limpio[G0_ANTICIPO] = bool(previo.get(G0_ANTICIPO))
        return limpio

    def validate_plan_areas(self, v):
        if not isinstance(v, list):
            raise serializers.ValidationError("Formato inválido.")
        filas, errores = [], []
        for i, f in enumerate(v[:15]):
            if not isinstance(f, dict) or f.get('area') not in AREAS:
                errores.append(f"Fila {i + 1}: elige el área.")
                continue
            fila = {'area': f['area'], 'secuencia': max(1, min(20, int(f.get('secuencia') or i + 1))),
                    'que_produce': str(f.get('que_produce') or '').strip()[:255]}
            if not fila['que_produce']:
                errores.append(f"Fila {i + 1}: anota qué produce {AREAS[f['area']]['nombre']}.")
            if f.get('fecha_entrega_interna'):
                fila['fecha_entrega_interna'] = str(f['fecha_entrega_interna'])[:10]
            try:
                if f.get('tiempo_estandar_dias') not in (None, ''):
                    fila['tiempo_estandar_dias'] = float(f['tiempo_estandar_dias'])
            except (TypeError, ValueError):
                errores.append(f"Fila {i + 1}: tiempo estándar inválido.")
            if f.get('responsable'):
                fila['responsable'] = int(f['responsable'])
            if f.get('especificacion'):
                limpia, errs = validar_especificacion(f['area'], f['especificacion'], exigir=False)
                if errs:
                    errores.append(f"Fila {i + 1}: " + " ".join(errs.values()))
                fila['especificacion'] = limpia
            filas.append(fila)
        if errores:
            raise serializers.ValidationError(errores)
        return filas

    def validate(self, attrs):
        cliente = attrs.get('cliente', getattr(self.instance, 'cliente', None))
        proyecto = attrs.get('proyecto', getattr(self.instance, 'proyecto', None))
        if proyecto and cliente and proyecto.cliente_id != cliente.pk:
            raise serializers.ValidationError({'proyecto': "Ese proyecto es de otro cliente."})
        cot = attrs.get('cotizacion')
        if cot and cliente and cot.cliente_id != cliente.pk:
            raise serializers.ValidationError({'cotizacion': "Esa cotización es de otro cliente."})
        if cot:
            attrs.setdefault('numero_cotizacion', cot.numero)
            if attrs.get('monto') in (None, ''):
                attrs['monto'] = cot.subtotal
        u = _usuario(self)
        if u and not (es_finanzas(u) or es_coordinacion(u) or (self.instance is None) or
                      u.pk in (self.instance.solicitada_por_id, self.instance.asesor_comercial_id)):
            for k in ('monto', 'anticipo_requerido'):
                attrs.pop(k, None)
        if self.instance and self.instance.estado not in ('SOLICITADA', 'DEVUELTA'):
            attrs.pop('plan_areas', None)  # después de liberar, las áreas se agregan con «Agregar área»
            attrs.pop('g0', None)
        req = attrs.get('fecha_requerida')
        if req and not self.instance and req < timezone.localdate():
            raise serializers.ValidationError({'fecha_requerida': "La fecha requerida no puede estar en el pasado."})
        primera = (attrs.get('plan_areas') or getattr(self.instance, 'plan_areas', None) or [None])[0]
        if primera and not attrs.get('departamento'):
            depto = Departamento.objects.filter(nombre=AREAS[primera['area']]['departamento']).first()
            if depto:
                attrs['departamento'] = depto
        return attrs


class OrdenAreaSerializer(serializers.ModelSerializer):
    """Orden de Área (F-02 a F-10)."""
    area_nombre = serializers.CharField(source='get_area_display', read_only=True)
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    orden_codigo = serializers.CharField(source='orden.codigo', read_only=True)
    orden_titulo = serializers.CharField(source='orden.titulo', read_only=True)
    orden_estado = serializers.CharField(source='orden.estado', read_only=True)
    cliente_nombre = serializers.CharField(source='orden.cliente.nombre', read_only=True)
    prioridad = serializers.CharField(source='orden.prioridad', read_only=True)
    formato = serializers.SerializerMethodField()
    responsable_nombre = serializers.SerializerMethodField()
    g1_entrega_por_nombre = serializers.SerializerMethodField()
    g1_recibe_por_nombre = serializers.SerializerMethodField()
    g3_supervisor_nombre = serializers.SerializerMethodField()
    requiere_g4 = serializers.BooleanField(read_only=True)
    vencida = serializers.BooleanField(read_only=True)
    tarea = serializers.SerializerMethodField()
    bloqueada_por = serializers.SerializerMethodField()
    traspaso_pendiente = serializers.SerializerMethodField()
    puedo = serializers.SerializerMethodField()

    class Meta:
        model = OrdenArea
        fields = ['id', 'orden', 'orden_codigo', 'orden_titulo', 'orden_estado', 'cliente_nombre', 'prioridad', 'area',
                  'area_nombre', 'numero', 'secuencia', 'que_produce', 'fecha_entrega_interna', 'tiempo_estandar_dias',
                  'responsable', 'responsable_nombre', 'estado', 'estado_nombre', 'especificacion', 'formato',
                  'g1', 'g1_entrega_por_nombre', 'g1_recibe_por_nombre', 'g1_fecha', 'g1_rechazo',
                  'requiere_g4', 'g4_aprobado', 'g4_canales', 'g4_ronda', 'g4_fecha', 'g4_aprobado_por', 'g4_version',
                  'g4_con_cambios', 'g3', 'g3_resultado', 'g3_observaciones', 'g3_supervisor_nombre', 'g3_fecha', 'g2',
                  'servicios_externos', 'otros_materiales', 'pase_retrabajo', 'fecha_terminada', 'vencida', 'tarea',
                  'bloqueada_por', 'traspaso_pendiente', 'puedo', 'fecha_creacion']
        read_only_fields = [f for f in fields if f not in ('que_produce', 'fecha_entrega_interna', 'especificacion',
                                                             'servicios_externos', 'otros_materiales', 'tiempo_estandar_dias')]

    def get_formato(self, oa):
        f = AREAS[oa.area]
        return {k: f.get(k) for k in ('formato', 'nombre', 'icono', 'nota', 'nota_g4', 'sale_al_cliente')}

    def get_responsable_nombre(self, oa):
        return nombre(oa.responsable)

    def get_g1_entrega_por_nombre(self, oa):
        return nombre(oa.g1_entrega_por)

    def get_g1_recibe_por_nombre(self, oa):
        return nombre(oa.g1_recibe_por)

    def get_g3_supervisor_nombre(self, oa):
        return nombre(oa.g3_supervisor)

    def get_tarea(self, oa):
        t = next((t for t in oa.tareas.all() if t.estado != 'CANCELADA'), None)
        if t is None:
            return None
        pasos = list(t.pasos.all())
        return {'id': t.pk, 'estado': t.estado, 'estado_nombre': t.get_estado_display(), 'pasos': len(pasos),
                'pasos_hechos': sum(p.hecho for p in pasos), 'rondas_revision': t.rondas_revision}

    def get_bloqueada_por(self, oa):
        if oa.estado not in ('EMITIDA', 'RECHAZADA'):
            return []
        return [a.numero for a in oa.orden.areas.all() if a.secuencia < oa.secuencia and a.estado not in ('TERMINADA', 'CANCELADA')]

    def get_traspaso_pendiente(self, oa):
        t = next((t for t in oa.traspasos.all() if t.resultado == 'PENDIENTE' and t.compuerta in ('G2', 'G5')), None)
        return TraspasoSerializer(t, context=self.context).data if t else None

    def get_puedo(self, oa):
        u = _usuario(self)
        if not u:
            return {}
        supervisa = supervisa_area(u, oa.area)
        trabaja = oa.responsable_id == u.pk or any(u.pk in [c.pk for c in t.companeros.all()] for t in oa.tareas.all())
        coord = es_coordinacion(u)
        return {'recibir': supervisa and oa.estado in ('EMITIDA', 'RECHAZADA'), 'reemitir': coord and oa.estado == 'RECHAZADA',
                'operar': (trabaja or supervisa or coord) and oa.estado in ('RECIBIDA', 'EN_EJECUCION', 'EN_APROBACION'),
                'editar': (supervisa or coord) and oa.estado not in ('TERMINADA', 'CANCELADA'), 'supervisa': supervisa,
                'costos': supervisa or coord or es_finanzas(u)}

    def validate_especificacion(self, v):
        area = self.instance.area if self.instance else None
        limpia, errores = validar_especificacion(area, v, exigir=False)
        if errores:
            raise serializers.ValidationError(list(errores.values()))
        return limpia


class TraspasoSerializer(serializers.ModelSerializer):
    compuerta_nombre = serializers.CharField(source='get_compuerta_display', read_only=True)
    resultado_nombre = serializers.CharField(source='get_resultado_display', read_only=True)
    entrega_por_nombre = serializers.SerializerMethodField()
    recibe_por_nombre = serializers.SerializerMethodField()
    oa_numero = serializers.CharField(source='oa.numero', read_only=True, default=None)
    orden_codigo = serializers.CharField(source='orden.codigo', read_only=True)
    puedo_recibir = serializers.SerializerMethodField()

    class Meta:
        model = Traspaso
        fields = ['id', 'numero', 'orden', 'orden_codigo', 'oa', 'oa_numero', 'destino_oa', 'compuerta', 'compuerta_nombre',
                  'que_entrega', 'entrega_area', 'entrega_por_nombre', 'entrega_fecha', 'recibe_area', 'recibe_por_nombre',
                  'recibe_fecha', 'verificacion', 'resultado', 'resultado_nombre', 'causa_rechazo', 'puedo_recibir']

    def get_entrega_por_nombre(self, t):
        return nombre(t.entrega_por)

    def get_recibe_por_nombre(self, t):
        return nombre(t.recibe_por)

    def get_puedo_recibir(self, t):
        from .servicios_ot import puede_recibir_traspaso
        u = _usuario(self)
        return bool(u and t.resultado == 'PENDIENTE' and t.entrega_por_id != u.pk and puede_recibir_traspaso(t, u))


class FirmaSerializer(serializers.ModelSerializer):
    tiene_imagen = serializers.SerializerMethodField()

    class Meta:
        model = Firma
        fields = ['id', 'contexto', 'rol', 'nombre', 'documento', 'tiene_imagen', 'imagen', 'fecha']

    def get_tiene_imagen(self, f):
        return bool(f.imagen)


class IncidenciaSerializer(serializers.ModelSerializer):
    reporta_nombre = serializers.SerializerMethodField()
    oa_numero = serializers.CharField(source='oa.numero', read_only=True)

    class Meta:
        model = Incidencia
        fields = ['id', 'oa', 'oa_numero', 'reporta_nombre', 'fecha', 'descripcion', 'minutos_perdidos', 'resolucion']
        read_only_fields = ['oa', 'fecha']

    def get_reporta_nombre(self, i):
        return nombre(i.reporta)


class CambioSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source='get_tipo_display', read_only=True)
    estado_nombre = serializers.CharField(source='get_estado_display', read_only=True)
    oa_numero = serializers.CharField(source='oa.numero', read_only=True, default=None)
    orden_codigo = serializers.CharField(source='orden.codigo', read_only=True)
    solicitado_por_nombre = serializers.SerializerMethodField()
    responsable_accion_nombre = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudCambio
        fields = ['id', 'numero', 'orden', 'orden_codigo', 'oa', 'oa_numero', 'tipo', 'tipo_nombre', 'clasificacion',
                  'descripcion', 'aprobado_original', 'impacto', 'area_responsable', 'costo_retrabajo', 'monto_cliente',
                  'areas_notificadas', 'accion_preventiva', 'responsable_accion', 'responsable_accion_nombre',
                  'fecha_verificacion', 'autorizaciones', 'estado', 'estado_nombre', 'solicitado_por_nombre', 'fecha']
        read_only_fields = ['numero', 'orden', 'estado', 'autorizaciones']

    def get_solicitado_por_nombre(self, c):
        return nombre(c.solicitado_por)

    def get_responsable_accion_nombre(self, c):
        return nombre(c.responsable_accion)

    def validate(self, attrs):
        if len((attrs.get('descripcion') or getattr(self.instance, 'descripcion', '') or '').strip()) < 5:
            raise serializers.ValidationError({'descripcion': "Describe el cambio o el error."})
        oa = attrs.get('oa')
        orden = self.context.get('orden')
        if oa and orden and oa.orden_id != orden.pk:
            raise serializers.ValidationError({'oa': "Esa Orden de Área es de otra OT."})
        return attrs


class ActaSerializer(serializers.ModelSerializer):
    modalidad_nombre = serializers.CharField(source='get_modalidad_display', read_only=True)
    conformidad_nombre = serializers.CharField(source='get_conformidad_display', read_only=True)
    liberada_por_nombre = serializers.SerializerMethodField()
    supervisor_nombre = serializers.SerializerMethodField()
    orden_codigo = serializers.CharField(source='orden.codigo', read_only=True)

    class Meta:
        model = Acta
        fields = ['id', 'numero', 'orden', 'orden_codigo', 'modalidad', 'modalidad_nombre', 'fecha', 'hora_llegada', 'hora_fin',
                  'direccion', 'contacto_sitio', 'g5', 'liberada_por_nombre', 'liberada_fecha', 'saldo_al_liberar',
                  'entrega_taller', 'recibe_cuadrilla', 'items', 'verificacion', 'hallazgos', 'material_devuelto',
                  'conformidad', 'conformidad_nombre', 'observaciones_cliente', 'garantia', 'instrucciones_mantenimiento',
                  'proxima_revision', 'supervisor_nombre', 'firmada', 'fecha_creacion']
        read_only_fields = ['numero', 'orden', 'g5', 'liberada_fecha', 'saldo_al_liberar', 'verificacion', 'conformidad',
                            'firmada']

    def get_liberada_por_nombre(self, a):
        return nombre(a.liberada_por)

    def get_supervisor_nombre(self, a):
        return nombre(a.supervisor)

    def validate_items(self, v):
        if not isinstance(v, list):
            raise serializers.ValidationError("Formato inválido.")
        return [{'descripcion': str(i.get('descripcion', ''))[:255], 'cantidad': str(i.get('cantidad', ''))[:20],
                 'observacion': str(i.get('observacion', ''))[:255]} for i in v[:30] if isinstance(i, dict) and i.get('descripcion')]

    def to_representation(self, a):
        d = super().to_representation(a)
        u = _usuario(self)
        if not (u and ve_montos(u, a.orden)):
            d['saldo_al_liberar'] = None
        return d


class AreaConfigSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source='get_codigo_display', read_only=True)
    departamento_nombre = serializers.CharField(source='departamento.nombre', read_only=True, default=None)
    supervisores = serializers.PrimaryKeyRelatedField(many=True, required=False, queryset=User.objects.filter(is_active=True))
    supervisores_nombres = serializers.SerializerMethodField()

    class Meta:
        model = AreaConfig
        fields = ['id', 'codigo', 'nombre', 'departamento', 'departamento_nombre', 'supervisores', 'supervisores_nombres', 'activa']
        read_only_fields = ['codigo']

    def get_supervisores_nombres(self, a):
        return [nombre(u) for u in a.supervisores.all()]


class TiempoEstandarSerializer(serializers.ModelSerializer):
    area_nombre = serializers.CharField(source='get_area_display', read_only=True)

    class Meta:
        model = TiempoEstandar
        fields = ['id', 'area', 'area_nombre', 'trabajo', 'dias']
