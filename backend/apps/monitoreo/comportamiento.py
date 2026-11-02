"""
Reglas de comportamiento, incidencias, herramientas de IA y perfiles de monitoreo (lo que en Teramind son Behavior Rules,
AI Usage Control y Monitoring Profiles). Todo se calcula con lo que el agente ya envía: aplicación, sitio y título de la
ventana por minuto. Nunca contenido, teclas, archivos ni mensajes.
"""
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import ConfiguracionMonitoreo, Incidencia, PerfilMonitoreo, ReglaComportamiento

# ------------------------------------------------------------------ Herramientas de IA
# (campo, patrón, nombre). Sitios: el dominio y sus subdominios. Apps y títulos: el texto aparece.
HERRAMIENTAS_IA = [
    ('DOMINIO', 'chatgpt.com', 'ChatGPT'), ('DOMINIO', 'chat.openai.com', 'ChatGPT'), ('APP', 'chatgpt', 'ChatGPT'),
    ('DOMINIO', 'claude.ai', 'Claude'), ('APP', 'claude', 'Claude'),
    ('DOMINIO', 'gemini.google.com', 'Gemini'), ('DOMINIO', 'aistudio.google.com', 'Gemini'),
    ('DOMINIO', 'notebooklm.google.com', 'NotebookLM'),
    ('DOMINIO', 'copilot.microsoft.com', 'Copilot'), ('APP', 'copilot', 'Copilot'),
    ('DOMINIO', 'perplexity.ai', 'Perplexity'), ('DOMINIO', 'deepseek.com', 'DeepSeek'), ('DOMINIO', 'meta.ai', 'Meta AI'),
    ('DOMINIO', 'grok.com', 'Grok'), ('DOMINIO', 'poe.com', 'Poe'), ('DOMINIO', 'character.ai', 'Character.AI'),
    ('DOMINIO', 'midjourney.com', 'Midjourney'), ('DOMINIO', 'leonardo.ai', 'Leonardo'), ('DOMINIO', 'firefly.adobe.com', 'Adobe Firefly'),
    ('DOMINIO', 'runwayml.com', 'Runway'), ('DOMINIO', 'elevenlabs.io', 'ElevenLabs'), ('DOMINIO', 'suno.com', 'Suno'),
    ('DOMINIO', 'heygen.com', 'HeyGen'), ('DOMINIO', 'gamma.app', 'Gamma'),
]


def _dominio_coincide(dominio, patron):
    return bool(dominio) and (dominio == patron or dominio.endswith('.' + patron))


def herramienta_ia(app='', dominio='', titulo=''):
    app, dominio = (app or '').lower(), (dominio or '').lower()
    for campo, patron, nombre in HERRAMIENTAS_IA:
        if campo == 'DOMINIO' and _dominio_coincide(dominio, patron):
            return nombre
        if campo == 'APP' and patron in app:
            return nombre
    return None


