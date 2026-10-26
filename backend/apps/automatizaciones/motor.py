"""
Motor de automatizaciones: recibe un evento y ejecuta las reglas activas que coinciden.

Nunca rompe la acción del usuario: si una regla falla, queda anotado en la bitácora y sigue.
"""
import hashlib
import hmac
import json
import logging
import threading
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Ejecucion, Regla

log = logging.getLogger('adzone')


def _clave(objeto):
    return f"{objeto._meta.model_name}:{objeto.pk}"


def contexto(objeto):
    """Datos del objeto para filtros, mensajes ({numero}, {titulo}…) y el webhook."""
    modelo = objeto._meta.model_name
    d = {'modelo': modelo, 'id': objeto.pk}
    if modelo == 'ordentrabajo':
        d.update(numero=objeto.numero, titulo=objeto.titulo, cliente=objeto.cliente.nombre, tipo=objeto.tipo,
                 tipo_nombre=objeto.get_tipo_display(), estado=objeto.estado, estado_nombre=objeto.get_estado_display(),
                 departamento_id=objeto.departamento_id, departamento=objeto.departamento.nombre,
                 responsable=objeto.responsable.get_full_name() if objeto.responsable else '',
                 fecha_compromiso=str(objeto.fecha_compromiso or ''), monto=str(objeto.monto or ''),
                 enlace=f"/ordenes/{objeto.pk}")
    elif modelo == 'tarea':
        d.update(numero='', titulo=objeto.titulo, cliente=objeto.cliente, estado=objeto.estado,
                 responsable=objeto.colaborador.get_full_name() or objeto.colaborador.username,
                 fecha_limite=str(objeto.fecha_limite), orden_id=objeto.orden_id, proyecto_id=objeto.proyecto_id,
                 departamento_id=getattr(getattr(getattr(objeto.colaborador, 'perfil', None), 'puesto_trabajo', None), 'departamento_id', None),
                 enlace='/mis-tareas')
    elif modelo in ('factura', 'cotizacion'):
        d.update(numero=objeto.numero, titulo=getattr(objeto, 'titulo', '') or objeto.numero, cliente=objeto.cliente.nombre,
                 estado=objeto.estado, total=str(objeto.total), monto=str(objeto.total),
                 saldo=str(getattr(objeto, 'saldo', '')), vencimiento=str(getattr(objeto, 'vencimiento', '') or ''),
                 enlace='/finanzas')
    elif modelo == 'pago':
        f = objeto.factura
        d.update(numero=f.numero, titulo=f"Pago de {f.numero}", cliente=f.cliente.nombre, monto=str(objeto.monto),
                 estado=f.estado, enlace='/finanzas')
    return d


def _coincide(regla, datos):
    for campo in ('tipo', 'estado', 'departamento_id'):
        esperado = (regla.condiciones or {}).get(campo)
        if esperado not in (None, '', []) and str(datos.get(campo)) != str(esperado):
            return False
    return True


def _texto(plantilla, datos):
    class Seguro(dict):
        def __missing__(self, k):
            return ''
    try:
        return plantilla.format_map(Seguro(datos))
    except (ValueError, IndexError):
        return plantilla


def _destinatarios(regla, objeto, datos):
    from django.contrib.auth.models import User
    from apps.desempeno.permisos import administradores, revisores_de
    from apps.operaciones.permisos import es_finanzas
    quienes = []
    for a in (regla.parametros or {}).get('a', []):
        if a == 'responsable':
            quienes.append(getattr(objeto, 'responsable', None) or getattr(objeto, 'colaborador', None))
        elif a == 'solicitante':
            quienes.append(getattr(objeto, 'solicitada_por', None) or getattr(objeto, 'asignada_por', None))
        elif a == 'jefes':
            if datos['modelo'] == 'ordentrabajo':
                from apps.operaciones.servicios import jefes_de_departamento
                quienes.extend(jefes_de_departamento(objeto.departamento_id))
            elif datos['modelo'] == 'tarea':
                quienes.extend(revisores_de(objeto.colaborador))
        elif a == 'finanzas':
            quienes.extend(u for u in User.objects.filter(is_active=True) if es_finanzas(u))
        elif a == 'administradores':
            quienes.extend(administradores())
    uid = (regla.parametros or {}).get('usuario_id')
    if uid:
        quienes.append(User.objects.filter(pk=uid, is_active=True).first())
    return [q for q in quienes if q]


def _webhook(url, cuerpo):
    datos = json.dumps(cuerpo, ensure_ascii=False, default=str).encode()
    cabeceras = {'Content-Type': 'application/json', 'User-Agent': 'AdzoneTeam/5', 'X-Adzone-Evento': cuerpo['evento']}
    secreto = getattr(settings, 'AUTOMATIZACIONES_SECRETO', '')
    if secreto:
        cabeceras['X-Adzone-Firma'] = hmac.new(secreto.encode(), datos, hashlib.sha256).hexdigest()
    pedido = urllib.request.Request(url, data=datos, headers=cabeceras, method='POST')
    with urllib.request.urlopen(pedido, timeout=8) as r:  # noqa: S310 (URL la pone un administrador)
        return r.status


