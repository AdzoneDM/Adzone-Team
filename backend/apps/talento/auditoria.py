"""
Auditoría automática de cambios administrativos.

Un middleware guarda quién hace la petición; señales pre/post_save y post_delete registran, para los modelos
vigilados, qué campos cambiaron (antes → después). El salario además deja su historial en CambioSalarial.
"""
import contextvars
from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_save
from django.utils import timezone

_usuario = contextvars.ContextVar('usuario_auditoria', default=None)


class AuditoriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        token = _usuario.set(user if user is not None and user.is_authenticated else None)
        try:
            return self.get_response(request)
        finally:
            _usuario.reset(token)


def usuario_actual():
    u = _usuario.get()
    return u if u is not None and getattr(u, 'is_authenticated', False) else None


def _valor(v):
    if isinstance(v, Decimal):
        return float(v)
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    return v


def auditar(accion, objeto, antes=None, despues=None, usuario=None):
    from .models import AuditoriaCambio
    AuditoriaCambio.objects.create(usuario=usuario or usuario_actual(), accion=accion[:60], objeto=str(objeto)[:200],
                                   antes=antes, despues=despues)


# modelo (app_label.Modelo) → (nombre legible, campos vigilados)
VIGILADOS = {
    'kpis.KPIAsignado': ('KPI del puesto', ['ponderacion', 'objetivo_meta', 'meta_numerica', 'periodicidad_objetivo', 'es_entrada_manual', 'activo', 'umbral_alerta']),
    'kpis.PlantillaKPI': ('Plantilla de KPI', ['nombre', 'unidad_medida', 'menor_es_mejor', 'fuente', 'formula', 'fuente_datos', 'responsable_validacion']),
    'desempeno.ConfiguracionDesempeno': ('Reglas del puntaje', ['peso_tareas', 'peso_calidad', 'peso_jornada', 'nota_tarde', 'puntaje_minimo', 'minimo_tareas_evaluacion', 'minimo_tareas_empleado_mes', 'tramos_bono']),
    'desempeno.ResultadoKPI': ('Resultado de KPI', ['valor_meta', 'valor_real']),
    'monitoreo.ConfiguracionMonitoreo': ('Configuración del monitoreo', ['activo', 'capturas', 'capturas_cada_min', 'desenfocar_capturas', 'umbral_inactivo_seg', 'retencion_dias', 'retencion_capturas_dias', 'version_politica', 'meta_productividad_pct']),
    'monitoreo.ReglaProductividad': ('Regla de productividad', ['tipo', 'patron', 'categoria', 'departamento_id']),
    'monitoreo.Dispositivo': ('Computadora', ['nombre', 'activo', 'usuario_id']),
    'asistencia.Marcaje': ('Marcaje', ['tipo', 'momento', 'usuario_id']),
    'asistencia.Horario': ('Horario', ['nombre', 'dias', 'almuerzo_minutos', 'tolerancia_minutos', 'por_defecto']),
    'asistencia.AsignacionHorario': ('Horario de una persona', ['horario_id', 'marca_obligatoria']),
    'asistencia.Ausencia': ('Permiso', ['estado']),
    'organizacion.PerfilUsuario': ('Perfil de persona', ['puesto_trabajo_id', 'salario_mensual', 'costo_hora', 'nomina', 'horas_semana']),
    'organizacion.PuestoDeTrabajo': ('Puesto', ['nombre', 'departamento_id', 'supervisor_id']),
    'talento.Evaluacion': ('Evaluación', ['estado']),
    'talento.EventoExpediente': ('Expediente', ['tipo', 'titulo', 'visible_al_colaborador']),
    'talento.Politica': ('Política', ['titulo', 'version', 'borrador', 'activa', 'para_todos', 'requiere_aceptacion']),
    'talento.DocumentoEmpleado': ('Documento del expediente', ['tipo', 'titulo', 'vence', 'visible_al_colaborador']),
    'monitoreo.ReglaComportamiento': ('Regla de comportamiento', ['nombre', 'patrones', 'minutos_minimos', 'riesgo', 'accion', 'activa']),
    'monitoreo.PerfilMonitoreo': ('Perfil de monitoreo', ['nombre', 'monitorear', 'capturas', 'capturas_cada_min', 'desenfocar_capturas']),
    'monitoreo.Incidencia': ('Incidencia', ['estado']),
}


def _clave(instancia):
    return f'{instancia._meta.app_label}.{instancia.__class__.__name__}'


def _antes(sender, instance, **kwargs):
    if _clave(instance) not in VIGILADOS or not instance.pk:
        instance._auditoria_antes = None
        return
    viejo = sender.objects.filter(pk=instance.pk).values(*VIGILADOS[_clave(instance)][1]).first()
    instance._auditoria_antes = viejo


def _despues(sender, instance, created, raw=False, **kwargs):
    clave = _clave(instance)
    if raw or clave not in VIGILADOS:
        return
    nombre, campos = VIGILADOS[clave]
    ahora = {c: _valor(getattr(instance, c, None)) for c in campos}
    antes = getattr(instance, '_auditoria_antes', None)
    # Las automáticas (agente, marcajes propios, resultados guardados por el sistema) no llevan usuario de la
    # plataforma administrativa: solo se audita lo que hace alguien con sesión, y nunca su propio marcaje normal.
    usuario = usuario_actual()
    if usuario is None:
        return
    if clave == 'asistencia.Marcaje' and created and getattr(instance, 'origen', '') != 'MANUAL':
        return
    if created:
        auditar(f'Creó {nombre.lower()}', _descripcion(instance), None, ahora, usuario)
        return
    if antes is None:
        return
    cambios_antes = {c: _valor(antes.get(c)) for c in campos if _valor(antes.get(c)) != ahora[c]}
    if cambios_antes:
        auditar(f'Cambió {nombre.lower()}', _descripcion(instance), cambios_antes, {c: ahora[c] for c in cambios_antes}, usuario)
    if clave == 'organizacion.PerfilUsuario' and 'salario_mensual' in cambios_antes:
        from .models import CambioSalarial
        CambioSalarial.objects.create(usuario=instance.user, fecha=timezone.localdate(), anterior=antes.get('salario_mensual'),
                                      nuevo=instance.salario_mensual, registrado_por=usuario)


def _borrado(sender, instance, **kwargs):
    clave = _clave(instance)
    if clave in VIGILADOS and usuario_actual() is not None:
        nombre, campos = VIGILADOS[clave]
        auditar(f'Borró {nombre.lower()}', _descripcion(instance), {c: _valor(getattr(instance, c, None)) for c in campos}, None)


def _descripcion(instance):
    for attr in ('usuario', 'user', 'evaluado', 'colaborador'):
        persona = getattr(instance, attr, None)
        if persona is not None and hasattr(persona, 'get_full_name'):
            return f'{instance} · {persona.get_full_name() or persona.username}'
    return str(instance)


def conectar():
    from django.apps import apps
    for clave in VIGILADOS:
        app_label, nombre = clave.split('.')
        try:
            modelo = apps.get_model(app_label, nombre)
        except LookupError:
            continue
        pre_save.connect(_antes, sender=modelo, dispatch_uid=f'aud-pre-{clave}')
        post_save.connect(_despues, sender=modelo, dispatch_uid=f'aud-post-{clave}')
        post_delete.connect(_borrado, sender=modelo, dispatch_uid=f'aud-del-{clave}')