# ------------------------------------------------------------------ Reglas iniciales
REGLAS_INICIALES = [
    # nombre, categoría, campo, patrones, minutos, riesgo, acción, descripción, departamentos excluidos (por nombre)
    ('Contenido para adultos', 'CUMPLIMIENTO', 'DOMINIO', ['pornhub.com', 'xvideos.com', 'xnxx.com', 'xhamster.com', 'onlyfans.com'],
     1, 'CRITICO', 'ALERTAR', 'Prohibido en equipos de la empresa (reglamento interno).', []),
    ('Apuestas y casinos en línea', 'CUMPLIMIENTO', 'DOMINIO', ['bet365.com', 'stake.com', '1xbet.com', 'betcris.com', 'codere.com',
                                                                 'pokerstars.com', 'betway.com', 'bancaenlinea.do'],
     1, 'ALTO', 'ALERTAR', 'Sitios de apuestas en horario laboral.', []),
    ('Descargas P2P (torrent)', 'SEGURIDAD', 'APP', ['qbittorrent', 'utorrent', 'bittorrent', 'transmission'],
     1, 'ALTO', 'ALERTAR', 'Riesgo de virus y de piratería en la red de la empresa.', []),
    ('Acceso remoto', 'SEGURIDAD', 'APP', ['anydesk', 'teamviewer', 'rustdesk', 'remote desktop'],
     5, 'MEDIO', 'ALERTAR', 'Alguien de fuera puede controlar el equipo. En Tecnología es parte del trabajo.', ['tecnolog']),
    ('VPN o navegación anónima', 'SEGURIDAD', 'APP', ['nordvpn', 'expressvpn', 'protonvpn', 'hotspot shield', 'psiphon', 'tor browser'],
     5, 'MEDIO', 'REGISTRAR', 'Saltarse la red de la empresa.', ['tecnolog']),
    ('Envío de archivos a servicios externos', 'SEGURIDAD', 'DOMINIO', ['wetransfer.com', 'mega.nz', 'mediafire.com', 'sendspace.com',
                                                                         'gofile.io'],
     3, 'MEDIO', 'REGISTRAR', 'Archivos de clientes saliendo por servicios no aprobados.', []),
    ('IA no aprobada', 'IA', 'DOMINIO', ['deepseek.com', 'character.ai'],
     5, 'MEDIO', 'ALERTAR', 'Herramientas de IA que la empresa no aprobó para datos de clientes.', []),
    ('Juegos', 'PRODUCTIVIDAD', 'APP', ['steam', 'epicgameslauncher', 'riotclient', 'robloxplayer', 'minecraft', 'leagueclient'],
     15, 'MEDIO', 'ALERTAR', 'Juegos en jornada.', []),
    ('Series y películas', 'PRODUCTIVIDAD', 'DOMINIO', ['netflix.com', 'primevideo.com', 'disneyplus.com', 'max.com', 'crunchyroll.com'],
     30, 'BAJO', 'REGISTRAR', 'Más de media hora en el día.', ['audiovisual', 'adzone tv']),
    ('Compras en línea', 'PRODUCTIVIDAD', 'DOMINIO', ['amazon.com', 'shein.com', 'temu.com', 'aliexpress.com', 'ebay.com'],
     20, 'BAJO', 'REGISTRAR', 'Más de 20 minutos en el día.', ['almac', 'finanzas', 'administraci']),
    ('Redes sociales fuera de su función', 'PRODUCTIVIDAD', 'DOMINIO', ['facebook.com', 'instagram.com', 'tiktok.com', 'x.com', 'twitter.com'],
     45, 'BAJO', 'REGISTRAR', 'Más de 45 minutos en el día en áreas donde no es parte del trabajo.',
     ['marketing', 'audiovisual', 'adzone tv', 'comercial']),
]


def sembrar_reglas():
    from apps.core.models import Departamento
    creadas = 0
    for nombre, cat, campo, patrones, minutos, riesgo, accion, desc, excluir in REGLAS_INICIALES:
        regla, nueva = ReglaComportamiento.objects.get_or_create(nombre=nombre, defaults={
            'categoria': cat, 'campo': campo, 'patrones': '\n'.join(patrones), 'minutos_minimos': minutos,
            'riesgo': riesgo, 'accion': accion, 'descripcion': desc})
        if nueva:
            for texto in excluir:
                regla.excluir_departamentos.add(*Departamento.objects.filter(nombre__icontains=texto))
            creadas += 1
    return creadas


# ------------------------------------------------------------------ Motor de reglas
class Motor:
    """Carga las reglas activas una vez y dice cuáles coinciden con un minuto de actividad."""

    def __init__(self):
        self.reglas = []
        for r in ReglaComportamiento.objects.filter(activa=True).prefetch_related('departamentos', 'excluir_departamentos'):
            self.reglas.append((r, r.lista_patrones(), {d.pk for d in r.departamentos.all()}, {d.pk for d in r.excluir_departamentos.all()}))

    def coinciden(self, depto, app='', dominio='', titulo=''):
        app, dominio, titulo = (app or '').lower(), (dominio or '').lower(), (titulo or '').lower()
        salida = []
        for r, patrones, solo, excluir in self.reglas:
            if (solo and depto not in solo) or (depto in excluir):
                continue
            for p in patrones:
                if ((r.campo == 'DOMINIO' and _dominio_coincide(dominio, p)) or (r.campo == 'APP' and p in app)
                        or (r.campo == 'TITULO' and p in titulo)):
                    salida.append(r)
                    break
        return salida


