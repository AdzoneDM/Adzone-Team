"""Evaluaciones 360°, alertas de KPIs bajo su umbral y datos del expediente."""
import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from .models import COMPETENCIAS, CicloEvaluacion, Evaluacion

PROMEDIO_REVISION = 3  # una evaluación del supervisor con promedio menor la confirma la dirección


def _nombre(u):
    return u.get_full_name() or u.username


def a_porcentaje(promedio):
    """1 a 5 → 0 a 100."""
    return None if promedio is None else round((promedio - 1) / 4 * 100, 1)


# ------------------------------------------------------------------ Ciclos
def evaluables():
    """Personas activas con puesto (los agentes también: se evalúan con sus competencias)."""
    return User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=False).select_related('perfil__puesto_trabajo__departamento')


def generar(ciclo, pares_por_persona=2, semilla=None):
    """Crea las evaluaciones pendientes del ciclo: autoevaluación, supervisor(es) y, si aplica, compañeros del mismo departamento."""
    from apps.desempeno.permisos import revisores_de
    from apps.desempeno.servicios import avisar
    azar = random.Random(semilla)
    personas = list(evaluables())
    por_depto = {}
    for p in personas:
        por_depto.setdefault(p.perfil.puesto_trabajo.departamento_id, []).append(p)
    creadas = 0
    for p in personas:
        filas = [(p, 'AUTO')] + [(s, 'SUPERVISOR') for s in revisores_de(p) if s.pk != p.pk]
        if ciclo.con_pares:
            companeros = [c for c in por_depto.get(p.perfil.puesto_trabajo.departamento_id, []) if c.pk != p.pk]
            filas += [(c, 'PAR') for c in azar.sample(companeros, min(pares_por_persona, len(companeros)))]
        for evaluador, tipo in filas:
            _, nueva = Evaluacion.objects.get_or_create(ciclo=ciclo, evaluado=p, evaluador=evaluador, tipo=tipo)
            creadas += nueva
    pendientes = {}
    for e in Evaluacion.objects.filter(ciclo=ciclo, estado='PENDIENTE'):
        pendientes[e.evaluador_id] = pendientes.get(e.evaluador_id, 0) + 1
    for u in User.objects.filter(pk__in=pendientes):
        avisar([u], 'TALENTO', f'Evaluaciones de «{ciclo.nombre}»: tienes {pendientes[u.pk]} por hacer',
               f'Antes del {ciclo.cierre:%d/%m}.', enlace='/talento?ver=evaluar')
    return creadas


def enviar(evaluacion, puntajes, fortalezas='', a_mejorar='', comentario=''):
    """Valida y envía. Una evaluación baja del supervisor queda en revisión de la dirección. Devuelve un error o None."""
    from apps.desempeno.permisos import administradores
    from apps.desempeno.servicios import avisar
    if evaluacion.estado not in ('PENDIENTE',):
        return 'Esta evaluación ya se envió.'
    if not evaluacion.ciclo.abierto:
        return 'El ciclo ya cerró.'
    limpios = {}
    for clave, _ in COMPETENCIAS:
        try:
            v = int((puntajes or {}).get(clave))
        except (TypeError, ValueError):
            return 'Califica todas las competencias del 1 al 5.'
        if not 1 <= v <= 5:
            return 'Califica todas las competencias del 1 al 5.'
        limpios[clave] = v
    promedio = sum(limpios.values()) / len(limpios)
    if evaluacion.tipo == 'SUPERVISOR' and promedio < PROMEDIO_REVISION and not str(a_mejorar).strip():
        return 'Una evaluación por debajo de «Cumple» necesita explicar qué hay que mejorar.'
    evaluacion.puntajes = limpios
    evaluacion.fortalezas, evaluacion.a_mejorar, evaluacion.comentario = str(fortalezas)[:4000], str(a_mejorar)[:4000], str(comentario)[:4000]
    evaluacion.enviada = timezone.now()
    evaluacion.estado = 'EN_REVISION' if evaluacion.tipo == 'SUPERVISOR' and promedio < PROMEDIO_REVISION else 'ENVIADA'
    evaluacion.save()
    if evaluacion.estado == 'EN_REVISION':
        avisar(administradores(), 'TALENTO', f'Evaluación baja de {_nombre(evaluacion.evaluado)} por revisar',
               f'{_nombre(evaluacion.evaluador)} la calificó con {promedio:.1f} de 5. Confírmala antes de que la vea la persona.',
               enlace='/talento?ver=revisar', excepto=evaluacion.evaluador)
    return None


