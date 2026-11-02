"""Clasificación de la actividad, ingesta del agente, resúmenes (día, período, equipo) y alertas."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.asistencia.models import Marcaje
from apps.asistencia.servicios import TURNO_MAXIMO, rango
from .models import IMPRODUCTIVA, NEUTRAL, PRODUCTIVA, Actividad, AlertaEnviada, ConfiguracionMonitoreo, Consentimiento, ReglaProductividad

FOCO_MINIMO = 25  # minutos seguidos productivos y activos para contar como «tiempo de foco»
ORDEN_TIPOS = ('DOMINIO', 'TITULO', 'APP')


# ------------------------------------------------------------------ Clasificación
class Clasificador:
    """Carga las reglas una vez. Gana la del departamento; dentro de cada nivel, sitio > título > aplicación."""

    def __init__(self):
        # La más específica primero: a igual nivel, gana el patrón más largo.
        self.reglas = sorted(ReglaProductividad.objects.all().values('tipo', 'patron', 'categoria', 'departamento_id'),
                             key=lambda r: -len(r['patron']))

    @staticmethod
    def _coincide(tipo, patron, texto):
        patron = patron.lower()
        if tipo == 'DOMINIO':
            return texto == patron or texto.endswith('.' + patron)  # «x.com» no marca «dropbox.com»
        return patron in texto

    def categoria(self, departamento_id, app='', titulo='', dominio=''):
        campos = {'APP': (app or '').lower(), 'TITULO': (titulo or '').lower(), 'DOMINIO': (dominio or '').lower()}
        for depto in ((departamento_id,) if departamento_id else ()) + (None,):
            for tipo in ORDEN_TIPOS:
                texto = campos[tipo]
                if not texto:
                    continue
                for r in self.reglas:
                    if r['tipo'] == tipo and r['departamento_id'] == depto and self._coincide(tipo, r['patron'], texto):
                        return r['categoria']
        return NEUTRAL


def departamento_de(usuario):
    puesto = getattr(getattr(usuario, 'perfil', None), 'puesto_trabajo', None)
    return puesto.departamento_id if puesto else None


def reclasificar(desde=None):
    """Aplica las reglas actuales a la actividad guardada (tras cambiar reglas)."""
    from django.db.models import F
    clasif = Clasificador()
    qs = Actividad.objects.all()
    if desde:
        qs = qs.filter(minuto__gte=desde)
    cambiados = 0
    # Una consulta por combinación distinta (departamento, app, título, sitio), no una por minuto.
    combos = qs.values('usuario__perfil__puesto_trabajo__departamento_id', 'app', 'titulo', 'dominio', 'categoria').distinct()
    for c in combos:
        depto = c['usuario__perfil__puesto_trabajo__departamento_id']
        cat = clasif.categoria(depto, c['app'], c['titulo'], c['dominio'])
        if cat != c['categoria']:
            cambiados += qs.filter(usuario__perfil__puesto_trabajo__departamento_id=depto, app=c['app'], titulo=c['titulo'],
                                   dominio=c['dominio'], categoria=c['categoria']).update(categoria=cat)
    return cambiados


# ------------------------------------------------------------------ Jornada y consentimiento
def tramos_en_jornada(usuario, desde, hasta):
    """Intervalos [(inicio, fin)] en que la persona estaba trabajando (marcó entrada/regreso y no pausa/salida)."""
    marcajes = list(Marcaje.objects.filter(usuario=usuario, momento__gte=desde - TURNO_MAXIMO, momento__lte=hasta).order_by('momento'))
    tramos, inicio = [], None
    for m in marcajes:
        if m.tipo in (Marcaje.ENTRADA, Marcaje.REGRESO):
            if inicio and m.momento - inicio > TURNO_MAXIMO:
                tramos.append((inicio, inicio + TURNO_MAXIMO))  # olvidó marcar salida: se corta a las 16 h
                inicio = None
            inicio = inicio or m.momento
        elif inicio:
            tramos.append((inicio, m.momento))
            inicio = None
    if inicio:
        tramos.append((inicio, min(hasta + timedelta(minutes=1), inicio + TURNO_MAXIMO)))
    return tramos


def consintio(usuario, config=None):
    config = config or ConfiguracionMonitoreo.actual()
    return Consentimiento.objects.filter(usuario=usuario, version=config.version_politica).exists()


def estado_agente(dispositivo):
    """Qué le dice la plataforma al agente: si registra ahora, y cada cuánto toma capturas."""
    from apps.asistencia.servicios import estado_actual
    config = ConfiguracionMonitoreo.actual()
    usuario = dispositivo.usuario
    jornada, _ = estado_actual(usuario)
    registrar, motivo = True, 'Midiendo tu jornada.'
    if not config.activo:
        registrar, motivo = False, 'El monitoreo está apagado.'
    elif not usuario.is_active or not dispositivo.activo:
        registrar, motivo = False, 'Este equipo fue desvinculado.'
    elif not consintio(usuario, config):
        registrar, motivo = False, 'Falta aceptar la política de monitoreo en Adzone Team.'
    elif jornada == 'FUERA':
        registrar, motivo = False, 'No has marcado entrada: no se registra nada.'
    elif jornada == 'EN_PAUSA':
        registrar, motivo = False, 'Estás en pausa: no se registra nada.'
    return {
        'registrar': registrar, 'motivo': motivo, 'jornada': jornada,
        'usuario': usuario.get_full_name() or usuario.username, 'equipo': dispositivo.nombre,
        'umbral_inactivo_seg': config.umbral_inactivo_seg,
        'capturas': registrar and config.capturas, 'capturas_cada_min': config.capturas_cada_min,
        'desenfocar': config.desenfocar_capturas, 'consentimiento': consintio(usuario, config),
        'version_politica': config.version_politica, 'intervalo_envio_seg': 60,
    }


def _a_minuto(texto):
    try:
        m = datetime.fromisoformat(str(texto).replace('Z', '+00:00'))
    except ValueError:
        return None
    if timezone.is_naive(m):
        m = timezone.make_aware(m)
    return m.replace(second=0, microsecond=0)


def _entero(v, tope):
    try:
        return max(0, min(int(v), tope))
    except (TypeError, ValueError):
        return 0


def ingestar(dispositivo, minutos, ahora=None):
    """
    Guarda los minutos que manda el agente. Descarta lo que cae fuera de jornada, lo del futuro, lo de hace más de
    3 días y los duplicados. Devuelve (guardados, descartados).
    """
    ahora = ahora or timezone.now()
    config = ConfiguracionMonitoreo.actual()
    usuario = dispositivo.usuario
    if not config.activo or not consintio(usuario, config):
        return 0, len(minutos)
    validos = []
    for item in minutos[:720]:
        if not isinstance(item, dict):
            continue
        m = _a_minuto(item.get('minuto'))
        if m is None or m > ahora + timedelta(minutes=2) or m < ahora - timedelta(days=3):
            continue
        validos.append((m, item))
    if not validos:
        return 0, len(minutos)
    tramos = tramos_en_jornada(usuario, min(v[0] for v in validos), max(v[0] for v in validos))
    clasif = Clasificador()
    depto = departamento_de(usuario)
    guardados = 0
    for m, item in validos:
        if not any(a <= m < b for a, b in tramos):
            continue
        app, titulo, dominio = (str(item.get(k) or '')[:n] for k, n in (('app', 100), ('titulo', 255), ('dominio', 150)))
        try:
            with transaction.atomic():
                Actividad.objects.create(
                    usuario=usuario, dispositivo=dispositivo, minuto=m,
                    activos=_entero(item.get('activos'), 60), inactivos=_entero(item.get('inactivos'), 60),
                    intensidad=_entero(item.get('intensidad'), 100), cambios=_entero(item.get('cambios'), 200),
                    app=app, titulo=titulo, dominio=dominio.lower(), categoria=clasif.categoria(depto, app, titulo, dominio))
            guardados += 1
        except IntegrityError:
            pass  # ese minuto ya llegó (de este u otro equipo de la misma persona)
    return guardados, len(minutos) - guardados


# ------------------------------------------------------------------ Resúmenes
def _resumir(filas, minutos_jornada=None):
    """Indicadores a partir de filas de Actividad ya ordenadas por minuto."""
    total = len(filas)
    activos = sum(1 for f in filas if f.activos >= 30)
    por_cat = Counter(f.categoria for f in filas if f.activos >= 30)
    apps, sitios = defaultdict(lambda: [0, NEUTRAL]), defaultdict(lambda: [0, NEUTRAL])
    for f in filas:
        clave = f.app or 'Desconocida'
        apps[clave][0] += 1
        apps[clave][1] = f.categoria
        if f.dominio:
            sitios[f.dominio][0] += 1
            sitios[f.dominio][1] = f.categoria
    # tiempo de foco: rachas de minutos consecutivos productivos y activos de FOCO_MINIMO o más
    foco = racha = sesiones_foco = 0
    anterior = None
    for f in filas:
        seguido = anterior is not None and f.minuto - anterior == timedelta(minutes=1)
        if f.categoria == PRODUCTIVA and f.activos >= 30 and seguido and racha:
            racha += 1
        else:
            if racha >= FOCO_MINIMO:
                foco, sesiones_foco = foco + racha, sesiones_foco + 1
            racha = 1 if f.categoria == PRODUCTIVA and f.activos >= 30 else 0
        anterior = f.minuto
    if racha >= FOCO_MINIMO:
        foco, sesiones_foco = foco + racha, sesiones_foco + 1
    horas = total / 60 if total else 0
    return {
        'minutos_registrados': total, 'minutos_activos': activos, 'minutos_inactivos': total - activos,
        'minutos_productivos': por_cat[PRODUCTIVA], 'minutos_neutrales': por_cat[NEUTRAL], 'minutos_improductivos': por_cat[IMPRODUCTIVA],
        'actividad': round(activos / total * 100, 1) if total else None,
        'productividad': round(por_cat[PRODUCTIVA] / activos * 100, 1) if activos else None,
        'improductividad': round(por_cat[IMPRODUCTIVA] / activos * 100, 1) if activos else None,
        'intensidad': round(sum(f.intensidad for f in filas) / total, 1) if total else None,
        'cambios_por_hora': round(sum(f.cambios for f in filas) / horas, 1) if horas else None,
        'minutos_foco': foco, 'sesiones_foco': sesiones_foco,
        'cobertura': round(min(total / minutos_jornada, 1) * 100, 1) if minutos_jornada else None,
        'apps': sorted(({'nombre': k, 'minutos': v[0], 'categoria': v[1]} for k, v in apps.items()), key=lambda x: -x['minutos'])[:15],
        'sitios': sorted(({'nombre': k, 'minutos': v[0], 'categoria': v[1]} for k, v in sitios.items()), key=lambda x: -x['minutos'])[:15],
    }


def resumen_dia(usuario, dia):
    from apps.asistencia.servicios import jornada
    filas = list(Actividad.objects.filter(usuario=usuario, minuto__range=rango(dia)).order_by('minuto'))
    j = jornada(usuario, dia)
    r = _resumir(filas, j['trabajados'])
    # línea de tiempo en bloques de 10 minutos
    bloques = {}
    for f in filas:
        local = timezone.localtime(f.minuto)
        clave = local.replace(minute=local.minute - local.minute % 10)
        b = bloques.setdefault(clave, Counter())
        b['activos' if f.activos >= 30 else 'inactivos'] += 1
        if f.activos >= 30:
            b[f.categoria] += 1
    r['linea'] = [{'hora': k.strftime('%H:%M'), 'activos': v['activos'], 'inactivos': v['inactivos'],
                   'productivos': v[PRODUCTIVA], 'neutrales': v[NEUTRAL], 'improductivos': v[IMPRODUCTIVA]}
                  for k, v in sorted(bloques.items())]
    r['primera'] = filas[0].minuto if filas else None
    r['ultima'] = filas[-1].minuto if filas else None
    r['jornada'] = {k: j[k] for k in ('estado', 'entrada', 'salida', 'trabajados', 'pausa', 'tardanza', 'llegada', 'turno')}
    return r


def resumen_periodo(usuario, desde, hasta):
    filas = list(Actividad.objects.filter(usuario=usuario, minuto__range=rango(desde, hasta)).order_by('minuto'))
    from apps.asistencia.servicios import resumen
    trabajados = resumen(usuario, desde, hasta)['minutos_trabajados']
    r = _resumir(filas, trabajados)
    r['dias_con_actividad'] = len({timezone.localtime(f.minuto).date() for f in filas})
    return r


def indicadores_pc(ids, desde, hasta):
    """Actividad y productividad del período por persona, agregadas en la base (rápido para el ranking)."""
    from django.db.models import Count, Q
    filas = (Actividad.objects.filter(usuario_id__in=ids, minuto__range=rango(desde, hasta)).values('usuario_id')
             .annotate(n_total=Count('id'), n_activos=Count('id', filter=Q(activos__gte=30)),
                       n_productivos=Count('id', filter=Q(activos__gte=30, categoria=PRODUCTIVA)),
                       n_improductivos=Count('id', filter=Q(activos__gte=30, categoria=IMPRODUCTIVA))))
    res = {}
    for f in filas:
        total, activos = f['n_total'], f['n_activos']
        res[f['usuario_id']] = {
            'minutos_registrados': total, 'minutos_activos': activos,
            'actividad': round(activos / total * 100, 1) if total else None,
            'productividad': round(f['n_productivos'] / activos * 100, 1) if activos else None,
            'improductividad': round(f['n_improductivos'] / activos * 100, 1) if activos else None,
        }
    return res


def ultimo_contacto_por_usuario(ids):
    """Última actividad recibida de la computadora de cada persona (para la vista «Hoy»)."""
    hace = timezone.now() - timedelta(hours=12)
    ultimo = {}
    for a in Actividad.objects.filter(usuario_id__in=ids, minuto__gte=hace).order_by('usuario_id', '-minuto').values(
            'usuario_id', 'minuto', 'app', 'titulo', 'categoria', 'activos'):
        ultimo.setdefault(a['usuario_id'], a)
    return {k: {'minuto': v['minuto'], 'app': v['app'], 'categoria': v['categoria'], 'activo': v['activos'] >= 30,
                'en_vivo': v['minuto'] >= timezone.now() - timedelta(minutes=5)} for k, v in ultimo.items()}


# ------------------------------------------------------------------ Alertas
def _una_vez(usuario, clave, tipo, detalle):
    _, nueva = AlertaEnviada.objects.get_or_create(usuario=usuario, clave=clave[:80], defaults={'tipo': tipo, 'detalle': detalle[:255]})
    return nueva


def revisar_alertas(ahora=None):
    """Recorre a quienes están en jornada y avisa a su supervisor. Pensado para correr cada 5-10 minutos."""
    from apps.asistencia.servicios import estado_actual, jornada
    from apps.desempeno.permisos import revisores_de
    from apps.desempeno.servicios import avisar
    ahora = ahora or timezone.now()
    config = ConfiguracionMonitoreo.actual()
    hoy = timezone.localtime(ahora).date()
    enviados = 0
    for u in User.objects.filter(is_active=True, dispositivos__activo=True).distinct():
        nombre = u.get_full_name() or u.username
        estado, ultimo = estado_actual(u, ahora)
        if estado != 'TRABAJANDO':
            continue
        desde_marca = (ahora - ultimo.momento).total_seconds() / 60
        recientes = list(Actividad.objects.filter(usuario=u, minuto__gte=ahora - timedelta(minutes=config.alerta_inactivo_min)).order_by('minuto'))
        if (config.activo and consintio(u, config) and desde_marca >= config.alerta_sin_pc_min
                and not Actividad.objects.filter(usuario=u, minuto__gte=ultimo.momento).exists()):
            if _una_vez(u, f'sinpc-{ultimo.momento:%Y%m%d%H%M}', 'SIN_PC', f'Marcó a las {timezone.localtime(ultimo.momento):%H:%M}'):
                avisar(revisores_de(u), 'MONITOREO', f'{nombre}: su computadora no reporta',
                       f'Marcó a las {timezone.localtime(ultimo.momento):%H:%M} y en {config.alerta_sin_pc_min} minutos su computadora no ha enviado actividad.',
                       enlace=f'/monitoreo?persona={u.pk}')
                enviados += 1
        if (desde_marca >= config.alerta_inactivo_min and len(recientes) >= config.alerta_inactivo_min - 2
                and all(a.activos < 30 for a in recientes)):
            if _una_vez(u, f'inactivo-{recientes[0].minuto:%Y%m%d%H}', 'INACTIVO', f'{config.alerta_inactivo_min} min'):
                avisar(revisores_de(u), 'MONITOREO', f'{nombre} lleva {config.alerta_inactivo_min} minutos inactivo',
                       'En jornada, sin teclado ni ratón en su computadora.', enlace=f'/monitoreo?persona={u.pk}')
                enviados += 1
        dia = _resumir(list(Actividad.objects.filter(usuario=u, minuto__range=rango(hoy)).order_by('minuto')))
        if (dia['minutos_activos'] >= 60 and dia['improductividad'] is not None and dia['improductividad'] >= config.alerta_improductivo_pct):
            if _una_vez(u, f'improductivo-{hoy:%Y%m%d}', 'IMPRODUCTIVO', f"{dia['improductividad']} %"):
                avisar(revisores_de(u), 'MONITOREO', f"{nombre}: {dia['improductividad']} % de su tiempo hoy es improductivo",
                       'Revisa sus aplicaciones y sitios del día.', enlace=f'/monitoreo?persona={u.pk}')
                enviados += 1
    # Tardanzas y entradas sin marcar: solo a quien ya usa el control de horario o tiene horario asignado
    from apps.asistencia.models import AsignacionHorario
    usan = set(Marcaje.objects.values_list('usuario_id', flat=True).distinct()) | set(
        AsignacionHorario.objects.filter(marca_obligatoria=True).values_list('usuario_id', flat=True))
    for u in User.objects.filter(is_active=True, pk__in=usan):
        j = jornada(u, hoy, ahora)
        nombre = u.get_full_name() or u.username
        if j['llegada'] == 'TARDE' and j['tardanza'] >= 15 and _una_vez(u, f'tarde-{hoy:%Y%m%d}', 'TARDE', f"{j['tardanza']} min"):
            avisar(revisores_de(u), 'ASISTENCIA', f"{nombre} llegó {j['tardanza']} minutos tarde", enlace='/asistencia')
            enviados += 1
        if j['estado'] == 'TARDE_SIN_MARCAR' and _una_vez(u, f'sinmarcar-{hoy:%Y%m%d}', 'SIN_MARCAR', ''):
            avisar([u], 'ASISTENCIA', 'No has marcado tu entrada', 'Márcala en Adzone Team en cuanto llegues.', enlace='/')
            avisar(revisores_de(u), 'ASISTENCIA', f'{nombre} no ha marcado entrada', f"Entraba a las {j['turno'][0]}.", enlace='/asistencia')
            enviados += 1
    return enviados


def limpiar(ahora=None):
    """Borra la actividad y las capturas más viejas que la retención configurada."""
    from .models import Captura
    ahora = ahora or timezone.now()
    config = ConfiguracionMonitoreo.actual()
    borradas = Actividad.objects.filter(minuto__lt=ahora - timedelta(days=config.retencion_dias)).delete()[0]
    capturas = 0
    for c in Captura.objects.filter(tomada_en__lt=ahora - timedelta(days=config.retencion_capturas_dias)):
        c.archivo.delete(save=False)
        c.delete()
        capturas += 1
    AlertaEnviada.objects.filter(creada__lt=ahora - timedelta(days=config.retencion_dias)).delete()
    return borradas, capturas
