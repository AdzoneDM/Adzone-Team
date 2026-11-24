"""Estado de las cuentas: suspender, dar de baja, eliminar (sin borrar nada) y reactivar.

Una cuenta que no está ACTIVA no puede entrar ni mantener sesiones (`is_active=False`), pero conserva todo: tareas, asignaciones,
conversaciones, comentarios, evidencias e historial. Antes de apartar a alguien se ven sus pendientes y se pueden pasar a otra persona.
Cada cambio queda con quién lo hizo, cuándo y por qué (campos del perfil + historial de auditoría).
"""
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

SIN_ACCESO = ('SUSPENDIDA', 'INACTIVA', 'ELIMINADA')
ESTADOS = ('ACTIVA',) + SIN_ACCESO
ETIQUETA = {'ACTIVA': 'Activa', 'SUSPENDIDA': 'Suspendida', 'INACTIVA': 'Inactiva (baja)', 'ELIMINADA': 'Eliminada'}
ABIERTAS = ('PENDIENTE', 'EN_PROGRESO', 'BLOQUEADA', 'EN_REVISION')


def _nombre(u):
    return u.get_full_name() or u.username


def pendientes(usuario, limite=40):
    """Lo que `usuario` tiene a medias y habría que pasar a otra persona antes de apartarlo."""
    from apps.desempeno.models import Tarea, TareaRecurrente
    propias = Tarea.objects.filter(colaborador=usuario, estado__in=ABIERTAS).order_by('fecha_limite')
    como_companero = Tarea.objects.filter(companeros=usuario, estado__in=ABIERTAS).exclude(colaborador=usuario)
    por_revisar = Tarea.objects.filter(revisor=usuario, estado='EN_REVISION')
    recurrentes = TareaRecurrente.objects.filter(colaborador=usuario, activa=True)
    try:
        from apps.activos.models import Activo
        activos = Activo.objects.filter(asignado_a=usuario).count()
    except Exception:  # noqa: BLE001 (el módulo de activos es opcional aquí)
        activos = 0
    return {
        'tareas': propias.count(), 'como_companero': como_companero.count(), 'por_revisar': por_revisar.count(),
        'recurrentes': recurrentes.count(), 'activos': activos,
        'lista': [{'id': t.id, 'titulo': t.titulo, 'estado': t.estado, 'fecha_limite': t.fecha_limite} for t in propias[:limite]],
    }


def hay_pendientes(p):
    return bool(p['tareas'] or p['como_companero'] or p['por_revisar'] or p['recurrentes'])


@transaction.atomic
def reasignar(origen, destino, quien):
    """Pasa lo pendiente de `origen` a `destino`. El historial de cada tarea deja constancia de quién lo hizo y por qué."""
    from apps.desempeno import servicios
    from apps.desempeno.models import Tarea, TareaRecurrente
    hechas = 0
    for t in Tarea.objects.filter(colaborador=origen, estado__in=ABIERTAS):
        t.colaborador = destino
        t.save(update_fields=['colaborador'])
        t.companeros.remove(destino)
        servicios.registrar(t, quien, 'EDITADA', f"Reasignada de {_nombre(origen)} a {_nombre(destino)} (cuenta de {_nombre(origen)} apartada por {_nombre(quien)}).")
        servicios.avisar([destino], 'ASIGNADA', f"Te reasignaron: {t.titulo}", f"Antes la tenía {_nombre(origen)}. Entrega: {t.fecha_limite:%d/%m/%Y}.",
                         tarea=t, enlace='/mis-tareas', excepto=quien)
        hechas += 1
    for t in Tarea.objects.filter(companeros=origen, estado__in=ABIERTAS):
        t.companeros.remove(origen)
        if t.colaborador_id != destino.pk:
            t.companeros.add(destino)
        servicios.registrar(t, quien, 'EDITADA', f"{_nombre(origen)} salió de la tarea (cuenta apartada); la continúa {_nombre(destino)}.")
    revisadas = Tarea.objects.filter(revisor=origen).update(revisor=None)
    recurrentes = TareaRecurrente.objects.filter(colaborador=origen, activa=True).update(colaborador=destino)
    return {'tareas': hechas, 'revisor_quitado': revisadas, 'recurrentes': recurrentes}


def _cerrar_accesos(usuario):
    """Una cuenta apartada no mantiene sesiones ni recibe avisos en sus dispositivos."""
    from apps.core.models import SuscripcionPush
    from apps.core.seguridad import cerrar_sesiones
    cerrar_sesiones(usuario)
    SuscripcionPush.objects.filter(usuario=usuario).delete()


@transaction.atomic
def cambiar_estado(usuario, estado, quien, motivo='', hasta=None):
    """Pone la cuenta en `estado` y deja constancia (quién, cuándo, por qué). Devuelve el estado anterior."""
    from apps.talento.auditoria import auditar
    perfil = usuario.perfil
    anterior = perfil.estado_cuenta
    perfil.estado_cuenta = estado
    perfil.estado_motivo = (motivo or '')[:300] if estado != 'ACTIVA' else ''
    perfil.estado_desde = timezone.now()
    perfil.estado_por = quien
    perfil.suspendida_hasta = hasta if estado == 'SUSPENDIDA' else None
    perfil.save(update_fields=['estado_cuenta', 'estado_motivo', 'estado_desde', 'estado_por', 'suspendida_hasta'])
    activa = estado == 'ACTIVA'
    if usuario.is_active != activa:
        usuario.is_active = activa
        usuario.save(update_fields=['is_active'])
    if not activa:
        _cerrar_accesos(usuario)
    auditar(f'Cuenta: {ETIQUETA[anterior]} → {ETIQUETA[estado]}', f'{_nombre(usuario)} ({usuario.username})',
            antes={'estado': anterior}, despues={'estado': estado, 'motivo': perfil.estado_motivo, 'hasta': hasta.isoformat() if hasta else None},
            usuario=quien)
    return anterior


def reactivar_suspensiones_vencidas(hoy=None):
    """Las suspensiones con fecha de fin terminan solas (para el cron diario). Devuelve cuántas reactivó."""
    from apps.organizacion.models import PerfilUsuario
    hoy = hoy or timezone.localdate()
    n = 0
    for p in PerfilUsuario.objects.filter(estado_cuenta='SUSPENDIDA', suspendida_hasta__lte=hoy).select_related('user'):
        cambiar_estado(p.user, 'ACTIVA', None, motivo='Terminó la suspensión')
        n += 1
    return n
