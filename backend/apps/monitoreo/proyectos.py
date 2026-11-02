"""
Productividad por proyecto y por OT: horas del cronómetro, minutos de computadora en ese trabajo, tareas,
correcciones, estimado contra real y (para Finanzas y la dirección) costo de la mano de obra.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum

from apps.asistencia.servicios import rango
from .models import PRODUCTIVA, Actividad


def _f(v):
    return float(v) if v is not None else None


def _pct(a, b):
    return round(a / b * 100, 1) if b else None


def productividad(desde, hasta, usuarios=None, con_costos=False):
    """
    `usuarios`: ids a incluir (None = todos). Devuelve {'ordenes': [...], 'proyectos': [...], 'totales': {...}}.
    Las horas del período salen de los cronómetros que empezaron entre `desde` y `hasta`; el «estimado contra real»
    usa todas las horas de la OT o el proyecto, porque el presupuesto de horas es de toda la obra.
    """
    from apps.desempeno.models import Tarea
    from apps.operaciones.models import OrdenArea, OrdenTrabajo, Proyecto, SolicitudCambio
    from apps.tiempo.models import RegistroTiempo

    regs = RegistroTiempo.objects.filter(inicio__range=rango(desde, hasta)).filter(Q(orden__isnull=False) | Q(proyecto__isnull=False))
    if usuarios is not None:
        regs = regs.filter(usuario_id__in=usuarios)
    regs = list(regs.select_related('usuario__perfil'))
    costo_hora = {r.usuario_id: r.usuario.perfil.costo_hora for r in regs if hasattr(r.usuario, 'perfil')}

    # Minutos de computadora unidos a cada cronómetro
    pc = {f['registro_id']: f for f in Actividad.objects.filter(registro_id__in=[r.pk for r in regs]).values('registro_id').annotate(
        n_total=Count('id'), n_activos=Count('id', filter=Q(activos__gte=30)),
        n_productivos=Count('id', filter=Q(activos__gte=30, categoria=PRODUCTIVA)))}

    def vacio():
        return {'minutos': 0, 'facturables': 0, 'pc_total': 0, 'pc_activos': 0, 'pc_productivos': 0, 'costo': Decimal(0),
                'sin_costo': 0, 'personas': defaultdict(lambda: {'minutos': 0, 'pc_activos': 0, 'pc_productivos': 0})}

    grupos = {'orden': defaultdict(vacio), 'proyecto': defaultdict(vacio)}
    for r in regs:
        claves = []
        if r.orden_id:
            claves.append(('orden', r.orden_id))
        if r.proyecto_id:
            claves.append(('proyecto', r.proyecto_id))
        m = r.minutos_hasta_ahora()
        datos_pc = pc.get(r.pk, {})
        for tipo, pk in claves:
            g = grupos[tipo][pk]
            g['minutos'] += m
            g['facturables'] += m if r.facturable else 0
            for k in ('total', 'activos', 'productivos'):
                g[f'pc_{k}'] += datos_pc.get(f'n_{k}', 0)
            p = g['personas'][r.usuario_id]
            p['nombre'] = r.usuario.get_full_name() or r.usuario.username
            p['minutos'] += m
            p['pc_activos'] += datos_pc.get('n_activos', 0)
            p['pc_productivos'] += datos_pc.get('n_productivos', 0)
            if costo_hora.get(r.usuario_id):
                g['costo'] += costo_hora[r.usuario_id] * m / 60
            else:
                g['sin_costo'] += m

    def tareas_de(filtro):
        qs = Tarea.objects.filter(**filtro).exclude(estado='CANCELADA')
        if usuarios is not None:
            qs = qs.filter(colaborador_id__in=usuarios)
        del_periodo = qs.filter(estado='COMPLETADA', fecha_completada__range=(desde, hasta))
        return {
            'abiertas': qs.exclude(estado='COMPLETADA').count(),
            'validadas': del_periodo.count(),
            'a_la_primera': del_periodo.filter(rondas_revision=0).count(),
            'correcciones': del_periodo.aggregate(s=Sum('rondas_revision'))['s'] or 0,
            'horas_estimadas_tareas': _f(qs.aggregate(s=Sum('horas_estimadas'))['s']),
        }

    def horas_totales(filtro):
        qs = RegistroTiempo.objects.filter(**filtro)
        if usuarios is not None:
            qs = qs.filter(usuario_id__in=usuarios)
        return round(sum(r.minutos_hasta_ahora() for r in qs.only('minutos', 'fin', 'inicio')) / 60, 1)

    def fila(g, base):
        horas = round(g['minutos'] / 60, 1)
        d = {**base,
             'horas': horas, 'horas_facturables': round(g['facturables'] / 60, 1),
             'minutos_pc': g['pc_total'], 'minutos_pc_activos': g['pc_activos'],
             'productividad_pc': _pct(g['pc_productivos'], g['pc_activos']),
             'cobertura_pc': _pct(g['pc_total'], g['minutos']),
             'personas': sorted(({'id': k, 'nombre': v['nombre'], 'horas': round(v['minutos'] / 60, 1),
                                  'productividad_pc': _pct(v['pc_productivos'], v['pc_activos'])}
                                 for k, v in g['personas'].items()), key=lambda x: -x['horas'])}
        est, real = d.get('horas_estimadas'), d.get('horas_reales_total')
        d['desvio_horas_pct'] = round((real - est) / est * 100, 1) if est and real is not None else None
        d['sobre_estimado'] = bool(est and real is not None and real > est)
        if con_costos:
            d['costo'] = round(float(g['costo']), 2)
            d['horas_sin_costo'] = round(g['sin_costo'] / 60, 1)
        return d

    ordenes = []
    for ot in OrdenTrabajo.objects.filter(pk__in=grupos['orden']).select_related('cliente'):
        t = tareas_de({'orden': ot})
        est_areas = _f(OrdenArea.objects.filter(orden=ot).aggregate(s=Sum('horas_estimadas'))['s'])
        base = {'id': ot.pk, 'numero': ot.numero or ot.solicitud, 'titulo': ot.titulo, 'cliente': ot.cliente.nombre if ot.cliente_id else None,
                'estado': ot.get_estado_display(), 'fecha_compromiso': ot.fecha_compromiso, 'fecha_entrega': ot.fecha_entrega,
                'a_tiempo': (ot.fecha_entrega <= ot.fecha_compromiso) if ot.fecha_entrega and ot.fecha_compromiso else None,
                'horas_estimadas': est_areas or t['horas_estimadas_tareas'], 'horas_reales_total': horas_totales({'orden': ot}),
                'cambios': SolicitudCambio.objects.filter(orden=ot).count(), **t}
        f = fila(grupos['orden'][ot.pk], base)
        if con_costos:
            f['monto'] = _f(ot.monto)
            f['costo_retrabajo'] = _f(SolicitudCambio.objects.filter(orden=ot).aggregate(s=Sum('costo_retrabajo'))['s'])
        ordenes.append(f)

    proyectos = []
    for p in Proyecto.objects.filter(pk__in=grupos['proyecto']).select_related('cliente'):
        t = tareas_de({'proyecto': p})
        est_areas = _f(OrdenArea.objects.filter(orden__proyecto=p).aggregate(s=Sum('horas_estimadas'))['s'])
        base = {'id': p.pk, 'numero': p.codigo, 'titulo': p.nombre, 'cliente': p.cliente.nombre if p.cliente_id else None,
                'estado': p.get_estado_display(), 'fecha_compromiso': p.fecha_fin, 'fecha_entrega': None, 'a_tiempo': None,
                'horas_estimadas': est_areas or t['horas_estimadas_tareas'], 'horas_reales_total': horas_totales({'proyecto': p}),
                'cambios': SolicitudCambio.objects.filter(orden__proyecto=p).count(), **t}
        f = fila(grupos['proyecto'][p.pk], base)
        if con_costos:
            f['monto'] = _f(p.presupuesto)
        proyectos.append(f)

    ordenes.sort(key=lambda x: -x['horas'])
    proyectos.sort(key=lambda x: -x['horas'])
    total_min = sum(r.minutos_hasta_ahora() for r in regs)
    totales = {'horas': round(total_min / 60, 1), 'ordenes': len(ordenes), 'proyectos': len(proyectos),
               'sobre_estimado': sum(1 for o in ordenes if o['sobre_estimado']),
               'productividad_pc': _pct(sum(v['n_productivos'] for v in pc.values()), sum(v['n_activos'] for v in pc.values()))}
    if con_costos:
        # Cada cronómetro una sola vez (una OT y su proyecto comparten las mismas horas).
        totales['costo'] = round(float(sum((costo_hora.get(r.usuario_id) or 0) * r.minutos_hasta_ahora() / 60 for r in regs)), 2)
    return {'ordenes': ordenes, 'proyectos': proyectos, 'totales': totales}
