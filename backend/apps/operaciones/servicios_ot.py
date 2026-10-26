"""
Flujo de los formatos ADZONE: compuertas G0–G6, estados E1–E7, Órdenes de Área, traspasos con doble firma,
acta de entrega y cierre. Todo cambio pasa por aquí: deja historial, avisa a quien corresponde y
dispara las automatizaciones.
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.desempeno import servicios as tareas_srv
from apps.desempeno.models import PasoTarea, Tarea
from apps.desempeno.servicios import avisar, nombre
from .formatos import AREAS, AREAS_CONTENIDO, COLCHON, G0, VALIDACION_FINAL, VENTANAS, faltan
from .models import Acta, AreaConfig, EventoOrden, Firma, OrdenArea, OrdenTrabajo, SolicitudCambio, Traspaso
from .permisos import es_coordinacion, es_finanzas, es_gerencia

G0_TEXTOS = [t for _, t in G0]
G0_ANTICIPO = dict(G0)['anticipo']
PRIORIDAD_TAREA = {'N': 'MEDIA', 'U': 'ALTA', 'E': 'ALTA'}


class ErrorFlujo(Exception):
    """Algo que falta para avanzar. El mensaje se muestra tal cual."""


def disparar(evento, objeto, quien=None):
    from apps.automatizaciones.motor import disparar as d
    d(evento, objeto, quien=quien)


def registrar(orden, usuario, texto, detalle=''):
    EventoOrden.objects.create(orden=orden, usuario=usuario, texto=texto[:255], detalle=detalle or '')


def enlace(orden, oa=None):
    return f"/ordenes/{orden.pk}" + (f"/areas/{oa.pk}" if oa else '')


def coordinadores():
    from django.db.models import Q
    return list(User.objects.filter(is_active=True).filter(Q(groups__name='Coordinación') | Q(is_staff=True)).distinct())


def supervisores_de(codigo):
    from .permisos import areas_que_supervisa
    conf = AreaConfig.de(codigo)
    asignados = list(conf.supervisores.filter(is_active=True))
    if asignados:
        return asignados
    from .servicios import jefes_de_departamento
    return jefes_de_departamento(conf.departamento_id) if conf.departamento_id else [u for u in coordinadores() if codigo in areas_que_supervisa(u)]


def finanzas():
    return [u for u in User.objects.filter(is_active=True) if es_finanzas(u)]


# ------------------------------------------------------------------ Fecha comprometida (F-01 §4)
def sumar_habiles(desde, dias):
    """Suma días hábiles (lunes a viernes), redondeando hacia arriba."""
    restantes = int(Decimal(dias).to_integral_value(rounding=ROUND_HALF_UP)) if dias else 0
    fecha = desde
    while restantes > 0:
        fecha += timedelta(days=1)
        if fecha.weekday() < 5:
            restantes -= 1
    return fecha


def cola_del_area(codigo, excluir_orden=None):
    """Días de trabajo que ya esperan en el área: suma del tiempo estándar de sus OA abiertas."""
    qs = OrdenArea.objects.filter(area=codigo, estado__in=['EMITIDA', 'RECIBIDA', 'EN_EJECUCION', 'EN_APROBACION'])
    if excluir_orden:
        qs = qs.exclude(orden=excluir_orden)
    total = qs.aggregate(t=Sum('tiempo_estandar_dias'))['t'] or Decimal('0')
    personas = max(1, len(supervisores_de(codigo)))  # aproximación: el área trabaja en paralelo por cada responsable
    return (Decimal(total) / personas).quantize(Decimal('0.1'))


def calcular_compromiso(orden, plan=None, hoy=None):
    """
    Fecha comprometida = hoy + (tiempo estándar del camino + cola del área más cargada + aprobación del cliente) × (1 + colchón).
    Las áreas con la misma secuencia van en paralelo: cuenta la más larga de cada secuencia.
    """
    hoy = hoy or timezone.localdate()
    plan = plan if plan is not None else orden.plan_areas
    por_secuencia = {}
    for fila in plan:
        sec = int(fila.get('secuencia') or 1)
        estandar = Decimal(str(fila.get('tiempo_estandar_dias') or 0))
        por_secuencia[sec] = max(por_secuencia.get(sec, Decimal('0')), estandar)
    estandar = sum(por_secuencia.values(), Decimal('0'))
    cola = max([cola_del_area(f['area'], orden if orden.pk else None) for f in plan if f.get('area') in AREAS] or [Decimal('0')])
    requiere_aprobacion = any(AREAS.get(f.get('area'), {}).get('requiere_g4') for f in plan)
    aprobacion = Decimal(orden.rondas_incluidas) if requiere_aprobacion else Decimal('0')  # 24 h × rondas
    colchon = COLCHON.get(orden.prioridad, 20)
    total = (estandar + cola + aprobacion) * (Decimal(100 + colchon) / 100)
    horas = sum((Decimal(str(f.get('horas_estimadas') or 0)) for f in plan), Decimal('0'))
    return {'tiempo_estandar_dias': estandar, 'cola_dias': cola, 'aprobacion_dias': aprobacion, 'colchon_pct': colchon,
            'dias_habiles': total.quantize(Decimal('0.1')), 'fecha_compromiso': sumar_habiles(hoy, total), 'horas_estimadas': horas,
            'anticipacion': anticipacion(plan, orden.fecha_requerida, hoy)}


def habiles_entre(desde, hasta):
    n, d = 0, desde
    while d < hasta:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def anticipacion(plan, fecha_requerida, hoy=None):
    """
    Ventanas de anticipación del contenido (Marketing, Diseño, Audiovisuales):
    ideal 15 días calendario, seguro 10, emergencia 7 días hábiles (solo con plantillas y copys aprobados).
    """
    if not fecha_requerida or not any(f.get('area') in AREAS_CONTENIDO for f in plan):
        return None
    hoy = hoy or timezone.localdate()
    if isinstance(fecha_requerida, str):
        from datetime import date
        fecha_requerida = date.fromisoformat(fecha_requerida[:10])
    dias = (fecha_requerida - hoy).days
    habiles = habiles_entre(hoy, fecha_requerida)
    if dias >= VENTANAS['ideal']:
        nivel, texto = 'ideal', "Ventana ideal: hay margen para trabajar con excelencia y corregir."
    elif dias >= VENTANAS['seguro']:
        nivel, texto = 'seguro', "Ventana segura: se mantiene la calidad sin improvisar."
    elif habiles >= VENTANAS['emergencia_habiles']:
        nivel, texto = 'emergencia', "Emergencia: solo si hay plantillas, copys aprobados y automatizaciones listas."
    else:
        nivel, texto = 'insuficiente', (f"Menos de {VENTANAS['emergencia_habiles']} días hábiles: por debajo de la ventana mínima. "
                                         "Negocia la fecha con el cliente o márcala como emergencia.")
    return {'dias': dias, 'habiles': habiles, 'nivel': nivel, 'texto': texto}


# ------------------------------------------------------------------ G0 · apertura (Comercial → Coordinación)
def al_solicitar(orden, quien):
    orden.g0_entregada_por = quien
    orden.g0_entregada_fecha = timezone.now()
    orden.save(update_fields=['g0_entregada_por', 'g0_entregada_fecha'])
    registrar(orden, quien, f"Solicitud {orden.solicitud} entregada a Coordinación (G0)")
    avisar(coordinadores(), 'ORDEN', f"Nueva solicitud {orden.solicitud}: {orden.titulo}",
           f"{nombre(quien)} la entregó para {orden.cliente}. Revisa la compuerta G0.", enlace=enlace(orden), excepto=quien)
    disparar('ORDEN_CREADA', orden, quien)


def confirmar_anticipo(orden, quien, fuente='MANUAL'):
    orden.anticipo_confirmado = True
    orden.anticipo_fuente = fuente
    orden.anticipo_confirmado_por = quien
    orden.anticipo_fecha = timezone.now()
    orden.g0 = {**orden.g0, G0_ANTICIPO: True}
    orden.save(update_fields=['anticipo_confirmado', 'anticipo_fuente', 'anticipo_confirmado_por', 'anticipo_fecha', 'g0'])
    registrar(orden, quien, "Anticipo confirmado" + (" (pago leído de Cashflow)" if fuente == 'CASHFLOW' else " por Administración"))
    avisar(coordinadores(), 'ORDEN', f"Anticipo confirmado: {orden.codigo}", orden.titulo, enlace=enlace(orden), excepto=quien)


def pagado_de(orden):
    from apps.finanzas.models import Factura
    return sum((f.pagado for f in Factura.objects.filter(orden=orden).exclude(estado='ANULADA')), Decimal('0'))


def saldo_de(orden):
    """Lo que el cliente todavía debe de esta OT: saldo de sus facturas emitidas + lo que falta por facturar (sin ITBIS)."""
    from apps.finanzas.models import Factura
    facturas = list(Factura.objects.filter(orden=orden).exclude(estado__in=['ANULADA', 'BORRADOR']))
    por_facturar = max(Decimal('0'), (orden.monto or Decimal('0')) - sum((f.subtotal for f in facturas), Decimal('0')))
    return sum((f.saldo for f in facturas), Decimal('0')) + por_facturar


def revisar_anticipo(orden):
    """Si los pagos de las facturas de la OT ya cubren el anticipo, la casilla G0 se marca sola."""
    if orden.anticipo_confirmado or not orden.anticipo_requerido:
        return False
    if pagado_de(orden) >= orden.anticipo_requerido:
        confirmar_anticipo(orden, None, 'CASHFLOW')
        return True
    return False


def autorizar_excepcion(orden, quien, motivo):
    if not es_gerencia(quien):
        raise ErrorFlujo("La excepción sin anticipo solo la autoriza Gerencia General.")
    if len((motivo or '').strip()) < 5:
        raise ErrorFlujo("Escribe el motivo de la excepción.")
    orden.excepcion_g0_por = quien
    orden.excepcion_g0_motivo = motivo.strip()
    orden.excepcion_g0_regularizar = timezone.now() + timedelta(hours=24)
    orden.save(update_fields=['excepcion_g0_por', 'excepcion_g0_motivo', 'excepcion_g0_regularizar'])
    registrar(orden, quien, "Excepción G0 autorizada por Gerencia General", f"{motivo}. Regularizar antes de 24 h.")
    avisar(finanzas(), 'FINANZAS', f"Excepción sin anticipo: {orden.codigo}",
           f"Gerencia autorizó iniciar sin anticipo. Regularizar antes de {orden.excepcion_g0_regularizar:%d/%m %H:%M}.",
           enlace=enlace(orden), excepto=quien)


def revisar_excepciones():
    """Tarea diaria: OT liberadas sin anticipo cuya regularización de 24 h ya venció."""
    vencidas = OrdenTrabajo.objects.filter(excepcion_g0_regularizar__lt=timezone.now(), anticipo_confirmado=False).exclude(
        estado__in=['CANCELADA', 'CERRADA'])
    from django.db.models import Q
    gerencia = list(User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True)))
    for orden in vencidas:
        avisar(finanzas() + gerencia, 'FINANZAS', f"Anticipo sin regularizar: {orden.codigo}",
               f"Liberada sin anticipo por excepción ({orden.excepcion_g0_motivo}). Venció el plazo de 24 h.", enlace=enlace(orden))
    return vencidas.count()


def faltan_g0(orden):
    pendientes = faltan(G0_TEXTOS, orden.g0)
    if G0_ANTICIPO in pendientes and orden.excepcion_g0_por_id:
        pendientes.remove(G0_ANTICIPO)
    return pendientes


@transaction.atomic
def liberar(orden, quien, fecha_compromiso=None):
    """Coordinación recibe conforme, numera la OT y emite las Órdenes de Área (E1)."""
    if not es_coordinacion(quien):
        raise ErrorFlujo("Solo Coordinación de Producción libera y numera las OT.")
    if orden.estado not in ('SOLICITADA', 'DEVUELTA'):
        raise ErrorFlujo("Esta OT ya fue liberada.")
    pendientes = faltan_g0(orden)
    if pendientes:
        raise ErrorFlujo("El área no inicia si falta una casilla. Falta: " + "; ".join(pendientes) + ".")
    plan = [f for f in orden.plan_areas if f.get('area') in AREAS]
    if not plan:
        raise ErrorFlujo("Indica las áreas que intervienen (sección 3).")
    calculo = calcular_compromiso(orden, plan)
    orden.fecha_compromiso = fecha_compromiso or orden.fecha_compromiso or calculo['fecha_compromiso']
    for k in ('tiempo_estandar_dias', 'cola_dias', 'aprobacion_dias', 'colchon_pct'):
        setattr(orden, k, calculo[k])
    orden.asignar_numero()
    orden.estado = 'LIBERADA'
    orden.aprobada_por = quien
    orden.responsable = orden.responsable or quien
    orden.fecha_aprobacion = timezone.now()
    orden.save()
    for fila in sorted(plan, key=lambda f: int(f.get('secuencia') or 1)):
        oa = OrdenArea.objects.create(
            orden=orden, area=fila['area'], secuencia=int(fila.get('secuencia') or 1),
            que_produce=(fila.get('que_produce') or AREAS[fila['area']]['nombre'])[:255],
            fecha_entrega_interna=fila.get('fecha_entrega_interna') or orden.fecha_compromiso,
            tiempo_estandar_dias=fila.get('tiempo_estandar_dias') or None, horas_estimadas=fila.get('horas_estimadas') or None,
            responsable_id=fila.get('responsable') or None, g1_entrega_por=quien,
            especificacion=fila.get('especificacion') or {})
        avisar(supervisores_de(oa.area), 'ORDEN', f"Orden de Área {oa.numero}", f"{oa.que_produce} · {orden.cliente}. Revisa la compuerta G1.",
               enlace=enlace(orden, oa), excepto=quien)
        disparar('OA_ESTADO', oa, quien)
    Traspaso.objects.create(orden=orden, compuerta='G0', que_entrega="OT Maestra completa (F-01)", entrega_area='Comercial',
                            entrega_por=orden.g0_entregada_por or orden.solicitada_por, recibe_area='Coordinación', recibe_por=quien,
                            recibe_fecha=timezone.now(), verificacion=orden.g0, resultado='ACEPTADO')
    registrar(orden, quien, f"Liberada como {orden.numero} (E1)", f"Fecha comprometida {orden.fecha_compromiso:%d/%m/%Y}. "
              f"Áreas: {', '.join(f['area'] for f in plan)}.")
    avisar([orden.solicitada_por, orden.asesor_comercial], 'ORDEN', f"Liberada: {orden.numero}",
           f"{orden.titulo}. Fecha comprometida {orden.fecha_compromiso:%d/%m/%Y}.", enlace=enlace(orden), excepto=quien)
    disparar('ORDEN_ESTADO', orden, quien)
    return orden


def rechazar_g0(orden, quien, causa, devuelto_a='Comercial'):
    if not es_coordinacion(quien):
        raise ErrorFlujo("Solo Coordinación rechaza en G0.")
    if len((causa or '').strip()) < 3:
        raise ErrorFlujo("Escribe la causa del rechazo.")
    orden.estado = 'DEVUELTA'
    orden.g0_rechazo = f"{causa.strip()} · devuelto a {devuelto_a} · {timezone.localtime():%d/%m/%Y %H:%M}"
    orden.save(update_fields=['estado', 'g0_rechazo'])
    Traspaso.objects.create(orden=orden, compuerta='G0', que_entrega="OT Maestra (F-01)", entrega_area='Comercial',
                            entrega_por=orden.g0_entregada_por or orden.solicitada_por, recibe_area='Coordinación', recibe_por=quien,
                            recibe_fecha=timezone.now(), verificacion=orden.g0, resultado='RECHAZADO', causa_rechazo=causa)
    registrar(orden, quien, "Rechazada en G0", orden.g0_rechazo)
    avisar([orden.solicitada_por, orden.asesor_comercial], 'ORDEN', f"Devuelta en G0: {orden.solicitud}", causa,
           enlace=enlace(orden), excepto=quien)


def reenviar(orden, quien):
    if orden.estado != 'DEVUELTA':
        raise ErrorFlujo("Solo se reenvía una solicitud devuelta.")
    orden.estado = 'SOLICITADA'
    orden.save(update_fields=['estado'])
    al_solicitar(orden, quien)


# ------------------------------------------------------------------ Órdenes de Área
def bloqueada_por(oa):
    """OA anteriores en la secuencia que todavía no terminan."""
    return list(oa.orden.areas.filter(secuencia__lt=oa.secuencia).exclude(estado__in=['TERMINADA', 'CANCELADA']))


@transaction.atomic
def recibir_g1(oa, quien, marcados, responsable, equipo=(), fecha_interna=None, forzar_secuencia=False):
    from .permisos import supervisa_area
    if not supervisa_area(quien, oa.area):
        raise ErrorFlujo(f"La compuerta G1 la firma quien supervisa {oa.get_area_display()}.")
    if oa.estado not in ('EMITIDA', 'RECHAZADA'):
        raise ErrorFlujo("Esta Orden de Área ya fue recibida.")
    antes = bloqueada_por(oa)
    if antes and not (forzar_secuencia and es_coordinacion(quien)):
        raise ErrorFlujo("Primero tiene que terminar: " + ", ".join(f"{a.numero} ({a.get_estado_display()})" for a in antes) + ".")
    lista = AREAS[oa.area]['g1']
    oa.g1 = {t: bool(marcados.get(t)) for t in lista}
    pendientes = faltan(lista, oa.g1)
    if pendientes:
        oa.save(update_fields=['g1'])
        raise ErrorFlujo("El área no inicia si falta una casilla. Falta: " + "; ".join(pendientes) + ".")
    if responsable is None:
        raise ErrorFlujo("Asigna al ejecutor.")
    oa.responsable = responsable
    oa.fecha_entrega_interna = fecha_interna or oa.fecha_entrega_interna or oa.orden.fecha_compromiso
    oa.g1_recibe_por = quien
    oa.g1_fecha = timezone.now()
    oa.g1_rechazo = ''
    oa.estado = 'RECIBIDA'
    oa.save()
    tarea = Tarea.objects.create(
        titulo=f"{oa.numero} · {oa.que_produce}"[:255], descripcion=oa.orden.descripcion, cliente=oa.orden.cliente.nombre,
        colaborador=responsable, asignada_por=quien, prioridad=PRIORIDAD_TAREA.get(oa.orden.prioridad, 'MEDIA'),
        fecha_limite=oa.fecha_entrega_interna, fecha_inicio=timezone.localdate(), orden=oa.orden, oa=oa,
        proyecto=oa.orden.proyecto, horas_estimadas=oa.horas_estimadas or ((oa.tiempo_estandar_dias or 0) * 8) or None)
    tarea.companeros.set([u for u in equipo if u.pk != responsable.pk])
    for i, etapa in enumerate(AREAS[oa.area]['etapas']):
        PasoTarea.objects.create(tarea=tarea, texto=etapa, orden=i)
    tareas_srv.al_asignar(tarea, quien)
    Traspaso.objects.create(orden=oa.orden, oa=oa, compuerta='G1', que_entrega=f"Orden de Área {oa.numero}", entrega_area='Coordinación',
                            entrega_por=oa.g1_entrega_por, recibe_area=oa.get_area_display(), recibe_por=quien,
                            recibe_fecha=timezone.now(), verificacion=oa.g1, resultado='ACEPTADO')
    registrar(oa.orden, quien, f"{oa.numero} recibida en G1 (E2)", f"Ejecutor: {nombre(responsable)}.")
    sincronizar_orden(oa.orden, quien)
    disparar('OA_ESTADO', oa, quien)
    return tarea


def rechazar_g1(oa, quien, marcados, causa):
    from .permisos import supervisa_area
    if not supervisa_area(quien, oa.area):
        raise ErrorFlujo(f"La compuerta G1 la firma quien supervisa {oa.get_area_display()}.")
    if len((causa or '').strip()) < 3:
        raise ErrorFlujo("Escribe la causa del rechazo.")
    oa.g1 = {t: bool((marcados or {}).get(t)) for t in AREAS[oa.area]['g1']}
    oa.estado = 'RECHAZADA'
    oa.g1_rechazo = f"{causa.strip()} · {timezone.localtime():%d/%m/%Y %H:%M}"
    oa.save(update_fields=['g1', 'estado', 'g1_rechazo'])
    Traspaso.objects.create(orden=oa.orden, oa=oa, compuerta='G1', que_entrega=f"Orden de Área {oa.numero}", entrega_area='Coordinación',
                            entrega_por=oa.g1_entrega_por, recibe_area=oa.get_area_display(), recibe_por=quien,
                            recibe_fecha=timezone.now(), verificacion=oa.g1, resultado='RECHAZADO', causa_rechazo=causa)
    registrar(oa.orden, quien, f"{oa.numero} rechazada en G1", causa)
    disparar('OA_ESTADO', oa, quien)
    avisar(coordinadores(), 'ORDEN', f"Rechazada en G1: {oa.numero}", causa, enlace=enlace(oa.orden, oa), excepto=quien)


def reemitir(oa, quien, nota=''):
    if not es_coordinacion(quien):
        raise ErrorFlujo("Solo Coordinación reemite una Orden de Área.")
    if oa.estado != 'RECHAZADA':
        raise ErrorFlujo("Solo se reemite una OA rechazada.")
    oa.estado = 'EMITIDA'
    oa.g1_entrega_por = quien
    oa.save(update_fields=['estado', 'g1_entrega_por'])
    registrar(oa.orden, quien, f"{oa.numero} reemitida", nota)
    avisar(supervisores_de(oa.area), 'ORDEN', f"Reemitida: {oa.numero}", nota or "Ya está completa. Revisa G1.",
           enlace=enlace(oa.orden, oa), excepto=quien)


def _puede_operar(oa, quien):
    from .permisos import supervisa_area
    ids = {oa.responsable_id, *[u.pk for t in oa.tareas.all() for u in t.companeros.all()]}
    return quien.pk in ids or supervisa_area(quien, oa.area) or es_coordinacion(quien)


def enviar_a_aprobacion(oa, quien):
    if not _puede_operar(oa, quien):
        raise ErrorFlujo("No trabajas en esta Orden de Área.")
    if oa.estado not in ('RECIBIDA', 'EN_EJECUCION'):
        raise ErrorFlujo("Solo se envía al cliente lo que está en ejecución.")
    if AREAS[oa.area].get('revision_interna') and not oa.revision_interna_por_id:
        raise ErrorFlujo("Antes del cliente va la revisión interna del Gerente de Marketing (checklist de validación final): "
                         "si no hay revisión humana, no hay publicación.")
    oa.estado = 'EN_APROBACION'
    oa.g4_ronda += 1
    oa.g4_primer_envio = oa.g4_primer_envio or timezone.now()
    oa.save(update_fields=['estado', 'g4_ronda', 'g4_primer_envio'])
    registrar(oa.orden, quien, f"{oa.numero} enviada al cliente (G4, ronda {oa.g4_ronda}) · E4")
    sincronizar_orden(oa.orden, quien)
    disparar('OA_ESTADO', oa, quien)


def pedir_revision(oa, quien):
    """El ejecutor avisa al Gerente de Marketing que la propuesta está lista para la revisión interna."""
    if not _puede_operar(oa, quien):
        raise ErrorFlujo("No trabajas en esta Orden de Área.")
    if not AREAS[oa.area].get('revision_interna'):
        raise ErrorFlujo("Esta área no lleva revisión interna antes del cliente.")
    if oa.estado not in ('RECIBIDA', 'EN_EJECUCION'):
        raise ErrorFlujo("La Orden de Área no está en ejecución.")
    registrar(oa.orden, quien, f"{oa.numero}: propuesta lista para revisión interna")
    avisar(supervisores_de(oa.area), 'ORDEN', f"Revisión interna: {oa.numero}", f"{nombre(quien)} subió la propuesta de «{oa.que_produce}».",
           enlace=enlace(oa.orden, oa), excepto=quien)


def revisar_interna(oa, quien, marcados, aprobar, comentario=''):
    """Revisión interna del Gerente de Marketing con el checklist de validación final, antes de mostrar al cliente."""
    from .permisos import supervisa_area
    if not supervisa_area(quien, oa.area):
        raise ErrorFlujo("La revisión interna la hace el Gerente de Marketing (supervisor del área).")
    if oa.estado not in ('RECIBIDA', 'EN_EJECUCION'):
        raise ErrorFlujo("La Orden de Área no está en ejecución.")
    oa.revision_interna = {t: bool((marcados or {}).get(t)) for t in VALIDACION_FINAL}
    oa.revision_interna_comentario = (comentario or '').strip()
    if aprobar:
        pendientes = faltan(VALIDACION_FINAL, oa.revision_interna)
        if pendientes:
            oa.save(update_fields=['revision_interna', 'revision_interna_comentario'])
            raise ErrorFlujo("Nada sale sin el checklist completo. Falta: " + "; ".join(pendientes) + ".")
        oa.revision_interna_por = quien
        oa.revision_interna_fecha = timezone.now()
        oa.save(update_fields=['revision_interna', 'revision_interna_comentario', 'revision_interna_por', 'revision_interna_fecha'])
        registrar(oa.orden, quien, f"{oa.numero}: revisión interna aprobada", comentario)
        avisar([oa.responsable], 'ORDEN', f"Visto bueno interno: {oa.numero}", "Ya se puede enviar al cliente (G4).",
               enlace=enlace(oa.orden, oa), excepto=quien)
    else:
        if len(oa.revision_interna_comentario) < 3:
            raise ErrorFlujo("Escribe qué ajustes pides.")
        oa.revision_interna_por = None
        oa.revisiones_internas_devueltas += 1
        oa.save(update_fields=['revision_interna', 'revision_interna_comentario', 'revision_interna_por', 'revisiones_internas_devueltas'])
        registrar(oa.orden, quien, f"{oa.numero}: ajustes pedidos en la revisión interna", comentario)
        avisar([oa.responsable, *[u for t in oa.tareas.all() for u in t.companeros.all()]], 'DEVUELTA',
               f"Ajustes internos: {oa.numero}", comentario, enlace=enlace(oa.orden, oa), excepto=quien)


def registrar_g4(oa, quien, aprobado, canales, aprobado_por='', version='', con_cambios=False, comentario=''):
    if not _puede_operar(oa, quien):
        raise ErrorFlujo("No trabajas en esta Orden de Área.")
    if oa.estado != 'EN_APROBACION':
        raise ErrorFlujo("La Orden de Área no está esperando al cliente.")
    if aprobado and not canales:
        raise ErrorFlujo("Marca por dónde aprobó el cliente (WhatsApp archivado, correo, firma…): la aprobación tiene que ser por escrito.")
    if aprobado and len((aprobado_por or '').strip()) < 2:
        raise ErrorFlujo("Anota quién aprobó.")
    oa.g4_aprobado = bool(aprobado)
    oa.g4_canales = canales or []
    oa.g4_fecha = timezone.now()
    oa.g4_aprobado_por = (aprobado_por or '').strip()
    oa.g4_version = version or ''
    oa.g4_con_cambios = bool(con_cambios)
    oa.estado = 'EN_EJECUCION'
    oa.save()
    aviso = None
    if aprobado:
        registrar(oa.orden, quien, f"{oa.numero}: cliente aprobó (G4)", f"{aprobado_por} · {', '.join(canales)} · versión {version}")
    else:
        registrar(oa.orden, quien, f"{oa.numero}: cliente pidió cambios (ronda {oa.g4_ronda})", comentario)
        if AREAS[oa.area].get('revision_interna'):  # la nueva versión vuelve a pasar por la revisión interna
            oa.revision_interna_por = None
            oa.save(update_fields=['revision_interna_por'])
        if oa.g4_ronda >= oa.orden.rondas_incluidas:
            aviso = (f"Ya van {oa.g4_ronda} rondas y la cotización incluye {oa.orden.rondas_incluidas}. "
                     "La siguiente se cobra: registra una Solicitud de Cambio (F-14).")
            avisar(coordinadores(), 'ORDEN', f"Rondas agotadas: {oa.numero}", aviso, enlace=enlace(oa.orden, oa), excepto=quien)
    disparar('OA_ESTADO', oa, quien)
    return aviso


def validar_g3(oa, quien, marcados, observaciones=''):
    """Se llama al validar la tarea de la OA: el supervisor firma el control de calidad interno."""
    lista = AREAS[oa.area]['g3']
    oa.g3 = {t: bool((marcados or {}).get(t)) for t in lista}
    pendientes = faltan(lista, oa.g3)
    if pendientes:
        raise ErrorFlujo("Control de calidad (G3) incompleto. Falta: " + "; ".join(pendientes) + ".")
    if oa.requiere_g4 and not oa.g4_aprobado:
        raise ErrorFlujo(AREAS[oa.area].get('nota_g4') or "No se entrega sin la aprobación escrita del cliente (G4).")
    oa.g3_resultado = 'APROBADO'
    oa.g3_observaciones = observaciones or ''
    oa.g3_supervisor = quien
    oa.g3_fecha = timezone.now()
    oa.save(update_fields=['g3', 'g3_resultado', 'g3_observaciones', 'g3_supervisor', 'g3_fecha'])
    registrar(oa.orden, quien, f"{oa.numero}: control de calidad aprobado (G3)", observaciones)


def rechazar_g3(oa, quien, marcados, observaciones, causa_retrabajo=None):
    oa.g3 = {t: bool((marcados or {}).get(t)) for t in AREAS[oa.area]['g3']}
    oa.g3_resultado = 'RECHAZADO'
    oa.g3_observaciones = observaciones or ''
    oa.g3_supervisor = quien
    oa.g3_fecha = timezone.now()
    campos = ['g3', 'g3_resultado', 'g3_observaciones', 'g3_supervisor', 'g3_fecha']
    if causa_retrabajo:
        oa.pase_retrabajo += 1
        campos.append('pase_retrabajo')
        SolicitudCambio.objects.create(orden=oa.orden, oa=oa, tipo='RETRABAJO', clasificacion=[causa_retrabajo],
                                       descripcion=observaciones or causa_retrabajo, area_responsable=oa.area, solicitado_por=quien)
    oa.save(update_fields=campos)
    registrar(oa.orden, quien, f"{oa.numero}: control de calidad rechazado (G3)", observaciones)


def traspasar(oa, quien, marcados, destino_oa=None, que_entrega=''):
    """G2/G5: el área entrega con su lista de salida; el trabajo no avanza hasta que quien recibe firma."""
    if not _puede_operar(oa, quien):
        raise ErrorFlujo("No trabajas en esta Orden de Área.")
    if oa.g3_resultado != 'APROBADO':
        raise ErrorFlujo("Primero el supervisor firma el control de calidad (G3): se hace al validar la tarea.")
    if oa.traspasos.filter(compuerta__in=['G2', 'G5'], resultado='PENDIENTE').exists():
        raise ErrorFlujo("Ya hay un traspaso esperando la firma de quien recibe.")
    lista = AREAS[oa.area]['g2']
    oa.g2 = {t: bool((marcados or {}).get(t)) for t in lista}
    oa.save(update_fields=['g2'])
    pendientes = faltan(lista, oa.g2)
    if pendientes:
        raise ErrorFlujo("Sin la lista de salida completa el trabajo no avanza. Falta: " + "; ".join(pendientes) + ".")
    if destino_oa is not None and destino_oa.orden_id != oa.orden_id:
        raise ErrorFlujo("El destino tiene que ser un área de la misma OT.")
    t = Traspaso.objects.create(
        orden=oa.orden, oa=oa, destino_oa=destino_oa, compuerta='G2' if destino_oa else 'G5',
        que_entrega=(que_entrega or oa.que_produce)[:2000], entrega_area=oa.get_area_display(), entrega_por=quien,
        recibe_area=destino_oa.get_area_display() if destino_oa else 'Coordinación', verificacion={})
    destinatarios = supervisores_de(destino_oa.area) if destino_oa else coordinadores()
    avisar(destinatarios, 'ORDEN', f"Traspaso por recibir: {oa.numero}", f"{t.que_entrega}. Verifica y firma la recepción.",
           enlace=enlace(oa.orden, oa), excepto=quien)
    registrar(oa.orden, quien, f"{oa.numero}: entregada en {t.compuerta} a {t.recibe_area}", t.que_entrega)
    disparar('TRASPASO', t, quien)
    return t


def puede_recibir_traspaso(t, quien):
    from .permisos import supervisa_area
    if t.destino_oa_id:
        return supervisa_area(quien, t.destino_oa.area) or es_coordinacion(quien)
    return es_coordinacion(quien)


@transaction.atomic
def recibir_traspaso(t, quien, verificacion, aceptar, causa=''):
    if t.resultado != 'PENDIENTE':
        raise ErrorFlujo("Este traspaso ya fue firmado.")
    if not puede_recibir_traspaso(t, quien):
        raise ErrorFlujo(f"Firma la recepción quien supervisa {t.recibe_area}.")
    if quien.pk == t.entrega_por_id:
        raise ErrorFlujo("La doble firma tiene que ser de dos personas distintas.")
    from .formatos import VERIFICACION_TRASPASO
    t.verificacion = {x: bool((verificacion or {}).get(x)) for x in VERIFICACION_TRASPASO}
    t.recibe_por = quien
    t.recibe_fecha = timezone.now()
    oa = t.oa
    if aceptar:
        if not all(t.verificacion.get(x) for x in ('Completo según especificación', 'Identificado con No. OT')):
            raise ErrorFlujo("Para aceptar, verifica al menos que está completo según especificación e identificado con No. OT.")
        t.resultado = 'ACEPTADO'
        t.save()
        oa.estado = 'TERMINADA'
        oa.fecha_terminada = timezone.now()
        oa.save(update_fields=['estado', 'fecha_terminada'])
        registrar(oa.orden, quien, f"{oa.numero} terminada (E5): traspaso firmado por {t.recibe_area}")
        disparar('OA_ESTADO', oa, quien)
        avisar([oa.responsable], 'ORDEN', f"Traspaso aceptado: {oa.numero}", f"Recibió {nombre(quien)}.", enlace=enlace(oa.orden, oa), excepto=quien)
    else:
        if len((causa or '').strip()) < 3:
            raise ErrorFlujo("Escribe la causa del rechazo y a quién se devuelve.")
        t.resultado = 'RECHAZADO'
        t.causa_rechazo = causa.strip()
        t.save()
        oa.g3_resultado = ''
        oa.estado = 'EN_EJECUCION'
        oa.pase_retrabajo += 1
        oa.save(update_fields=['g3_resultado', 'estado', 'pase_retrabajo'])
        for tarea in oa.tareas.filter(estado='COMPLETADA'):
            tarea.estado = 'EN_PROGRESO'
            tarea.comentario_revision = f"Traspaso rechazado por {t.recibe_area}: {causa}"
            tarea.rondas_revision += 1
            tarea.save(update_fields=['estado', 'comentario_revision', 'rondas_revision'])
            tareas_srv.registrar(tarea, quien, 'DEVUELTA', tarea.comentario_revision)
        registrar(oa.orden, quien, f"{oa.numero}: traspaso rechazado por {t.recibe_area}", causa)
        avisar([oa.responsable, *supervisores_de(oa.area)], 'DEVUELTA', f"Traspaso rechazado: {oa.numero}", causa,
               enlace=enlace(oa.orden, oa), excepto=quien)
    sincronizar_orden(oa.orden, quien)
    return t


def sincronizar_desde_tarea(tarea, quien):
    """La OA sigue a su tarea: empezar → E3."""
    oa = tarea.oa
    if oa is None:
        return
    if tarea.estado in ('EN_PROGRESO', 'EN_REVISION') and oa.estado == 'RECIBIDA':
        oa.estado = 'EN_EJECUCION'
        oa.save(update_fields=['estado'])
        registrar(oa.orden, quien, f"{oa.numero} en ejecución (E3)")
        sincronizar_orden(oa.orden, quien)
        disparar('OA_ESTADO', oa, quien)


def sincronizar_orden(orden, quien=None):
    """La OT sigue a sus áreas: alguna recibida → en producción; todas terminadas → lista para entregar."""
    if orden.estado not in ('LIBERADA', 'EN_PRODUCCION', 'LISTA'):
        return
    estados = list(orden.areas.exclude(estado='CANCELADA').values_list('estado', flat=True))
    if not estados:
        return
    if all(e == 'TERMINADA' for e in estados):
        nuevo = 'LISTA'
    elif any(e in ('RECIBIDA', 'EN_EJECUCION', 'EN_APROBACION', 'TERMINADA') for e in estados):
        nuevo = 'EN_PRODUCCION'
    else:
        nuevo = 'LIBERADA'
    if nuevo != orden.estado:
        orden.estado = nuevo
        if nuevo == 'LISTA':
            orden.fecha_lista = timezone.now()
        orden.save(update_fields=['estado', 'fecha_lista'])
        registrar(orden, quien, f"OT {orden.get_estado_display()}")
        if nuevo == 'LISTA':
            avisar([orden.solicitada_por, orden.asesor_comercial, *coordinadores(), *finanzas()], 'ORDEN',
                   f"Lista para entregar: {orden.numero}", "Todas las áreas terminaron. Falta liberar la salida (G5) y el acta.",
                   enlace=enlace(orden), excepto=quien)
        disparar('ORDEN_ESTADO', orden, quien)


# ------------------------------------------------------------------ F-12 · Acta de entrega / instalación
def liberar_g5(acta, quien, marcados):
    from .formatos import G5_ACTA
    if not (es_finanzas(quien) or es_gerencia(quien)):
        raise ErrorFlujo("La liberación de salida (G5) la firma Administración.")
    textos = dict(G5_ACTA)
    acta.g5 = {t: bool((marcados or {}).get(t)) for t in textos.values()}
    saldo = saldo_de(acta.orden)
    pagado = acta.g5.get(textos['saldo']) and saldo <= 0
    autorizado = acta.g5.get(textos['autorizacion']) and es_gerencia(quien)
    if saldo > 0 and acta.g5.get(textos['saldo']):
        raise ErrorFlujo(f"El cliente todavía debe RD$ {saldo:,.2f} de esta OT. Sale solo con autorización de Gerencia General.")
    if not (pagado or autorizado):
        raise ErrorFlujo("Para liberar: saldo pagado, o autorización escrita de Gerencia General.")
    resto = [t for k, t in G5_ACTA if k not in ('saldo', 'autorizacion')]
    pendientes = faltan(resto, acta.g5)
    if pendientes:
        raise ErrorFlujo("Falta: " + "; ".join(pendientes) + ".")
    acta.liberada_por = quien
    acta.liberada_fecha = timezone.now()
    acta.saldo_al_liberar = saldo
    acta.save()
    registrar(acta.orden, quien, f"Salida liberada (G5) · acta {acta.numero}", f"Saldo al liberar: RD$ {saldo:,.2f}")
    avisar(coordinadores() + supervisores_de('INS'), 'ORDEN', f"Salida liberada: {acta.orden.numero}", "Ya se puede cargar el vehículo.",
           enlace=enlace(acta.orden), excepto=quien)


@transaction.atomic
def firmar_acta(acta, quien, datos):
    """Conformidad del cliente: firma en pantalla, o fotos y nombre si no puede firmar. Con esto la OT queda entregada (E6)."""
    from .formatos import VERIFICACION_SITIO
    from .permisos import supervisa_area
    if not (supervisa_area(quien, 'INS') or es_coordinacion(quien) or quien.pk in acta.orden.participantes_ids()
            or any(supervisa_area(quien, a.area) for a in acta.orden.areas.all())):
        raise ErrorFlujo("Firma el acta el supervisor de instalación o quien entrega.")
    if not acta.liberada_por_id:
        raise ErrorFlujo("Antes de salir, Administración libera la salida (G5).")
    if acta.firmada:
        raise ErrorFlujo("El acta ya está firmada.")
    nombre_cliente = (datos.get('cliente_nombre') or '').strip()
    imagen = datos.get('firma') or ''
    if len(nombre_cliente) < 3:
        raise ErrorFlujo("Anota el nombre de quien recibe.")
    if not datos.get('conformidad'):
        raise ErrorFlujo("Marca la conformidad del cliente.")
    if not imagen.startswith('data:image/'):
        if not acta.orden.archivos.filter(categoria='FOTO').exists():
            raise ErrorFlujo("Sin firma del cliente hace falta evidencia fotográfica: sube las fotos de la entrega.")
    for campo in ('hallazgos', 'material_devuelto', 'observaciones_cliente', 'garantia', 'direccion', 'contacto_sitio'):
        if campo in datos:
            setattr(acta, campo, (datos.get(campo) or '')[:2000])
    acta.items = [i for i in (datos.get('items') or acta.items) if isinstance(i, dict) and i.get('descripcion')][:30]
    acta.verificacion = {t: bool((datos.get('verificacion') or {}).get(t)) for t in VERIFICACION_SITIO}
    acta.conformidad = datos['conformidad']
    acta.instrucciones_mantenimiento = bool(datos.get('instrucciones_mantenimiento'))
    acta.proxima_revision = datos.get('proxima_revision') or None
    acta.supervisor = quien
    acta.firmada = True
    acta.save()
    Firma.objects.create(orden=acta.orden, contexto='ACTA', rol='Cliente', nombre=nombre_cliente,
                         documento=(datos.get('cliente_cedula') or '')[:20], imagen=imagen[:400000])
    Firma.objects.create(orden=acta.orden, contexto='ACTA', rol='Supervisor de instalación', usuario=quien, nombre=nombre(quien))
    orden = acta.orden
    orden.estado = 'ENTREGADA'
    orden.fecha_entrega = acta.fecha
    orden.recibido_por = nombre_cliente
    orden.save(update_fields=['estado', 'fecha_entrega', 'recibido_por'])
    registrar(orden, quien, f"Entregada (E6) · acta {acta.numero} firmada", f"Recibió {nombre_cliente} · {acta.get_conformidad_display()}")
    avisar([orden.solicitada_por, orden.asesor_comercial, *finanzas()], 'ORDEN', f"Entregada: {orden.numero}",
           f"Acta firmada por {nombre_cliente}. Ya se puede facturar.", enlace=enlace(orden), excepto=quien)
    disparar('ORDEN_ESTADO', orden, quien)


# ------------------------------------------------------------------ Costos y cierre (G6)
def costos_oa(oa):
    from apps.tiempo.models import RegistroTiempo
    registros = RegistroTiempo.objects.filter(tarea__oa=oa, fin__isnull=False).select_related('usuario__perfil')
    minutos = sum(r.minutos for r in registros)
    mano_obra = sum((Decimal(r.minutos) / 60 * (getattr(r.usuario.perfil, 'costo_hora', None) or 0) for r in registros), Decimal('0'))
    materiales = sum((v.costo_total for v in oa.vales.filter(estado__in=['DESPACHADO', 'CERRADO']).prefetch_related('lineas')), Decimal('0'))
    desperdicio = sum((l.desperdicio * l.costo_unitario for v in oa.vales.all() for l in v.lineas.all()), Decimal('0'))
    retrabajo = oa.cambios.filter(tipo='RETRABAJO').aggregate(t=Sum('costo_retrabajo'))['t'] or Decimal('0')
    materiales_total = materiales + oa.otros_materiales
    total = mano_obra + materiales_total + oa.servicios_externos + retrabajo
    q = lambda x: Decimal(x).quantize(Decimal('0.01'))  # noqa: E731
    return {'horas': round(minutos / 60, 1), 'mano_obra': q(mano_obra), 'materiales': q(materiales_total), 'desperdicio': q(desperdicio),
            'servicios_externos': q(oa.servicios_externos), 'retrabajo': q(retrabajo), 'total': q(total)}


def costos_orden(orden):
    filas = {oa.numero: costos_oa(oa) for oa in orden.areas.exclude(estado='CANCELADA')}
    gastos = sum((g.monto for g in orden.gastos.all()), Decimal('0'))
    total = sum((c['total'] for c in filas.values()), Decimal('0')) + gastos
    cotizado = orden.monto or Decimal('0')
    return {'areas': filas, 'gastos': gastos, 'costo_real': total.quantize(Decimal('0.01')), 'cotizado': cotizado,
            'margen': (cotizado - total).quantize(Decimal('0.01')),
            'margen_pct': round(float((cotizado - total) / cotizado * 100), 1) if cotizado else None}


@transaction.atomic
def cerrar(orden, quien):
    """G6: Administración cierra con acta firmada, factura emitida y el costo real calculado (E7)."""
    from apps.finanzas.models import Factura
    if not (es_finanzas(quien) or es_gerencia(quien)):
        raise ErrorFlujo("El cierre (G6) lo firma Administración.")
    if orden.estado != 'ENTREGADA':
        raise ErrorFlujo("Sin acta firmada no se cierra la OT.")
    facturas = Factura.objects.filter(orden=orden, estado__in=['EMITIDA', 'PAGADA'])
    pendiente = (orden.monto or Decimal('0')) - sum((f.subtotal for f in facturas), Decimal('0'))
    if pendiente > 0 or not facturas.exists():
        raise ErrorFlujo(f"Falta facturar RD$ {max(pendiente, Decimal('0')):,.2f} de esta OT (factura emitida).")
    if orden.areas.filter(estado__in=OrdenArea.ABIERTAS).exists():
        raise ErrorFlujo("Hay Órdenes de Área sin terminar.")
    costos = costos_orden(orden)
    orden.costo_real = costos['costo_real']
    orden.estado = 'CERRADA'
    orden.fecha_cierre = timezone.now()
    orden.cerrada_por = quien
    orden.save(update_fields=['costo_real', 'estado', 'fecha_cierre', 'cerrada_por'])
    Firma.objects.create(orden=orden, contexto='CIERRE_OT', rol='Administración', usuario=quien, nombre=nombre(quien))
    registrar(orden, quien, "Cerrada (E7) · G6", f"Costo real RD$ {costos['costo_real']:,.2f} · margen RD$ {costos['margen']:,.2f}")
    disparar('ORDEN_ESTADO', orden, quien)
    return costos


def estado_e(orden):
    """La E del formato para mostrar: E1–E7 (o la etapa previa)."""
    return {'LIBERADA': 'E1', 'EN_PRODUCCION': 'E2–E5', 'LISTA': 'E5', 'ENTREGADA': 'E6', 'CERRADA': 'E7'}.get(orden.estado, '')


def firmas_pendientes_acta(acta):
    return not acta.firmada


__all__ = ['ErrorFlujo', 'Acta']
