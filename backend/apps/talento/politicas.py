"""Políticas (a quién aplican, aceptación por versión, cumplimiento) y documentos del expediente (faltantes y vencimientos)."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from .models import AceptacionPolitica, DocumentoEmpleado, Politica, VersionPolitica


def es_rrhh(user):
    """Gestión del Talento: la administración, el grupo «RRHH» o quien trabaje en ese departamento."""
    from apps.desempeno.permisos import es_administrador
    if not (user and user.is_authenticated):
        return False
    if es_administrador(user) or user.groups.filter(name='RRHH').exists():
        return True
    puesto = getattr(getattr(user, 'perfil', None), 'puesto_trabajo', None)
    nombre = (puesto.departamento.nombre if puesto and puesto.departamento_id else '').lower()
    return 'talento' in nombre or 'recursos humanos' in nombre


def gente_rrhh():
    from apps.desempeno.permisos import administradores
    gente = {u.pk: u for u in administradores()}
    for u in User.objects.filter(is_active=True).filter(Q(groups__name='RRHH') | Q(perfil__puesto_trabajo__departamento__nombre__icontains='talento')
                                                        | Q(perfil__puesto_trabajo__departamento__nombre__icontains='recursos humanos')):
        gente[u.pk] = u
    return list(gente.values())


# ------------------------------------------------------------------ Políticas
def personas_de(politica):
    qs = User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=False)
    if politica.para_todos:
        return qs
    return qs.filter(Q(perfil__puesto_trabajo__in=politica.puestos.all())
                     | Q(perfil__puesto_trabajo__departamento__in=politica.departamentos.all())).distinct()


def aplica(politica, usuario):
    if politica.para_todos:
        return True
    puesto = getattr(getattr(usuario, 'perfil', None), 'puesto_trabajo', None)
    if puesto is None:
        return False
    return politica.puestos.filter(pk=puesto.pk).exists() or politica.departamentos.filter(pk=puesto.departamento_id).exists()


def de_usuario(usuario):
    """Políticas publicadas que le aplican, con si ya aceptó la versión vigente."""
    aceptadas = dict(AceptacionPolitica.objects.filter(usuario=usuario).values_list('politica_id', 'version').order_by('version'))
    salida = []
    for p in Politica.objects.filter(activa=True, borrador=False).prefetch_related('puestos', 'departamentos'):
        if aplica(p, usuario):
            salida.append((p, aceptadas.get(p.pk) == p.version))
    return salida


def pendientes(usuario):
    return [p for p, ok in de_usuario(usuario) if p.requiere_aceptacion and not ok]


def aceptar(politica, usuario, ip=None, navegador=''):
    a, _ = AceptacionPolitica.objects.get_or_create(politica=politica, usuario=usuario, version=politica.version,
                                                    defaults={'ip': ip, 'navegador': (navegador or '')[:200]})
    if politica.categoria == 'MONITOREO':
        # Aceptar la política de monitoreo es también el consentimiento que pide el agente.
        from apps.monitoreo.models import ConfiguracionMonitoreo, Consentimiento
        Consentimiento.objects.get_or_create(usuario=usuario, version=ConfiguracionMonitoreo.actual().version_politica, defaults={'ip': ip})
    return a


def avisar_publicacion(politica, por=None, nueva=True):
    from apps.desempeno.servicios import avisar
    if not politica.requiere_aceptacion:
        return 0
    gente = list(personas_de(politica))
    titulo = f'{"Nueva política" if nueva else "Se actualizó"}: {politica.titulo}' + ('' if nueva else f' (versión {politica.version})')
    avisar(gente, 'TALENTO', titulo, 'Léela y acéptala en Adzone Team.', enlace=f'/politicas?ver={politica.pk}', excepto=por)
    return len(gente)


def nueva_version(politica, titulo, contenido, cambio, por):
    politica.version += 1
    politica.titulo = titulo or politica.titulo
    politica.contenido = contenido
    politica.vigente_desde = timezone.localdate()
    politica.save()
    VersionPolitica.objects.create(politica=politica, version=politica.version, titulo=politica.titulo, contenido=contenido,
                                   cambio=(cambio or '')[:255], por=por)
    if not politica.borrador:
        avisar_publicacion(politica, por, nueva=False)
    return politica


def cumplimiento():
    """Por política publicada: a cuántos aplica, cuántos aceptaron la versión vigente y quién falta."""
    filas = []
    for p in Politica.objects.filter(activa=True, borrador=False, requiere_aceptacion=True).prefetch_related('puestos', 'departamentos'):
        gente = list(personas_de(p).select_related('perfil__puesto_trabajo__departamento'))
        ok = set(AceptacionPolitica.objects.filter(politica=p, version=p.version).values_list('usuario_id', flat=True))
        faltan = [u for u in gente if u.pk not in ok]
        filas.append({'id': p.pk, 'titulo': p.titulo, 'version': p.version, 'personas': len(gente), 'aceptaron': len(gente) - len(faltan),
                      'porcentaje': round((len(gente) - len(faltan)) / len(gente) * 100, 1) if gente else None,
                      'faltan': [{'id': u.pk, 'nombre': u.get_full_name() or u.username,
                                  'departamento': u.perfil.puesto_trabajo.departamento.nombre if u.perfil.puesto_trabajo.departamento_id else None}
                                 for u in faltan]})
    return filas


# ------------------------------------------------------------------ Documentos
def estado_documentos(hoy=None, dias=30):
    """Quién no tiene los documentos requeridos y qué vence (o ya venció) en los próximos `dias`."""
    hoy = hoy or timezone.localdate()
    tipos = dict(DocumentoEmpleado.TIPOS)
    tiene = {}
    for uid, tipo in DocumentoEmpleado.objects.values_list('colaborador_id', 'tipo'):
        tiene.setdefault(uid, set()).add(tipo)
    faltantes = []
    for u in User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=False).order_by('first_name'):
        falta = [t for t in DocumentoEmpleado.REQUERIDOS if t not in tiene.get(u.pk, set())]
        if falta:
            faltantes.append({'id': u.pk, 'nombre': u.get_full_name() or u.username, 'faltan': [tipos[t] for t in falta]})
    vencen = [{'id': d.pk, 'persona': d.colaborador.get_full_name() or d.colaborador.username, 'usuario': d.colaborador_id,
               'tipo': tipos[d.tipo], 'titulo': d.titulo, 'vence': d.vence, 'vencido': d.vence < hoy}
              for d in DocumentoEmpleado.objects.filter(vence__isnull=False, vence__lte=hoy + timedelta(days=dias),
                                                        colaborador__is_active=True).select_related('colaborador').order_by('vence')]
    return {'faltantes': faltantes, 'vencen': vencen}


def revisar(hoy=None):
    """Para el cron diario: avisa a RR. HH. de documentos por vencer y recuerda las políticas pendientes cada semana."""
    from apps.desempeno.servicios import avisar
    from apps.monitoreo.models import AlertaEnviada
    hoy = hoy or timezone.localdate()
    enviados = 0
    rrhh = gente_rrhh()
    for d in DocumentoEmpleado.objects.filter(vence__isnull=False, vence__lte=hoy + timedelta(days=30), vence__gte=hoy - timedelta(days=1),
                                              colaborador__is_active=True).select_related('colaborador'):
        _, nueva = AlertaEnviada.objects.get_or_create(usuario=d.colaborador, clave=f'doc-{d.pk}-{d.vence:%Y%m%d}',
                                                       defaults={'tipo': 'DOCUMENTO', 'detalle': d.titulo[:255]})
        if nueva:
            avisar(rrhh, 'TALENTO', f'Vence el {d.vence:%d/%m}: {d.titulo} de {d.colaborador.get_full_name() or d.colaborador.username}',
                   'Renuévalo o sube la nueva versión al expediente.', enlace=f'/politicas?ver=documentos&usuario={d.colaborador_id}')
            enviados += 1
    semana = hoy.strftime('%G%V')
    for u in User.objects.filter(is_active=True, perfil__puesto_trabajo__isnull=False):
        faltan = [p for p in pendientes(u) if (hoy - p.vigente_desde).days >= 3]
        if not faltan:
            continue
        _, nueva = AlertaEnviada.objects.get_or_create(usuario=u, clave=f'pol-{semana}', defaults={'tipo': 'POLITICA', 'detalle': str(len(faltan))})
        if nueva:
            avisar([u], 'TALENTO', f'Tienes {len(faltan)} política(s) por aceptar', ', '.join(p.titulo for p in faltan[:3]), enlace='/politicas')
            enviados += 1
    return enviados
