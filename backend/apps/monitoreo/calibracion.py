"""
Calibración del piloto: qué aplicaciones y sitios usa el equipo que ninguna regla clasifica (quedan «neutral» por defecto),
para decidir rápido si son productivos o improductivos, para toda la empresa o para un departamento.
"""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Min
from django.utils import timezone

from apps.core.models import Departamento
from .models import Actividad
from .servicios import Clasificador


def _clave(app, dominio):
    """Un sitio se clasifica por su dominio sin «www.»; una aplicación por su nombre de proceso."""
    if dominio:
        d = dominio.lower()
        return ('DOMINIO', d[4:] if d.startswith('www.') else d)
    return ('APP', (app or '').lower())


def sin_clasificar(dias=7, limite=60):
    desde = timezone.now() - timedelta(days=dias)
    qs = Actividad.objects.filter(minuto__gte=desde, justificada=False)
    total = qs.count()
    clasif = Clasificador()
    grupos = defaultdict(lambda: {'minutos': 0, 'personas': set(), 'departamentos': defaultdict(int), 'ejemplo': ''})
    con_regla = 0
    filas = (qs.values('usuario_id', 'usuario__perfil__puesto_trabajo__departamento_id', 'app', 'dominio')
             .annotate(n=Count('id'), titulo=Min('titulo')))
    for f in filas:
        depto = f['usuario__perfil__puesto_trabajo__departamento_id']
        r = clasif.regla(depto, f['app'], f['titulo'] or '', f['dominio'])
        # Un sitio decidido solo por la regla del navegador («chrome» = neutral) sigue sin clasificar
        if r is not None and not (f['dominio'] and r['tipo'] == 'APP'):
            con_regla += f['n']
            continue
        tipo, patron = _clave(f['app'], f['dominio'])
        if not patron:
            continue
        g = grupos[(tipo, patron)]
        g['minutos'] += f['n']
        g['personas'].add(f['usuario_id'])
        g['departamentos'][depto] += f['n']
        g['ejemplo'] = g['ejemplo'] or (f['titulo'] or '')[:120]
    nombres = dict(Departamento.objects.values_list('id', 'nombre'))
    lista = sorted(grupos.items(), key=lambda kv: -kv[1]['minutos'])[:limite]
    return {
        'dias': dias, 'minutos_total': total, 'minutos_con_regla': con_regla,
        'cobertura': round(con_regla / total * 100, 1) if total else None,
        'sin_clasificar': [{
            'tipo': tipo, 'patron': patron, 'minutos': g['minutos'], 'personas': len(g['personas']), 'ejemplo': g['ejemplo'],
            'departamentos': sorted(({'id': d, 'nombre': nombres.get(d, 'Sin departamento'), 'minutos': m}
                                     for d, m in g['departamentos'].items()), key=lambda x: -x['minutos']),
        } for (tipo, patron), g in lista],
    }