def ejecutar(regla, evento, objeto, quien=None):
    from apps.desempeno.models import Tarea
    from apps.desempeno.servicios import avisar
    datos = contexto(objeto)
    p = regla.parametros or {}
    if regla.accion == 'AVISAR':
        destinatarios = _destinatarios(regla, objeto, datos)
        mensaje = _texto(p.get('mensaje') or '{titulo}', datos)
        avisar(destinatarios, 'AUTOMATIZACION', _texto(p.get('titulo') or regla.nombre, datos), mensaje,
               enlace=datos.get('enlace', ''))
        return f"Aviso a {len(destinatarios)} persona(s)"
    if regla.accion == 'CREAR_TAREA':
        from django.contrib.auth.models import User
        asignar = p.get('asignar', 'responsable')
        persona = None
        if asignar == 'usuario':
            persona = User.objects.filter(pk=p.get('usuario_id'), is_active=True).first()
        elif asignar == 'solicitante':
            persona = getattr(objeto, 'solicitada_por', None)
        else:
            persona = getattr(objeto, 'responsable', None) or getattr(objeto, 'colaborador', None)
        if persona is None:
            return "Sin persona a quién asignar"
        tarea = Tarea.objects.create(
            titulo=_texto(p.get('titulo') or regla.nombre, datos)[:255], colaborador=persona,
            descripcion=f"Creada por la automatización «{regla.nombre}».",
            cliente=datos.get('cliente', '')[:150], prioridad=p.get('prioridad', 'MEDIA'),
            fecha_limite=timezone.localdate() + timedelta(days=int(p.get('dias', 2) or 0)),
            orden=objeto if datos['modelo'] == 'ordentrabajo' else None,
            proyecto=getattr(objeto, 'proyecto', None) if datos['modelo'] in ('ordentrabajo', 'factura') else None)
        avisar([persona], 'ASIGNADA', f"Nueva tarea: {tarea.titulo}", f"La creó la automatización «{regla.nombre}».",
               tarea=tarea, enlace='/mis-tareas')
        return f"Tarea creada para {persona.get_full_name() or persona.username}"
    if regla.accion == 'WEBHOOK':
        url = p.get('url', '')
        cuerpo = {'evento': evento, 'regla': regla.nombre, 'fecha': timezone.now().isoformat(), 'datos': datos}
        if getattr(settings, 'AUTOMATIZACIONES_SINCRONO', False):
            return f"Webhook {_webhook(url, cuerpo)}"

        def enviar():
            try:
                _webhook(url, cuerpo)
            except Exception as e:  # noqa: BLE001
                log.warning("Webhook de «%s» falló: %s", regla.nombre, e)
                Ejecucion.objects.create(regla=regla, objeto=_clave(objeto), resultado=f"Webhook falló: {e}"[:255], exito=False)
        threading.Thread(target=enviar, daemon=True).start()
        return "Webhook enviado"
    return "Acción desconocida"


def disparar(evento, objeto, quien=None, una_sola_vez=False):
    reglas = [r for r in Regla.objects.filter(activa=True, evento=evento)]
    if not reglas:
        return 0
    datos = contexto(objeto)
    hechas = 0
    for regla in reglas:
        if not _coincide(regla, datos):
            continue
        clave = _clave(objeto)
        if una_sola_vez and Ejecucion.objects.filter(regla=regla, objeto=clave, exito=True).exists():
            continue
        try:
            resultado, exito = ejecutar(regla, evento, objeto, quien), True
        except Exception as e:  # noqa: BLE001 — una regla mala no debe frenar el trabajo
            log.exception("Automatización «%s» falló", regla.nombre)
            resultado, exito = f"Error: {e}", False
        Ejecucion.objects.create(regla=regla, objeto=clave, resultado=str(resultado)[:255], exito=exito)
        Regla.objects.filter(pk=regla.pk).update(veces=regla.veces + 1, ultima_vez=timezone.now())
        hechas += 1
    return hechas


def revisar_vencimientos():
    """Para la tarea diaria: dispara los eventos de vencimiento (una sola vez por regla y objeto)."""
    from apps.desempeno.models import Tarea
    from apps.finanzas.models import Factura
    from apps.operaciones.models import OrdenTrabajo
    hoy = timezone.localdate()
    total = 0
    for orden in OrdenTrabajo.objects.filter(estado__in=['APROBADA', 'EN_PRODUCCION', 'CONTROL_CALIDAD', 'EN_PAUSA'],
                                             fecha_compromiso__lt=hoy):
        total += disparar('ORDEN_VENCIDA', orden, una_sola_vez=True)
    for tarea in Tarea.objects.filter(estado__in=['PENDIENTE', 'EN_PROGRESO'], fecha_limite__lt=hoy):
        total += disparar('TAREA_VENCIDA', tarea, una_sola_vez=True)
    for factura in Factura.objects.filter(estado='EMITIDA', vencimiento__lt=hoy):
        total += disparar('FACTURA_VENCIDA', factura, una_sola_vez=True)
    return total
