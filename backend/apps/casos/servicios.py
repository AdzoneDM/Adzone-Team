"""Flujo de atención de los casos: recepción → clasificación y derivación → atención y seguimiento → validación y cierre.
Cada paso valida aquí quién puede hacerlo y deja su constancia en el historial."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from apps.desempeno.permisos import es_administrador, puestos_de

from . import permisos
from .models import Caso, EvidenciaCaso, MovimientoCaso

MAX_EVIDENCIAS = 5
MAX_ARCHIVO = 15 * 1024 * 1024
EXTENSIONES = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.csv')


class NoPermitido(Exception):
    pass


def dias_revision(prioridad):
    """Días hasta la próxima revisión según la prioridad (propuesta inicial; se ajusta en settings)."""
    return getattr(settings, 'CASOS_DIAS_REVISION', {'ALTA': 1, 'MEDIA': 3, 'BAJA': 7}).get(prioridad or 'MEDIA', 3)


def _nombre(u):
    return (u.get_full_name() or u.username) if u else ''


def _mov(caso, usuario, tipo, nota='', **datos):
    return MovimientoCaso.objects.create(caso=caso, usuario=usuario, tipo=tipo, nota=nota or '', datos=datos)


def _avisar(destinos, titulo, caso, mensaje='', excepto=None):
    from apps.desempeno.servicios import avisar
    avisar([d for d in destinos if d is not None], 'CASO', f'{caso.codigo}: {titulo}', mensaje or caso.titulo, enlace=f'/casos/{caso.pk}', excepto=excepto)


def operaciones():
    """Personas de Operaciones (reciben los casos nuevos). Si no hay nadie en ese departamento, Dirección."""
    gente = [u for u in User.objects.filter(is_active=True, perfil__puesto_trabajo__departamento__nombre=permisos.departamento_gestor())]
    gente += [u for u in User.objects.filter(is_active=True, perfil__puestos_adicionales__departamento__nombre=permisos.departamento_gestor())]
    if not gente:
        gente = [u for u in User.objects.filter(is_active=True) if es_administrador(u)]
    return list({u.pk: u for u in gente}.values())


def jefes_de_area(departamento):
    """Quien dirige el área: los que ocupan los puestos de más arriba dentro del departamento; si están vacantes, sube por el organigrama."""
    from apps.organizacion.models import PuestoDeTrabajo
    puestos = list(PuestoDeTrabajo.objects.filter(departamento=departamento).select_related('supervisor'))
    ids = {p.id for p in puestos}
    cima = [p for p in puestos if p.supervisor_id not in ids]
    for _ in range(6):
        gente = [pf.user for p in cima for pf in p.perfiles_usuarios.select_related('user') if pf.user.is_active]
        gente += [pf.user for p in cima for pf in p.perfiles_adicionales.select_related('user') if pf.user.is_active]
        if gente:
            return list({u.pk: u for u in gente}.values())
        cima = [p.supervisor for p in cima if p.supervisor_id]
        if not cima:
            break
    return [u for u in User.objects.filter(is_active=True) if es_administrador(u)]


def personas_del_area(departamento):
    from django.db.models import Q
    return (User.objects.filter(is_active=True)
            .filter(Q(perfil__puesto_trabajo__departamento=departamento) | Q(perfil__puestos_adicionales__departamento=departamento))
            .distinct().order_by('first_name', 'last_name'))


def _evidencias(caso, usuario, archivos):
    from apps.core.archivos import revisar_contenido
    import os
    if caso.evidencias.count() + len(archivos) > MAX_EVIDENCIAS * 3:
        raise ValueError('Este caso ya tiene muchas evidencias.')
    if len(archivos) > MAX_EVIDENCIAS:
        raise ValueError(f'Máximo {MAX_EVIDENCIAS} archivos a la vez.')
    for f in archivos:
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in EXTENSIONES:
            raise ValueError(f'«{f.name}»: solo imágenes, PDF, Word, Excel, texto o CSV.')
        if f.size > MAX_ARCHIVO:
            raise ValueError(f'«{f.name}» pesa más de 15 MB.')
        problema = revisar_contenido(f)
        if problema:
            raise ValueError(f'«{f.name}» {problema}.')
    for f in archivos:
        EvidenciaCaso.objects.create(caso=caso, archivo=f, nombre=f.name[:150], tamano=f.size, subido_por=usuario)


def area_de(usuario):
    p = next(iter(puestos_de(usuario)), None)
    return p.departamento if p else None


@transaction.atomic
def reportar(usuario, datos, archivos=()):
    caso = Caso(reportado_por=usuario, area_origen=area_de(usuario), titulo=datos['titulo'].strip(), descripcion=datos['descripcion'].strip(),
                tipo=datos.get('tipo') or 'INCIDENCIA', categoria=datos.get('categoria') or 'OTRO', impacto=datos.get('impacto') or 'MEDIO',
                referencia=(datos.get('referencia') or '').strip())
    caso.save()
    _evidencias(caso, usuario, list(archivos))
    _mov(caso, usuario, 'RECIBIDO', caso.descripcion)
    _avisar(operaciones(), 'nuevo caso por registrar', caso, f'{_nombre(usuario)}: {caso.titulo}', excepto=usuario)
    return caso


def agregar_info(usuario, caso, nota, archivos=()):
    if not permisos.puede_ver(usuario, caso):
        raise NoPermitido
    if not (nota or archivos):
        raise ValueError('Escribe la información o adjunta una evidencia.')
    _evidencias(caso, usuario, list(archivos))
    _mov(caso, usuario, 'INFO', nota, archivos=[f.name for f in archivos])
    destinos = [caso.reportado_por, caso.responsable] + (operaciones() if not permisos.es_operaciones(usuario) else [])
    _avisar(destinos, 'nueva información', caso, (nota or 'Se agregó una evidencia')[:200], excepto=usuario)


@transaction.atomic
def unir(usuario, caso, destino):
    """El reporte es la misma situación que un caso abierto: su información pasa al historial de ese caso."""
    if not permisos.es_operaciones(usuario):
        raise NoPermitido
    if destino.pk == caso.pk or not destino.abierto:
        raise ValueError('Solo se une a otro caso que siga abierto.')
    if not caso.abierto:
        raise ValueError('Este caso ya está cerrado.')
    _mov(destino, usuario, 'UNIDO', f'{caso.codigo} · {_nombre(caso.reportado_por)}: {caso.titulo}\n\n{caso.descripcion}', desde=caso.codigo)
    caso.evidencias.update(caso=destino)
    caso.estado, caso.cerrado, caso.resultado = 'CERRADO', timezone.now(), f'Unido a {destino.codigo} (la misma situación ya se está atendiendo).'
    caso.validacion = 'Unido a un caso abierto'
    caso.save()
    _mov(caso, usuario, 'UNIDO', f'Se unió a {destino.codigo}.', hacia=destino.codigo)
    _avisar([caso.reportado_por], f'se unió a {destino.codigo}', caso, f'Tu reporte se sigue en {destino.codigo}: {destino.titulo}', excepto=usuario)


@transaction.atomic
def clasificar(usuario, caso, prioridad, area, categoria=None, tipo=None, proxima_revision=None, nota=''):
    """Operaciones fija la prioridad, deriva al área competente y fija la próxima revisión."""
    if not permisos.es_operaciones(usuario):
        raise NoPermitido
    if not caso.abierto:
        raise ValueError('El caso está cerrado: reábrelo primero.')
    if prioridad not in dict(Caso.PRIORIDADES):
        raise ValueError('Elige la prioridad.')
    if area is None:
        raise ValueError('Elige el área que lo atenderá.')
    cambia_area = caso.area_asignada_id != area.pk
    caso.prioridad, caso.area_asignada = prioridad, area
    if categoria:
        caso.categoria = categoria
    if tipo:
        caso.tipo = tipo
    caso.proxima_revision = proxima_revision or timezone.localdate() + timedelta(days=dias_revision(prioridad))
    if cambia_area:
        caso.responsable, caso.responsable_confirmado = None, False
    if caso.estado == 'RECIBIDO':
        caso.estado = 'EN_ATENCION'
    caso.save()
    _mov(caso, usuario, 'DERIVADO' if cambia_area else 'CLASIFICADO', nota, prioridad=prioridad, area=area.nombre,
         proxima_revision=caso.proxima_revision.isoformat())
    if cambia_area:
        _avisar(jefes_de_area(area), f'derivado a {area.nombre}: designa a un responsable', caso,
                f'Prioridad {caso.get_prioridad_display().lower()} · revisión el {caso.proxima_revision:%d/%m/%Y}', excepto=usuario)
    return caso


def designar(usuario, caso, responsable):
    if not (permisos.es_operaciones(usuario) or permisos.gestiona_area(usuario, caso)):
        raise NoPermitido
    if not caso.area_asignada_id:
        raise ValueError('Primero Operaciones deriva el caso a un área.')
    if responsable is None or not responsable.is_active:
        raise ValueError('Elige a una persona activa.')
    caso.responsable = responsable
    # Lo confirma el área receptora: si lo designa quien la dirige (o la persona se lo asigna), queda confirmado; si lo propone
    # Operaciones, el área lo confirma después
    caso.responsable_confirmado = responsable.pk == usuario.pk or usuario.pk in {j.pk for j in jefes_de_area(caso.area_asignada)}
    caso.save()
    _mov(caso, usuario, 'RESPONSABLE', '', responsable=_nombre(responsable), confirmado=caso.responsable_confirmado)
    _avisar([responsable], 'te asignaron este caso', caso, f'Revisión el {caso.proxima_revision:%d/%m/%Y}' if caso.proxima_revision else '', excepto=usuario)
    if not caso.responsable_confirmado:
        _avisar(jefes_de_area(caso.area_asignada), 'confirma al responsable', caso, f'Operaciones propuso a {_nombre(responsable)}.', excepto=usuario)


def confirmar_responsable(usuario, caso):
    if not (caso.responsable_id == usuario.pk or permisos.gestiona_area(usuario, caso)):
        raise NoPermitido
    if not caso.responsable_id:
        raise ValueError('No hay responsable que confirmar.')
    caso.responsable_confirmado = True
    caso.save(update_fields=['responsable_confirmado', 'actualizado'])
    _mov(caso, usuario, 'CONFIRMADO', '', responsable=_nombre(caso.responsable))


def _abierto(caso):
    if not caso.abierto:
        raise ValueError('El caso está cerrado.')


def avance(usuario, caso, nota, proxima_revision=None, fecha_estimada=None):
    """Documenta el seguimiento: queda en el historial y mueve la próxima revisión (así deja de estar vencido)."""
    if not permisos.puede_atender(usuario, caso):
        raise NoPermitido
    _abierto(caso)
    if not (nota or '').strip():
        raise ValueError('Escribe qué se hizo.')
    hoy = timezone.localdate()
    if proxima_revision and proxima_revision < hoy:
        raise ValueError('La próxima revisión no puede ser en el pasado.')
    caso.proxima_revision = proxima_revision or hoy + timedelta(days=dias_revision(caso.prioridad))
    if fecha_estimada:
        caso.fecha_estimada = fecha_estimada
    if caso.estado == 'RECIBIDO' and caso.area_asignada_id:
        caso.estado = 'EN_ATENCION'
    caso.save()
    _mov(caso, usuario, 'AVANCE', nota, proxima_revision=caso.proxima_revision.isoformat(),
         fecha_estimada=fecha_estimada.isoformat() if fecha_estimada else None)
    if not permisos.es_operaciones(usuario):
        _avisar(operaciones(), 'avance registrado', caso, nota[:200], excepto=usuario)


def bloquear(usuario, caso, motivo, proxima_revision):
    if not permisos.puede_atender(usuario, caso):
        raise NoPermitido
    _abierto(caso)
    if not (motivo or '').strip():
        raise ValueError('Todo bloqueo necesita su motivo.')
    if not proxima_revision or proxima_revision < timezone.localdate():
        raise ValueError('Todo bloqueo necesita una próxima fecha de revisión (hoy o después).')
    caso.bloqueado, caso.motivo_bloqueo, caso.proxima_revision = True, motivo.strip()[:500], proxima_revision
    caso.save()
    _mov(caso, usuario, 'BLOQUEO', motivo, proxima_revision=proxima_revision.isoformat())
    _avisar(operaciones() + [caso.responsable], 'quedó bloqueado', caso, motivo[:200], excepto=usuario)


def desbloquear(usuario, caso, nota=''):
    if not permisos.puede_atender(usuario, caso):
        raise NoPermitido
    caso.bloqueado, caso.motivo_bloqueo = False, ''
    caso.save()
    _mov(caso, usuario, 'DESBLOQUEO', nota)


def escalar(usuario, caso, nota):
    """Operaciones escala según la prioridad y la línea de autoridad: avisa a quien dirige el área (y a su superior)."""
    if not permisos.es_operaciones(usuario):
        raise NoPermitido
    _abierto(caso)
    if not (nota or '').strip():
        raise ValueError('Escribe por qué se escala.')
    if not caso.area_asignada_id:
        raise ValueError('Primero deriva el caso a un área.')
    jefes = jefes_de_area(caso.area_asignada)
    superiores = []
    from apps.desempeno.permisos import revisores_de
    for j in jefes:
        superiores += list(revisores_de(j))
    _mov(caso, usuario, 'ESCALADO', nota, a=[_nombre(u) for u in jefes + superiores])
    _avisar(jefes + superiores, f'escalado (prioridad {caso.get_prioridad_display().lower() or "sin definir"})', caso, nota[:200], excepto=usuario)


def solucion(usuario, caso, nota):
    if not permisos.puede_atender(usuario, caso):
        raise NoPermitido
    _abierto(caso)
    if not (nota or '').strip():
        raise ValueError('Describe la solución.')
    caso.estado, caso.bloqueado, caso.motivo_bloqueo = 'PENDIENTE_VALIDACION', False, ''
    caso.resultado = nota.strip()
    caso.save()
    _mov(caso, usuario, 'SOLUCION', nota)
    _avisar([caso.reportado_por] + operaciones(), 'solución comunicada: confirma si quedó resuelto', caso, nota[:200], excepto=usuario)


RESPUESTAS_TECNICAS = {'REALIZADA': 'Acción realizada', 'PENDIENTE': 'Queda pendiente', 'DESCARTADA': 'Se descarta'}


def respuesta_tecnica(usuario, caso, accion, nota, autorizacion=''):
    """Tecnología responde: la acción realizada o el motivo por el que queda pendiente o se descarta."""
    if not (permisos.es_tecnologia(caso) and (permisos.puede_atender(usuario, caso) or usuario.pk == caso.responsable_id)):
        raise NoPermitido
    _abierto(caso)
    if accion not in RESPUESTAS_TECNICAS:
        raise ValueError('Indica si la acción se realizó, queda pendiente o se descarta.')
    if not (nota or '').strip():
        raise ValueError('Explica la acción realizada o el motivo.')
    _mov(caso, usuario, 'TECNICA', nota, accion=accion, accion_texto=RESPUESTAS_TECNICAS[accion], autorizacion=(autorizacion or '')[:200])
    if accion == 'REALIZADA':
        caso.estado, caso.resultado = 'PENDIENTE_VALIDACION', nota.strip()
        caso.bloqueado = False
        caso.save()
    _avisar(operaciones() + [caso.reportado_por], f'respuesta de Tecnología: {RESPUESTAS_TECNICAS[accion].lower()}', caso, nota[:200], excepto=usuario)


def validar(usuario, caso, conforme, nota=''):
    """Quien reportó (o la persona competente, a través de Operaciones) confirma el resultado. Si no quedó resuelto, vuelve a atención."""
    if not (caso.reportado_por_id == usuario.pk or permisos.es_operaciones(usuario)):
        raise NoPermitido
    if caso.estado != 'PENDIENTE_VALIDACION':
        raise ValueError('El caso no está pendiente de validación.')
    if conforme:
        caso.validado_por = usuario
        caso.validacion = (nota or 'Conforme').strip()[:500]
        caso.save()
        _mov(caso, usuario, 'VALIDADO', nota)
        _avisar(operaciones(), 'validado: listo para cerrar', caso, nota[:200] if nota else 'Conforme', excepto=usuario)
    else:
        if not (nota or '').strip():
            raise ValueError('Cuenta qué sigue pasando.')
        caso.estado = 'EN_ATENCION'
        caso.proxima_revision = timezone.localdate() + timedelta(days=dias_revision(caso.prioridad))
        caso.save()
        _mov(caso, usuario, 'REABIERTO', f'No quedó resuelto: {nota}')
        _avisar(operaciones() + [caso.responsable], 'no quedó resuelto', caso, nota[:200], excepto=usuario)


def cerrar(usuario, caso, resultado, validacion=''):
    """Operaciones documenta el resultado y el cierre. Exige la validación (de quien reportó o la que coordinó Operaciones)."""
    if not permisos.es_operaciones(usuario):
        raise NoPermitido
    _abierto(caso)
    if not (resultado or caso.resultado or '').strip():
        raise ValueError('Documenta el resultado.')
    if not (caso.validado_por_id or (validacion or '').strip()):
        raise ValueError('Falta la validación: que quien reportó lo confirme, o escribe con quién y cómo se validó.')
    if resultado:
        caso.resultado = resultado.strip()
    if not caso.validado_por_id:
        caso.validado_por, caso.validacion = usuario, validacion.strip()[:500]
    caso.estado, caso.cerrado, caso.bloqueado, caso.proxima_revision = 'CERRADO', timezone.now(), False, None
    caso.save()
    _mov(caso, usuario, 'CERRADO', caso.resultado, validacion=caso.validacion)
    _avisar([caso.reportado_por, caso.responsable], 'cerrado', caso, caso.resultado[:200], excepto=usuario)


def reabrir(usuario, caso, motivo):
    if not (permisos.es_operaciones(usuario) or caso.reportado_por_id == usuario.pk):
        raise NoPermitido
    if caso.abierto:
        raise ValueError('El caso ya está abierto.')
    if not (motivo or '').strip():
        raise ValueError('Cuenta por qué se reabre.')
    caso.estado, caso.cerrado, caso.validado_por, caso.validacion = 'EN_ATENCION' if caso.area_asignada_id else 'RECIBIDO', None, None, ''
    caso.reaperturas += 1
    caso.proxima_revision = timezone.localdate() + timedelta(days=dias_revision(caso.prioridad))
    caso.save()
    _mov(caso, usuario, 'REABIERTO', motivo)
    _avisar(operaciones() + [caso.responsable], 'reabierto', caso, motivo[:200], excepto=usuario)


def avisar_vencidos(hoy=None):
    """Para el cron diario: un aviso por caso vencido a Operaciones y a su responsable (una vez al día)."""
    from apps.desempeno.models import Notificacion
    hoy = hoy or timezone.localdate()
    ops = operaciones()
    n = 0
    for caso in Caso.objects.filter(estado__in=Caso.ABIERTOS, proxima_revision__lt=hoy).select_related('responsable'):
        if Notificacion.objects.filter(tipo='CASO', enlace=f'/casos/{caso.pk}', titulo__contains='vencido', fecha__date=hoy).exists():
            continue
        dias = (hoy - caso.proxima_revision).days
        _avisar(ops + [caso.responsable], f'vencido ({dias} día{"s" if dias != 1 else ""} sin seguimiento)', caso,
                f'Su revisión era el {caso.proxima_revision:%d/%m/%Y}. Registra el avance o el bloqueo.')
        n += 1
    return n


def resumen(qs, hoy=None):
    """Abiertos, vencidos y cerrados por área y prioridad, y situaciones recurrentes (para Operaciones)."""
    hoy = hoy or timezone.localdate()
    from collections import Counter, defaultdict
    por_area = defaultdict(lambda: {'abiertos': 0, 'vencidos': 0, 'cerrados': 0})
    por_prioridad = defaultdict(lambda: {'abiertos': 0, 'vencidos': 0, 'cerrados': 0})
    totales = Counter()
    recurrentes = Counter()
    hace90 = timezone.now() - timedelta(days=90)
    for c in qs.select_related('area_asignada', 'area_origen'):
        clave = 'cerrados' if not c.abierto else ('vencidos' if c.vencido(hoy) else 'abiertos')
        area = c.area_asignada.nombre if c.area_asignada_id else 'Sin derivar'
        prio = c.get_prioridad_display() or 'Sin prioridad'
        por_area[area][clave] += 1
        por_prioridad[prio][clave] += 1
        totales[clave] += 1
        totales[c.estado] += 1
        if c.recibido >= hace90 and not c.validacion == 'Unido a un caso abierto':
            recurrentes[(c.get_categoria_display(), c.area_origen.nombre if c.area_origen_id else 'Sin área')] += 1
    rec = [{'categoria': k[0], 'area_origen': k[1], 'casos': v} for k, v in recurrentes.most_common() if v >= 3]
    return {'totales': dict(totales), 'por_area': [{'area': k, **v} for k, v in sorted(por_area.items())],
            'por_prioridad': [{'prioridad': k, **v} for k, v in por_prioridad.items()], 'recurrentes': rec}