def registrar_incidencias(usuario, depto, filas):
    """`filas`: [(minuto, app, dominio, titulo)] recién guardadas. Acumula minutos por regla y día; avisa al cruzar el mínimo."""
    if not filas:
        return 0
    motor = Motor()
    if not motor.reglas:
        return 0
    acumulado = defaultdict(lambda: [0, None, None, ''])
    for minuto, app, dominio, titulo in filas:
        for r in motor.coinciden(depto, app, dominio, titulo):
            a = acumulado[(r, timezone.localtime(minuto).date())]
            a[0] += 1
            a[1] = minuto if a[1] is None or minuto < a[1] else a[1]
            a[2] = minuto if a[2] is None or minuto > a[2] else a[2]
            a[3] = a[3] or ' · '.join(x for x in (app, dominio, titulo) if x)[:255]
    avisos = 0
    for (regla, dia), (n, primera, ultima, ejemplo) in acumulado.items():
        with transaction.atomic():
            inc, nueva = Incidencia.objects.select_for_update().get_or_create(
                regla=regla, usuario=usuario, dia=dia, defaults={'minutos': n, 'primera': primera, 'ultima': ultima, 'ejemplo': ejemplo})
            if not nueva:
                Incidencia.objects.filter(pk=inc.pk).update(minutos=F('minutos') + n, primera=min(inc.primera, primera),
                                                            ultima=max(inc.ultima, ultima))
                inc.refresh_from_db()
            if regla.accion == 'ALERTAR' and not inc.avisada and inc.minutos >= regla.minutos_minimos:
                Incidencia.objects.filter(pk=inc.pk).update(avisada=True)
                _avisar(inc)
                avisos += 1
    return avisos


def _avisar(inc):
    from apps.desempeno.permisos import administradores, revisores_de
    from apps.desempeno.servicios import avisar
    from .servicios import tecnologia
    from .servicios import vigilantes
    destinatarios = vigilantes()
    if inc.regla.categoria == 'SEGURIDAD' or inc.regla.riesgo in ('ALTO', 'CRITICO'):
        destinatarios += tecnologia()
    if inc.regla.riesgo == 'CRITICO':
        destinatarios += list(administradores())
    nombre = inc.usuario.get_full_name() or inc.usuario.username
    avisar([d for d in destinatarios if d.pk != inc.usuario_id], 'MONITOREO',
           f'{nombre}: «{inc.regla.nombre}» (riesgo {inc.regla.get_riesgo_display().lower()})',
           f'{inc.minutos} min hoy · {inc.ejemplo[:150]}', enlace=f'/monitoreo?ver=incidencias&persona={inc.usuario_id}')


# ------------------------------------------------------------------ Riesgo
NIVELES = [(0, 'SIN_RIESGO'), (1, 'BAJO'), (5, 'MEDIO'), (15, 'ALTO'), (30, 'CRITICO')]


def nivel_riesgo(puntos):
    nivel = 'SIN_RIESGO'
    for minimo, nombre in NIVELES:
        if puntos >= minimo:
            nivel = nombre
    return nivel


def riesgo(ids, desde, hasta):
    """Puntos de riesgo por persona: suma del peso de cada incidencia que cuenta (descartadas no suman)."""
    puntos = defaultdict(int)
    critico = set()
    reglas = defaultdict(lambda: defaultdict(int))
    for inc in Incidencia.objects.filter(usuario_id__in=ids, dia__range=(desde, hasta)).exclude(estado='DESCARTADA').select_related('regla'):
        if inc.minutos < inc.regla.minutos_minimos:
            continue
        puntos[inc.usuario_id] += ReglaComportamiento.PESO[inc.regla.riesgo]
        if inc.regla.riesgo == 'CRITICO':
            critico.add(inc.usuario_id)
        reglas[inc.usuario_id][inc.regla.nombre] += 1
    def nivel(u, p):
        n = nivel_riesgo(p)
        return 'ALTO' if u in critico and n in ('SIN_RIESGO', 'BAJO', 'MEDIO') else n  # una sola incidencia crítica ya es riesgo alto
    return {u: {'puntos': p, 'nivel': nivel(u, p), 'reglas': sorted(reglas[u].items(), key=lambda x: -x[1])[:3]}
            for u, p in puntos.items()}


