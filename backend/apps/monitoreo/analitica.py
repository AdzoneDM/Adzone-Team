"""Resumen del monitoreo en un rango de fechas (el «Overview» de Teramind) con uso de IA, incidencias, riesgo e insights."""
from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Q

from apps.asistencia.servicios import rango
from .comportamiento import herramienta_ia, riesgo
from .models import IMPRODUCTIVA, PRODUCTIVA, Actividad, Incidencia, ReglaComportamiento


def _pct(a, b):
    return round(a / b * 100, 1) if b else None


def _horas(m):
    return f'{m // 60} h {m % 60:02d} min' if m >= 60 else f'{m} min'


def _base(ids, desde, hasta):
    return Actividad.objects.filter(usuario_id__in=ids, minuto__range=rango(desde, hasta))


def _uso_ia(qs):
    por_herramienta = defaultdict(lambda: {'minutos': 0, 'personas': set()})
    por_persona = defaultdict(lambda: defaultdict(int))
    for f in qs.filter(Q(dominio__gt='') | Q(app__gt='')).values('usuario_id', 'app', 'dominio').annotate(n=Count('id')):
        h = herramienta_ia(f['app'], f['dominio'])
        if h:
            por_herramienta[h]['minutos'] += f['n']
            por_herramienta[h]['personas'].add(f['usuario_id'])
            por_persona[f['usuario_id']][h] += f['n']
    return por_herramienta, por_persona


def resumen(ids, desde, hasta):
    ids = list(ids)
    qs = _base(ids, desde, hasta)
    nombres = {u.pk: (u.get_full_name() or u.username) for u in User.objects.filter(pk__in=ids)}
    deptos = dict(User.objects.filter(pk__in=ids).values_list('pk', 'perfil__puesto_trabajo__departamento__nombre'))

    personas = []
    for f in qs.values('usuario_id').annotate(total=Count('id'), act=Count('id', filter=Q(activos__gte=30)),
                                              prod=Count('id', filter=Q(activos__gte=30, categoria=PRODUCTIVA)),
                                              improd=Count('id', filter=Q(activos__gte=30, categoria=IMPRODUCTIVA))):
        personas.append({'id': f['usuario_id'], 'nombre': nombres.get(f['usuario_id'], '?'), 'departamento': deptos.get(f['usuario_id']),
                         'minutos': f['total'], 'minutos_activos': f['act'], 'actividad': _pct(f['act'], f['total']),
                         'productividad': _pct(f['prod'], f['act']), 'improductividad': _pct(f['improd'], f['act'])})
    personas.sort(key=lambda x: -(x['actividad'] or 0))
    total = sum(p['minutos'] for p in personas)
    activos = sum(p['minutos_activos'] for p in personas)
    prod = qs.filter(activos__gte=30, categoria=PRODUCTIVA).count()

    def top(campo):
        filas = (qs.exclude(**{campo: ''}).values(campo).annotate(minutos=Count('id'), personas=Count('usuario_id', distinct=True),
                                                                   improd=Count('id', filter=Q(categoria=IMPRODUCTIVA)),
                                                                   prod=Count('id', filter=Q(categoria=PRODUCTIVA)))
                 .order_by('-minutos')[:12])
        return [{'nombre': f[campo], 'minutos': f['minutos'], 'personas': f['personas'],
                 'categoria': 'P' if f['prod'] * 2 > f['minutos'] else 'I' if f['improd'] * 2 > f['minutos'] else 'N'} for f in filas]

    ia_h, ia_p = _uso_ia(qs)
    ia = {'minutos': sum(v['minutos'] for v in ia_h.values()),
          'personas': len(ia_p),
          'herramientas': sorted(({'nombre': k, 'minutos': v['minutos'], 'personas': len(v['personas'])} for k, v in ia_h.items()),
                                 key=lambda x: -x['minutos']),
          'por_persona': sorted(({'id': u, 'nombre': nombres.get(u, '?'), 'minutos': sum(h.values()),
                                  'herramientas': sorted(h, key=lambda k: -h[k])} for u, h in ia_p.items()), key=lambda x: -x['minutos'])[:15]}

    incid = defaultdict(lambda: {'veces': 0, 'personas': set(), 'minutos': 0})
    reglas = {}
    for inc in Incidencia.objects.filter(usuario_id__in=ids, dia__range=(desde, hasta)).exclude(estado='DESCARTADA').select_related('regla'):
        if inc.minutos < inc.regla.minutos_minimos:
            continue
        g = incid[inc.regla_id]
        g['veces'] += 1
        g['personas'].add(inc.usuario_id)
        g['minutos'] += inc.minutos
        reglas[inc.regla_id] = inc.regla
    incidencias = sorted(({'id': rid, 'nombre': reglas[rid].nombre, 'riesgo': reglas[rid].riesgo, 'categoria': reglas[rid].categoria,
                           'veces': g['veces'], 'personas': len(g['personas']), 'minutos': g['minutos']}
                          for rid, g in incid.items()), key=lambda x: (-ReglaComportamiento.PESO[x['riesgo']], -x['veces']))
    r = riesgo(ids, desde, hasta)
    riesgos = sorted(({'id': u, 'nombre': nombres.get(u, '?'), 'departamento': deptos.get(u), **v} for u, v in r.items()),
                     key=lambda x: -x['puntos'])

    # Período anterior del mismo largo, para comparar
    dias = (hasta - desde).days + 1
    a_desde, a_hasta = desde - timedelta(days=dias), desde - timedelta(days=1)
    qa = _base(ids, a_desde, a_hasta)
    a_act = qa.filter(activos__gte=30).count()
    a_prod = qa.filter(activos__gte=30, categoria=PRODUCTIVA).count()
    a_ia = sum(v['minutos'] for v in _uso_ia(qa)[0].values())
    totales = {'personas': len(personas), 'minutos': total, 'minutos_activos': activos, 'actividad': _pct(activos, total),
               'productividad': _pct(prod, activos), 'productividad_anterior': _pct(a_prod, a_act),
               'ia_minutos': ia['minutos'], 'ia_anterior': a_ia, 'incidencias': sum(i['veces'] for i in incidencias),
               'en_riesgo': sum(1 for x in riesgos if x['nivel'] in ('ALTO', 'CRITICO'))}
    sitios, apps = top('dominio'), top('app')
    return {'desde': desde, 'hasta': hasta, 'totales': totales, 'personas': personas, 'sitios': sitios, 'apps': apps,
            'ia': ia, 'incidencias': incidencias, 'riesgo': riesgos,
            'insights': insights(totales, personas, sitios, ia, incidencias, riesgos, qs, nombres)}


