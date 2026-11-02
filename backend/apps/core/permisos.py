"""
Mínimo privilegio: cada persona tiene uno o más PERFILES (grupos) y cada perfil activa PERMISOS concretos.

- QUÉ puede hacer alguien lo dicen sus perfiles (más las excepciones de su persona).
- SOBRE QUIÉN lo dice el organigrama: los permisos «de equipo» se aplican a quienes dependen de su puesto,
  más su equipo adicional (EquipoExtra). Dirección los tiene sobre toda la empresa.
- Los permisos «de empresa» (monitoreo, salarios, usuarios, configuración…) no dependen del organigrama.
- Nadie valida su propio trabajo, tenga el permiso que tenga.
"""
from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.utils import timezone

# código, nombre, grupo (para la pantalla), alcance ('equipo' o 'empresa'), descripción
PERMISOS = [
    ('tareas.asignar', 'Asignar tareas', 'Su equipo', 'equipo', 'Crear, editar y reasignar tareas a las personas de su equipo.'),
    ('tareas.validar', 'Validar tareas', 'Su equipo', 'equipo', 'Validar, devolver o reabrir las entregas de su equipo y calificar su calidad.'),
    ('equipo.ver', 'Ver a su equipo', 'Su equipo', 'equipo', 'Ver las tareas, la ficha, los KPIs y la carga de trabajo de su equipo.'),
    ('equipo.evaluar', 'Evaluar a su equipo', 'Su equipo', 'equipo', 'Hacer la evaluación 360° de su equipo como supervisor y ver sus resultados.'),
    ('equipo.expediente', 'Expediente y planes de mejora', 'Su equipo', 'equipo', 'Registrar reconocimientos, observaciones e incidencias y abrir planes de mejora a su equipo.'),
    ('asistencia.ver', 'Asistencia del equipo', 'Su equipo', 'equipo', 'Ver la asistencia de su equipo, recibir sus avisos de tardanza y aprobar permisos.'),
    ('asistencia.corregir', 'Corregir marcajes', 'Su equipo', 'equipo', 'Agregar o borrar marcajes de su equipo (con nota y auditoría).'),
    ('direccion', 'Dirección', 'Empresa', 'empresa', 'Todo el negocio: todas las personas, panel gerencial, ranking, bonos, puestos, KPIs y reglas del puntaje.'),
    ('monitoreo.ver', 'Ver el monitoreo', 'Empresa', 'empresa', 'Actividad en la computadora de todas las personas, incidencias y justificaciones.'),
    ('monitoreo.capturas', 'Ver capturas de pantalla', 'Empresa', 'empresa', 'Capturas y pantallas en vivo.'),
    ('monitoreo.configurar', 'Configurar el monitoreo', 'Empresa', 'empresa', 'Reglas, perfiles de monitoreo y computadoras (encender o apagar).'),
    ('personal.usuarios', 'Personas y accesos', 'Empresa', 'empresa', 'Crear y desactivar personas, cambiar contraseñas, perfiles de acceso y excepciones.'),
    ('personal.salarios', 'Salarios y costo por hora', 'Empresa', 'empresa', 'Ver y editar salarios, costo por hora e historial salarial.'),
    ('talento.rrhh', 'Gestión del Talento', 'Empresa', 'empresa', 'Políticas, documentos laborales, ciclos de evaluación y expedientes de toda la empresa.'),
    ('sistema.configurar', 'Configuración del sistema', 'Empresa', 'empresa', 'Automatizaciones, integraciones y ajustes generales.'),
    ('auditoria.ver', 'Ver la auditoría', 'Empresa', 'empresa', 'Quién cambió qué en la plataforma.'),
]
CODIGOS = {p[0] for p in PERMISOS}
DE_EQUIPO = {p[0] for p in PERMISOS if p[3] == 'equipo'}

SUPERVISOR = ['tareas.asignar', 'tareas.validar', 'equipo.ver', 'equipo.evaluar', 'asistencia.ver']
# perfil: (descripción, permisos, orden). «Administrador» es el nombre histórico del grupo de Dirección.
PERFILES = {
    'Colaborador': ('Cumple sus tareas y ve solo lo suyo.', [], 10),
    'Supervisor': ('Asigna, valida y evalúa a su equipo y ve su asistencia.', SUPERVISOR, 20),
    'Gerente de Departamento': ('Como supervisor, más expediente, planes de mejora y corrección de marcajes.',
                                SUPERVISOR + ['equipo.expediente', 'asistencia.corregir'], 30),
    'Administrador': ('Dirección: todo el negocio y toda la empresa.', sorted(CODIGOS), 90),
    'Administrador del sistema': ('Configura personas, accesos, monitoreo e integraciones. No ve salarios, expedientes ni documentos.',
                                  ['personal.usuarios', 'monitoreo.ver', 'monitoreo.capturas', 'monitoreo.configurar', 'sistema.configurar', 'auditoria.ver'], 80),
    'Tecnología': ('Monitoreo, capturas, computadoras y equipos.', ['monitoreo.ver', 'monitoreo.capturas', 'monitoreo.configurar'], 60),
    'Gestión del Talento': ('Políticas, documentos, evaluaciones, expedientes, personas y salarios.',
                            ['talento.rrhh', 'personal.usuarios', 'personal.salarios'], 70),
    'Finanzas': ('Facturación, gastos, rentabilidad y costo por hora.', ['personal.salarios'], 65),
    'Coordinación': ('Recibe y libera OT, emite órdenes de área y autoriza vales.', [], 40),
    'Almacén': ('Inventario, vales de materiales y activos.', [], 45),
    'Agente Call Center': ('Su pantalla de call center y lo suyo.', [], 15),
}


