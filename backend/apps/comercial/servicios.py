import re
import unicodedata

from django.db import transaction
from django.utils import timezone

from apps.desempeno.servicios import avisar

from .models import SERVICIOS, InteraccionComercial, MovimientoComercial, Oportunidad, SolicitudServicio


def registrar(usuario, tipo, oportunidad=None, solicitud=None, antes='', despues='', texto='', cambios=None):
    return MovimientoComercial.objects.create(usuario=usuario, tipo=tipo, oportunidad=oportunidad, solicitud=solicitud,
                                              estado_antes=antes, estado_despues=despues, texto=texto, cambios=cambios or {})


def gerentes_de(departamento_id):
    """Quienes gestionan el departamento (para avisarles de una solicitud nueva sin responsable)."""
    from django.contrib.auth.models import User

    from apps.operaciones.permisos import departamentos_a_cargo
    from apps.organizacion.models import PuestoDeTrabajo
    candidatos = User.objects.filter(is_active=True, perfil__puesto_trabajo__in=PuestoDeTrabajo.objects.filter(
        departamento_id=departamento_id)).distinct()
    salida = []
    for u in candidatos:
        a_cargo = departamentos_a_cargo(u)
        if a_cargo is not None and departamento_id in a_cargo:
            salida.append(u)
    return salida


def _valor(v):
    if hasattr(v, 'pk'):
        return str(v)
    return '' if v is None else str(v)


def guardar_cambios(instancia, datos, usuario, motivo=''):
    """Aplica `datos` y deja en el historial el antes y el después (estado aparte, como cambio de estado)."""
    estado_antes = instancia.estado
    cambios = {}
    for campo, valor in datos.items():
        antes = getattr(instancia, campo)
        if _valor(antes) != _valor(valor):
            cambios[campo] = {'antes': _valor(antes), 'despues': _valor(valor)}
            setattr(instancia, campo, valor)
    if not cambios:
        return instancia, {}
    if isinstance(instancia, Oportunidad) and 'estado' in cambios:
        instancia.fecha_cierre = timezone.now() if instancia.estado in Oportunidad.CERRADOS else None
    instancia.save()
    kw = {'oportunidad': instancia} if isinstance(instancia, Oportunidad) else {'solicitud': instancia}
    if 'estado' in cambios:
        registrar(usuario, 'ESTADO', antes=estado_antes, despues=instancia.estado, texto=motivo[:4000], **kw)
    otros = {k: v for k, v in cambios.items() if k != 'estado'}
    if otros:
        registrar(usuario, 'CAMBIO', cambios=otros, **kw)
    return instancia, cambios


def avisar_solicitud_nueva(s, quien):
    destinatarios = [s.responsable] if s.responsable else gerentes_de(s.departamento_id)
    avisar(destinatarios, 'COMERCIAL', f"Solicitud de servicio {s.codigo}: {s.servicio_nombre}",
           f"Cliente: {s.cliente}. {s.descripcion[:200]}", enlace=f"/oportunidades?solicitud={s.pk}", excepto=quien)


@transaction.atomic
def convertir_en_proyecto(s, usuario):
    """La solicitud aprobada se vuelve proyecto: el proyecto se enlaza (cliente, servicio y descripción no se copian a mano)."""
    from apps.operaciones.models import Proyecto
    proyecto = Proyecto.objects.create(
        nombre=f"{s.servicio_nombre} · {s.cliente.nombre}"[:200], cliente=s.cliente, departamento=s.departamento,
        responsable=s.responsable or usuario, creado_por=usuario,
        descripcion=f"Desde la solicitud {s.codigo}" + (f" (oportunidad {s.oportunidad.codigo})" if s.oportunidad_id else '')
                    + (f".\n\n{s.descripcion}" if s.descripcion else '.'))
    antes = s.estado
    s.proyecto, s.estado = proyecto, 'EN_EJECUCION'
    s.save(update_fields=['proyecto', 'estado', 'fecha_modificacion'])
    registrar(usuario, 'CONVERSION', solicitud=s, antes=antes, despues=s.estado, texto=f"Proyecto {proyecto.codigo}")
    if s.oportunidad_id:
        registrar(usuario, 'CONVERSION', oportunidad=s.oportunidad, texto=f"{s.codigo} → proyecto {proyecto.codigo}")
    return proyecto


@transaction.atomic
def enlazar_orden(s, orden, usuario):
    antes = s.estado
    s.orden, s.estado = orden, 'EN_EJECUCION'
    s.save(update_fields=['orden', 'estado', 'fecha_modificacion'])
    registrar(usuario, 'CONVERSION', solicitud=s, antes=antes, despues=s.estado, texto=f"Orden de trabajo {orden.codigo}")
    if s.oportunidad_id:
        registrar(usuario, 'CONVERSION', oportunidad=s.oportunidad, texto=f"{s.codigo} → orden {orden.codigo}")


def avisar_seguimientos(hoy=None):
    """Oportunidades abiertas con el seguimiento para hoy o atrasado: aviso diario a su responsable (para el cron)."""
    hoy = hoy or timezone.localdate()
    n = 0
    for o in (Oportunidad.objects.exclude(estado__in=Oportunidad.CERRADOS).filter(proximo_seguimiento__lte=hoy)
              .select_related('cliente', 'responsable', 'creado_por')):
        quien = o.responsable or o.creado_por
        if quien is None:
            continue
        atraso = (hoy - o.proximo_seguimiento).days
        avisar([quien], 'COMERCIAL', f"Seguimiento pendiente: {o.nombre_cliente}",
               f"{o.codigo} · {o.titulo} · {o.get_estado_display()}" + (f" · {atraso} día(s) de atraso" if atraso else " · hoy"),
               enlace=f"/oportunidades?oportunidad={o.pk}")
        n += 1
    return n