def insights(t, personas, sitios, ia, incidencias, riesgos, qs, nombres):
    """Frases cortas con lo que hay que mirar, de más a menos importante."""
    salida = []
    if t['productividad'] is not None and t['productividad_anterior'] is not None:
        d = round(t['productividad'] - t['productividad_anterior'], 1)
        if abs(d) >= 3:
            salida.append({'tono': 'bien' if d > 0 else 'mal',
                           'texto': f"La productividad {'subió' if d > 0 else 'bajó'} {abs(d):g} puntos frente al período anterior ({t['productividad_anterior']:g} % → {t['productividad']:g} %)."})
    criticos = [x for x in riesgos if x['nivel'] in ('ALTO', 'CRITICO')]
    if criticos:
        salida.append({'tono': 'mal', 'texto': f"{len(criticos)} persona(s) con riesgo alto o crítico: {', '.join(x['nombre'] for x in criticos[:3])}."})
    for i in incidencias[:2]:
        if i['riesgo'] in ('ALTO', 'CRITICO', 'MEDIO'):
            salida.append({'tono': 'mal', 'texto': f"«{i['nombre']}» se activó {i['veces']} vez(ces) en {i['personas']} persona(s)."})
    improd = [s for s in sitios if s['categoria'] == 'I']
    if improd:
        s = improd[0]
        salida.append({'tono': 'mal', 'texto': f"{s['nombre']} es el sitio improductivo con más tiempo: {_horas(s['minutos'])} entre {s['personas']} persona(s)."})
        quien = (qs.filter(dominio=s['nombre']).values('usuario_id').annotate(n=Count('id')).order_by('-n').first())
        if quien and quien['n'] >= 60:
            salida.append({'tono': 'mal', 'texto': f"{nombres.get(quien['usuario_id'], '?')} pasó {_horas(quien['n'])} en {s['nombre']}."})
    bajos = [p for p in personas if p['actividad'] is not None and p['actividad'] < 60 and p['minutos'] >= 240]
    if bajos:
        salida.append({'tono': 'aviso', 'texto': f"{len(bajos)} persona(s) con menos de 60 % de tiempo activo: {', '.join(p['nombre'] for p in bajos[:3])}."})
    if ia['minutos']:
        cambio = f" ({'+' if ia['minutos'] >= t['ia_anterior'] else ''}{round((ia['minutos'] - t['ia_anterior']) / t['ia_anterior'] * 100)} % frente al período anterior)" if t['ia_anterior'] else ''
        salida.append({'tono': 'info', 'texto': f"{ia['personas']} persona(s) usaron IA {_horas(ia['minutos'])}{cambio}; la más usada es {ia['herramientas'][0]['nombre']}."})
    if personas:
        mejor = max(personas, key=lambda p: (p['productividad'] or 0))
        if mejor['productividad']:
            salida.append({'tono': 'bien', 'texto': f"Más productivo del período: {mejor['nombre']} ({mejor['productividad']:g} % de su tiempo activo)."})
    return salida[:7]