def visibles_para_evaluado(qs):
    """Lo que la persona ve de sus evaluaciones: nunca lo que está en revisión, y los compañeros solo en promedio."""
    return qs.filter(estado__in=('ENVIADA', 'CERRADA'))


def resultados(ciclo, usuario, anonimo=True):
    """Promedios por competencia y por tipo (auto, supervisor, compañeros) y comentarios."""
    evals = list(Evaluacion.objects.filter(ciclo=ciclo, evaluado=usuario, estado__in=('ENVIADA', 'CERRADA')).select_related('evaluador'))
    por_tipo = {}
    for tipo in ('AUTO', 'SUPERVISOR', 'PAR'):
        grupo = [e for e in evals if e.tipo == tipo]
        if not grupo:
            continue
        comp = {}
        for clave, _ in COMPETENCIAS:
            valores = [e.puntajes.get(clave) for e in grupo if e.puntajes.get(clave)]
            comp[clave] = round(sum(valores) / len(valores), 2) if valores else None
        validos = [e.promedio for e in grupo if e.promedio is not None]
        por_tipo[tipo] = {
            'cantidad': len(grupo), 'competencias': comp,
            'promedio': round(sum(validos) / len(validos), 2) if validos else None,
            'comentarios': [{'de': None if (anonimo and tipo == 'PAR') else _nombre(e.evaluador), 'fortalezas': e.fortalezas,
                             'a_mejorar': e.a_mejorar, 'comentario': e.comentario} for e in grupo],
        }
    pendientes = Evaluacion.objects.filter(ciclo=ciclo, evaluado=usuario, estado__in=('PENDIENTE', 'EN_REVISION')).count()
    return {'ciclo': {'id': ciclo.id, 'nombre': ciclo.nombre, 'desde': ciclo.desde, 'hasta': ciclo.hasta},
            'por_tipo': por_tipo, 'pendientes': pendientes,
            'competencias': [{'clave': c, 'nombre': n} for c, n in COMPETENCIAS]}


def evaluacion_supervisor_pct(usuario, inicio, fin):
    """Evaluación del supervisor (0-100) de los ciclos que tocan el período, para el componente de calidad."""
    evals = Evaluacion.objects.filter(evaluado=usuario, tipo='SUPERVISOR', estado__in=('ENVIADA', 'CERRADA'),
                                      ciclo__desde__lte=fin, ciclo__hasta__gte=inicio)
    promedios = [e.promedio for e in evals if e.promedio is not None]
    return a_porcentaje(sum(promedios) / len(promedios)) if promedios else None


# ------------------------------------------------------------------ Alertas de KPIs
def revisar_kpis(periodo=None):
    """KPIs del mes (por defecto, el anterior) por debajo de su umbral: aviso al supervisor, una vez por KPI y mes."""
    from apps.desempeno.permisos import revisores_de
    from apps.desempeno.puntaje import Mediciones, kpis_del_mes, rango_del_mes
    from apps.desempeno.models import ResultadoKPI
    from apps.desempeno.servicios import avisar
    from apps.monitoreo.models import AlertaEnviada
    hoy = timezone.localdate()
    periodo = periodo or (hoy.replace(day=1) - timedelta(days=1)).replace(day=1)
    inicio, fin = rango_del_mes(periodo)
    enviados = 0
    for u in evaluables():
        manuales = ResultadoKPI.objects.filter(colaborador=u, periodo=inicio)
        bajos = [k for k in kpis_del_mes(u, inicio, fin, manuales, Mediciones(u, inicio, fin)) if k.get('bajo_umbral')]
        for k in bajos:
            clave = f"kpi-{k['kpi_asignado_id']}-{inicio:%Y%m}"
            _, nueva = AlertaEnviada.objects.get_or_create(usuario=u, clave=clave, defaults={'tipo': 'KPI', 'detalle': k['nombre'][:255]})
            if nueva:
                avisar(revisores_de(u), 'TALENTO', f"{_nombre(u)}: «{k['nombre']}» al {round(k['cumplimiento'])} % en {inicio:%m/%Y}",
                       f"Su umbral es {k['umbral']:g} %. Revisa su ficha y, si hace falta, abre un plan de mejora.",
                       enlace=f'/ficha?usuario={u.pk}&mes={inicio:%Y-%m}')
                enviados += 1
    return enviados