# ---------------------------------------------------------------- Prospecto → cliente registrado (sin duplicar)
def normalizar_nombre(texto):
    """«Café  Ñandú, S.R.L.» y «cafe ñandu srl» cuentan como el mismo nombre: sin tildes, sin mayúsculas, sin signos."""
    t = unicodedata.normalize('NFKD', texto or '')
    t = ''.join(c for c in t if not unicodedata.combining(c)).lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', t).split())


def normalizar_rnc(texto):
    return re.sub(r'\D', '', texto or '')


def coincidencias_cliente(nombre, rnc=''):
    """Clientes ya registrados que parecen el mismo prospecto.

    Devuelve (iguales, parecidos): «iguales» tienen el mismo nombre (sin distinguir mayúsculas ni tildes) o el mismo RNC, y con
    ellos NO se crea un cliente nuevo; «parecidos» contienen el nombre o están contenidos en él (solo como sugerencia).
    """
    from apps.operaciones.models import Cliente
    clave, rnc = normalizar_nombre(nombre), normalizar_rnc(rnc)
    iguales, parecidos = [], []
    if not clave and not rnc:
        return iguales, parecidos
    for c in Cliente.objects.only('id', 'nombre', 'rnc', 'contacto', 'telefono', 'correo', 'activo'):
        otro = normalizar_nombre(c.nombre)
        if (clave and otro == clave) or (rnc and normalizar_rnc(c.rnc) == rnc):
            iguales.append(c)
        elif clave and len(clave) >= 4 and otro and (clave in otro or (len(otro) >= 4 and otro in clave)):
            parecidos.append(c)
    return iguales, parecidos[:5]


def crear_solicitudes_de_interes(o, usuario):
    """Los servicios de interés anotados en el prospecto pasan a ser solicitudes para su departamento (los que aún no la tengan)."""
    from apps.core.models import Departamento
    ya = set(o.solicitudes.values_list('servicio', flat=True))
    creadas = []
    for codigo in o.servicios_interes or []:
        if codigo in ya or codigo not in SERVICIOS:
            continue
        sugerido = SERVICIOS[codigo][1]
        depto = (Departamento.objects.filter(nombre__iexact=sugerido).first() if sugerido else None) or o.departamento
        if depto is None:
            continue
        s = SolicitudServicio.objects.create(cliente=o.cliente, oportunidad=o, servicio=codigo, departamento=depto, creado_por=usuario,
                                             servicio_detalle='Por definir' if codigo == 'OTRO' else '', descripcion=o.necesidades)
        registrar(usuario, 'CREADA', solicitud=s, despues=s.estado, texto=s.servicio_nombre)
        registrar(usuario, 'CAMBIO', oportunidad=o, texto=f"Nueva solicitud {s.codigo}: {s.servicio_nombre} → {depto}")
        avisar_solicitud_nueva(s, usuario)
        ya.add(codigo)
        creadas.append(s)
    return creadas


@transaction.atomic
def convertir_en_cliente(o, usuario, cliente=None):
    """Enlaza la oportunidad a `cliente` (uno que ya existe) o, si no se indica, registra el cliente con los datos del prospecto.

    Si ya hay un cliente con el mismo nombre o RNC no se crea otro: se devuelve ValueError con esos clientes para elegir uno.
    """
    from apps.operaciones.models import Cliente
    nuevo = cliente is None
    if nuevo:
        iguales, _ = coincidencias_cliente(o.prospecto_nombre, o.prospecto_rnc)
        if iguales:
            raise ValueError(iguales)
        if not (o.prospecto_nombre or '').strip():
            raise ValueError([])
        cliente = Cliente.objects.create(
            nombre=o.prospecto_nombre.strip()[:200], rnc=o.prospecto_rnc, contacto=o.prospecto_contacto,
            telefono=o.prospecto_telefono, correo=o.prospecto_correo, creado_por=usuario,
            notas=f"Registrado desde la oportunidad {o.codigo}.")
    o.cliente = cliente
    o.save(update_fields=['cliente', 'fecha_modificacion'])
    texto = (f"Cliente nuevo registrado: {cliente.nombre}" if nuevo
             else f"Enlazada al cliente que ya existía: {cliente.nombre} (no se creó un duplicado)")
    registrar(usuario, 'CLIENTE', oportunidad=o, texto=texto,
              cambios={'cliente': {'antes': o.prospecto_nombre or '', 'despues': cliente.nombre}})
    crear_solicitudes_de_interes(o, usuario)
    return cliente, nuevo


def registrar_interaccion(o, usuario, datos):
    i = InteraccionComercial.objects.create(oportunidad=o, registrado_por=usuario, **datos)
    resumen = f"{i.get_tipo_display()}: {i.nota[:300]}"
    if i.monto_propuesta is not None:
        resumen += f" (RD$ {i.monto_propuesta:,.2f})"
    registrar(usuario, 'INTERACCION', oportunidad=o, texto=resumen)
    return i
