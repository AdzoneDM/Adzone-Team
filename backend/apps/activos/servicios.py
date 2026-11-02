from datetime import timedelta

from django.utils import timezone

from .models import Activo, MovimientoActivo


def gestiona_activos(user):
    """Administración, Tecnología y Almacén registran y asignan equipos."""
    from apps.desempeno.permisos import es_administrador
    from apps.operaciones.permisos import es_almacen
    if not (user and user.is_authenticated):
        return False
    from apps.core.permisos import tiene
    return es_administrador(user) or es_almacen(user) or tiene(user, 'monitoreo.configurar')


def responsables():
    from apps.desempeno.permisos import administradores
    from apps.monitoreo.servicios import tecnologia
    gente = {u.pk: u for u in tecnologia()}
    if not gente:
        gente = {u.pk: u for u in administradores()}
    return list(gente.values())


def mover(activo, tipo, por, persona=None, costo=None, nota='', fecha=None):
    """Registra el movimiento y actualiza el estado del activo según el tipo."""
    hoy = fecha or timezone.localdate()
    if tipo == 'ASIGNACION':
        activo.asignado_a, activo.estado = persona, 'ASIGNADO'
    elif tipo == 'DEVOLUCION':
        persona = persona or activo.asignado_a
        activo.asignado_a, activo.estado = None, 'DISPONIBLE'
    elif tipo == 'MANTENIMIENTO':
        if activo.mantenimiento_cada_meses:
            activo.proximo_mantenimiento = hoy + timedelta(days=30 * activo.mantenimiento_cada_meses)
        if activo.estado in ('MANTENIMIENTO', 'DANADO'):
            activo.estado = 'ASIGNADO' if activo.asignado_a_id else 'DISPONIBLE'
    elif tipo == 'REPARACION':
        activo.estado = 'ASIGNADO' if activo.asignado_a_id else 'DISPONIBLE'
    elif tipo == 'DANO':
        activo.estado = 'DANADO'
    elif tipo == 'BAJA':
        activo.asignado_a, activo.estado = None, 'BAJA'
    activo.save()
    return MovimientoActivo.objects.create(activo=activo, tipo=tipo, fecha=hoy, persona=persona, costo=costo, nota=(nota or '')[:255],
                                           registrado_por=por)


def revisar(hoy=None):
    """Diario: mantenimientos vencidos o en los próximos 7 días y garantías que vencen en 30, una vez cada uno."""
    from apps.desempeno.servicios import avisar
    from apps.monitoreo.models import AlertaEnviada
    hoy = hoy or timezone.localdate()
    gente = responsables()
    enviados = 0
    for a in Activo.objects.exclude(estado='BAJA').filter(proximo_mantenimiento__isnull=False, proximo_mantenimiento__lte=hoy + timedelta(days=7)):
        ref = a.asignado_a or (gente[0] if gente else None)
        if ref is None:
            continue
        _, nueva = AlertaEnviada.objects.get_or_create(usuario=ref, clave=f'act-mant-{a.pk}-{a.proximo_mantenimiento:%Y%m%d}',
                                                       defaults={'tipo': 'ACTIVO', 'detalle': a.nombre[:255]})
        if nueva:
            avisar(gente, 'MONITOREO', f'Mantenimiento de {a.codigo} · {a.nombre}: {a.proximo_mantenimiento:%d/%m}',
                   'Regístralo en Activos cuando se haga.', enlace=f'/activos?ver={a.pk}')
            enviados += 1
    return enviados


def resumen():
    hoy = timezone.localdate()
    activos = list(Activo.objects.exclude(estado='BAJA'))
    return {
        'total': len(activos), 'asignados': sum(1 for a in activos if a.estado == 'ASIGNADO'),
        'disponibles': sum(1 for a in activos if a.estado == 'DISPONIBLE'), 'danados': sum(1 for a in activos if a.estado == 'DANADO'),
        'en_mantenimiento': sum(1 for a in activos if a.estado == 'MANTENIMIENTO'),
        'mantenimiento_vencido': sum(1 for a in activos if a.proximo_mantenimiento and a.proximo_mantenimiento < hoy),
        'costo': float(sum((a.costo or 0) for a in activos)),
        'valor_actual': float(sum((a.valor_actual(hoy) or 0) for a in activos)),
    }
