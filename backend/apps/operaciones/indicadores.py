"""
Indicadores para la reunión semanal de producción: por área y de las OT.
Todo sale de lo que ya registra el flujo (compuertas, traspasos, incidencias, retrabajos y vales).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from .formatos import AREAS
from .models import Incidencia, OrdenArea, OrdenTrabajo, SolicitudCambio, Traspaso
from .permisos import areas_que_supervisa, es_coordinacion, es_finanzas, ve_montos


def _fecha(valor, defecto):
    try:
        return date.fromisoformat(str(valor)[:10]) if valor else defecto
    except ValueError:
        return defecto


def indicadores(user, desde=None, hasta=None):
    hoy = timezone.localdate()
    hasta = _fecha(hasta, hoy)
    desde = _fecha(desde, hasta - timedelta(days=6))
    rango = (desde, hasta)
    todas = es_coordinacion(user) or es_finanzas(user)
    codigos = list(AREAS) if todas else areas_que_supervisa(user)

    filas = []
    for codigo in codigos:
        oas = OrdenArea.objects.filter(area=codigo).exclude(orden__estado='CANCELADA')
        terminadas = list(oas.filter(estado='TERMINADA', fecha_terminada__date__range=rango))
        a_tiempo = [o for o in terminadas if o.fecha_entrega_interna and o.fecha_terminada.date() <= o.fecha_entrega_interna]
        abiertas = list(oas.filter(estado__in=OrdenArea.ABIERTAS))
        traspasos = Traspaso.objects.filter(oa__area=codigo, recibe_fecha__date__range=rango)
        retrabajos = SolicitudCambio.objects.filter(tipo='RETRABAJO', area_responsable=codigo, fecha__date__range=rango)
        causas = {}
        for r in retrabajos:
            for c in r.clasificacion or ['Sin clasificar']:
                causas[c] = causas.get(c, 0) + 1
        minutos = sum(i.minutos_perdidos for i in Incidencia.objects.filter(oa__area=codigo, fecha__date__range=rango))
        desperdicio = Decimal('0')
        try:
            from apps.almacen.models import LineaVale
            for linea in LineaVale.objects.filter(vale__oa__area=codigo, vale__fecha_despacho__date__range=rango):
                desperdicio += linea.desperdicio * linea.costo_unitario
        except Exception:  # noqa: BLE001 — almacén opcional
            pass
        rondas = [o.g4_ronda for o in terminadas if o.requiere_g4]
        # KPIs de adopción y eficiencia (uso estratégico de herramientas)
        primera = [o for o in terminadas if o.requiere_g4 and o.g4_aprobado]
        enviadas = oas.filter(g4_primer_envio__date__range=rango, g1_fecha__isnull=False)
        brief = [(o.g4_primer_envio - o.g1_fecha).total_seconds() / 3600 for o in enviadas]
        from apps.tiempo.models import RegistroTiempo
        con_estandar = [o for o in terminadas if o.horas_estimadas]
        estandar = sum((o.horas_estimadas for o in con_estandar), Decimal('0'))
        reales = sum(r.minutos for r in RegistroTiempo.objects.filter(tarea__oa__in=con_estandar, fin__isnull=False)) / 60 if con_estandar else 0
        filas.append({
            'area': codigo, 'nombre': AREAS[codigo]['nombre'],
            'terminadas': len(terminadas),
            'a_tiempo_pct': round(100 * len(a_tiempo) / len(terminadas)) if terminadas else None,
            'en_cola': sum(o.estado in ('EMITIDA', 'RECHAZADA') for o in abiertas),
            'en_curso': sum(o.estado in ('RECIBIDA', 'EN_EJECUCION', 'EN_APROBACION') for o in abiertas),
            'vencidas': sum(o.vencida for o in abiertas),
            'rechazos_g1': traspasos.filter(compuerta='G1', resultado='RECHAZADO').count(),
            'traspasos_rechazados': traspasos.filter(compuerta__in=['G2', 'G5'], resultado='RECHAZADO').count(),
            'traspasos_aceptados': traspasos.filter(compuerta__in=['G2', 'G5'], resultado='ACEPTADO').count(),
            'retrabajos': retrabajos.count(),
            'causas_retrabajo': causas,
            'minutos_perdidos': minutos,
            'desperdicio': desperdicio.quantize(Decimal('0.01')) if ve_montos(user) else None,
            'rondas_g4_promedio': round(sum(rondas) / len(rondas), 1) if rondas else None,
            'primera_aprobacion_pct': round(100 * sum(o.g4_ronda <= 1 for o in primera) / len(primera)) if primera else None,
            'brief_a_propuesta_h': round(sum(brief) / len(brief), 1) if brief else None,
            'horas_estandar': float(estandar) if con_estandar else None,
            'horas_reales': round(reales, 1) if con_estandar else None,
            'devoluciones_internas': sum(o.revisiones_internas_devueltas for o in terminadas),
        })

    ots = OrdenTrabajo.objects.all()
    entregadas = list(ots.filter(estado__in=['ENTREGADA', 'CERRADA'], fecha_entrega__range=rango))
    a_tiempo = [o for o in entregadas if o.a_tiempo]
    resumen = {
        'solicitadas': ots.filter(fecha_creacion__date__range=rango).count(),
        'liberadas': ots.filter(fecha_aprobacion__date__range=rango).count(),
        'devueltas_g0': Traspaso.objects.filter(compuerta='G0', resultado='RECHAZADO', recibe_fecha__date__range=rango).count(),
        'entregadas': len(entregadas),
        'a_tiempo_pct': round(100 * len(a_tiempo) / len(entregadas)) if entregadas else None,
        'en_produccion': ots.filter(estado__in=OrdenTrabajo.PRODUCCION).count(),
        'vencidas': sum(o.vencida for o in ots.filter(estado__in=['LIBERADA', 'EN_PRODUCCION', 'EN_PAUSA'])),
        'excepciones_sin_anticipo': ots.filter(excepcion_g0_por__isnull=False, fecha_aprobacion__date__range=rango).count(),
        'cambios_cobrables': SolicitudCambio.objects.filter(tipo='CAMBIO', estado='AUTORIZADA', fecha__date__range=rango).count(),
    }
    if ve_montos(user) and todas:
        cerradas = list(ots.filter(estado='CERRADA', fecha_cierre__date__range=rango).exclude(Q(monto__isnull=True) | Q(costo_real__isnull=True)))
        vendido = sum((o.monto for o in cerradas), Decimal('0'))
        costo = sum((o.costo_real for o in cerradas), Decimal('0'))
        resumen.update({'cerradas': len(cerradas), 'vendido': vendido, 'costo': costo,
                        'margen_pct': round(float((vendido - costo) / vendido * 100), 1) if vendido else None})
    return {'desde': desde, 'hasta': hasta, 'areas': filas, 'ot': resumen}