def _cache(user):
    """Permisos efectivos (se calculan una vez por objeto de usuario, es decir, por petición)."""
    if not (user and user.is_authenticated):
        return set()
    if getattr(user, '_permisos_acceso', None) is not None:
        return user._permisos_acceso
    from .models import ExcepcionPermiso, PermisosDePerfil
    if user.is_superuser:
        efectivos = set(CODIGOS)
    else:
        efectivos = set()
        for permisos in PermisosDePerfil.objects.filter(grupo__user=user).values_list('permisos', flat=True):
            efectivos.update(p for p in (permisos or []) if p in CODIGOS)
        for permiso, conceder in ExcepcionPermiso.objects.filter(usuario=user).values_list('permiso', 'conceder'):
            if conceder:
                efectivos.add(permiso)
            else:
                efectivos.discard(permiso)
    user._permisos_acceso = efectivos
    return efectivos


def permisos(user):
    return set(_cache(user))


def tiene(user, codigo):
    p = _cache(user)
    return codigo in p or (codigo in DE_EQUIPO and 'direccion' in p)


def con_permiso(codigo):
    """Personas activas que tienen un permiso (para avisos)."""
    ids = set(User.objects.filter(is_active=True, is_superuser=True).values_list('pk', flat=True))
    from .models import ExcepcionPermiso, PermisosDePerfil
    grupos = [p.grupo_id for p in PermisosDePerfil.objects.all() if codigo in (p.permisos or [])]
    ids |= set(User.objects.filter(is_active=True, groups__in=grupos).values_list('pk', flat=True))
    ids |= set(ExcepcionPermiso.objects.filter(permiso=codigo, conceder=True, usuario__is_active=True).values_list('usuario_id', flat=True))
    ids -= set(ExcepcionPermiso.objects.filter(permiso=codigo, conceder=False).values_list('usuario_id', flat=True))
    return User.objects.filter(pk__in=ids)


def extras(user):
    """Ids de personas en su equipo adicional vigente."""
    from .models import EquipoExtra
    hoy = timezone.localdate()
    return list(EquipoExtra.objects.filter(jefe=user, colaborador__is_active=True).filter(Q(hasta__isnull=True) | Q(hasta__gte=hoy))
                .values_list('colaborador_id', flat=True))


def sembrar_perfiles():
    from .models import PermisosDePerfil
    for nombre, (desc, lista, orden) in PERFILES.items():
        g, _ = Group.objects.get_or_create(name=nombre)
        PermisosDePerfil.objects.get_or_create(grupo=g, defaults={'descripcion': desc, 'permisos': list(lista), 'orden': orden})


def permisos_de_perfiles(nombres):
    from .models import PermisosDePerfil
    salida = set()
    for p in PermisosDePerfil.objects.filter(grupo__name__in=list(nombres)).values_list('permisos', flat=True):
        salida.update(c for c in (p or []) if c in CODIGOS)
    return salida


def revisar_cambio(quien, persona, permisos_en_juego):
    """
    Anti-escalada: nadie cambia sus propios accesos, nadie da o quita permisos que no tiene y nadie
    toca a alguien con más permisos que él. Devuelve el motivo del rechazo o None.
    """
    if quien.is_superuser:
        return None
    if persona is not None and persona.pk == quien.pk:
        return "No puedes cambiar tus propios accesos: lo hace otra persona con ese permiso."
    mios = permisos(quien)
    faltan = set(permisos_en_juego) - mios
    if faltan:
        nombres = {p[0]: p[1] for p in PERMISOS}
        return "No puedes dar ni quitar permisos que tú no tienes: " + ', '.join(sorted(nombres.get(c, c) for c in faltan)) + '.'
    if persona is not None and not permisos(persona) <= mios:
        return "Esta persona tiene permisos que tú no tienes: sus accesos los cambia la Dirección."
    return None