# ------------------------------------------------------------------ Perfiles
def perfil_de(usuario):
    """Perfil propio, si no el de su departamento, si no ninguno (se usa la configuración general)."""
    propio = PerfilMonitoreo.objects.filter(personas=usuario).first()
    if propio:
        return propio
    puesto = getattr(getattr(usuario, 'perfil', None), 'puesto_trabajo', None)
    if puesto and puesto.departamento_id:
        return PerfilMonitoreo.objects.filter(departamentos=puesto.departamento_id).first()
    return None


def parametros(usuario, config=None):
    """Lo que se aplica a la persona: monitorear, capturas, cada cuánto, desenfoque y umbral de inactividad."""
    config = config or ConfiguracionMonitoreo.actual()
    p = perfil_de(usuario)
    if p is None:
        return {'perfil': None, 'monitorear': True, 'capturas': config.capturas, 'capturas_cada_min': config.capturas_cada_min,
                'desenfocar': config.desenfocar_capturas, 'umbral_inactivo_seg': config.umbral_inactivo_seg}
    return {'perfil': p.nombre, 'monitorear': p.monitorear, 'capturas': p.capturas, 'capturas_cada_min': max(1, p.capturas_cada_min),
            'desenfocar': p.desenfocar_capturas, 'umbral_inactivo_seg': max(30, p.umbral_inactivo_seg)}


def reaplicar(dias=30, hoy=None):
    """Vuelve a calcular las incidencias de los últimos `dias` con las reglas actuales (tras crear o cambiar reglas).
    No envía avisos por días pasados; las revisiones ya hechas se conservan."""
    from django.contrib.auth.models import User
    from apps.asistencia.servicios import rango
    from .models import Actividad
    from .servicios import departamento_de
    hoy = hoy or timezone.localdate()
    desde = hoy - timedelta(days=dias - 1)
    motor = Motor()
    conteo = defaultdict(lambda: [0, None, None, ''])
    deptos = {}
    for f in (Actividad.objects.filter(minuto__range=rango(desde, hoy)).values_list('usuario_id', 'minuto', 'app', 'dominio', 'titulo')
              .iterator(chunk_size=5000)):
        uid, minuto, app, dominio, titulo = f
        if uid not in deptos:
            deptos[uid] = departamento_de(User.objects.get(pk=uid))
        for r in motor.coinciden(deptos[uid], app, dominio, titulo):
            c = conteo[(r.pk, uid, timezone.localtime(minuto).date())]
            c[0] += 1
            c[1] = minuto if c[1] is None or minuto < c[1] else c[1]
            c[2] = minuto if c[2] is None or minuto > c[2] else c[2]
            c[3] = c[3] or ' · '.join(x for x in (app, dominio, titulo) if x)[:255]
    vistos = set()
    for (rid, uid, dia), (n, primera, ultima, ejemplo) in conteo.items():
        inc, _ = Incidencia.objects.update_or_create(regla_id=rid, usuario_id=uid, dia=dia, defaults={
            'minutos': n, 'primera': primera, 'ultima': ultima, 'ejemplo': ejemplo})
        if dia < hoy and not inc.avisada:
            Incidencia.objects.filter(pk=inc.pk).update(avisada=True)
        vistos.add(inc.pk)
    # Lo que ya no coincide con ninguna regla (regla cambiada) se borra si nadie lo revisó.
    borradas = Incidencia.objects.filter(dia__range=(desde, hoy), estado='NUEVA').exclude(pk__in=vistos).delete()[0]
    return len(vistos), borradas
