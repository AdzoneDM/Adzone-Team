"""
Mínimo privilegio: cada persona tiene uno o más PERFILES (grupos) y cada perfil activa PERMISOS concretos.

- QUÉ puede hacer alguien lo dicen sus perfiles (más las excepciones de su persona).
- SOBRE QUIÉN lo dice el organigrama: los permisos «de equipo» se aplican a quienes dependen de su puesto,
  más su equipo adicional (EquipoExtra). Dirección los tiene sobre toda la empresa.
- Los permisos «de empresa» (salarios, usuarios, configuración…) no dependen del organigrama.
- Nadie valida su propio trabajo, tenga el permiso que tenga.
"""
from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.utils import timezone

# código, nombre, grupo (para la pantalla), alcance ('equipo' o 'empresa'), descripción
PERMISOS = [
    ('tareas.asignar', 'Asignar tareas', 'Su equipo', 'equipo', 'Crear tareas y asignarlas a las personas de su equipo.'),
    ('tareas.editar', 'Editar tareas', 'Su equipo', 'equipo', 'Cambiar cualquier dato de las tareas de su equipo (responsable, fechas, prioridad, instrucciones, archivos y la calificación), en cualquier estado, también validadas. Queda en el historial con el antes y el después.'),
    ('tareas.eliminar', 'Eliminar tareas', 'Su equipo', 'equipo', 'Eliminar tareas de su equipo en cualquier estado, con un motivo: dejan de contar para el avance, el puntaje y los KPIs, pero se conservan con su historial y se pueden recuperar.'),
    ('tareas.reabrir', 'Reabrir tareas', 'Su equipo', 'equipo', 'Reabrir tareas de su equipo en cualquier estado, también validadas o canceladas, con un motivo: vuelven al flujo de entrega y validación y dejan de contar hasta que se validen otra vez.'),
    ('tareas.validar', 'Validar tareas', 'Su equipo', 'equipo', 'Validar o devolver las entregas de su equipo y calificar su calidad.'),
    ('equipo.ver', 'Ver a su equipo', 'Su equipo', 'equipo', 'Ver las tareas, la ficha, los KPIs y la carga de trabajo de su equipo.'),
    ('equipo.evaluar', 'Evaluar a su equipo', 'Su equipo', 'equipo', 'Hacer la evaluación 360° de su equipo como supervisor y ver sus resultados.'),
    ('equipo.expediente', 'Expediente y planes de mejora', 'Su equipo', 'equipo', 'Registrar reconocimientos, observaciones e incidencias y abrir planes de mejora a su equipo.'),
    ('tareas.propias', 'Asignarse tareas a sí mismo', 'Su equipo', 'equipo', 'Crear y programar tareas para sí mismo, y validar esas mismas tareas (queda registrado en su historial como autovalidación).'),
    ('tareas.otras_areas', 'Asignar tareas a otras áreas', 'Su equipo', 'empresa', 'Asignar tareas a personas de cualquier otra área (menos Call Center y Dirección) como aporte o colaboración, y gestionar las que pidió (editarlas, eliminarlas o reabrirlas, si tiene esos permisos); la tarea conserva su área de origen.'),
    ('asistencia.ver', 'Asistencia del equipo', 'Su equipo', 'equipo', 'Ver la asistencia de su equipo, recibir sus avisos de tardanza y aprobar permisos.'),
    ('asistencia.corregir', 'Corregir marcajes', 'Su equipo', 'equipo', 'Agregar o borrar marcajes de su equipo (con nota y auditoría).'),
    ('equipo.todos', 'Supervisar a toda la empresa', 'Empresa', 'empresa', 'Su equipo pasa a ser todo el personal (menos Dirección): los permisos de equipo que tenga se ejercen sobre todos, y recibe sus avisos de entregas y tardanzas.'),
    ('finanzas.gestionar', 'Finanzas', 'Empresa', 'empresa', 'Facturas, gastos, pagos, cotizaciones, rentabilidad (con el costo de cada persona) y Cashflow.'),
    ('operaciones.coordinar', 'Coordinación de producción', 'Empresa', 'empresa', 'Recibe y numera las órdenes de trabajo, emite las órdenes de área y autoriza vales.'),
    ('almacen.gestionar', 'Almacén', 'Empresa', 'empresa', 'Inventario, vales de materiales y despacho.'),
    ('callcenter.gestionar', 'Campañas de Call Center', 'Empresa', 'empresa', 'Crear y editar campañas y ver el desempeño de los agentes (quien supervisa a un agente ya lo tiene sobre su equipo).'),
    ('direccion', 'Dirección', 'Empresa', 'empresa', 'Todo el negocio: todas las personas, panel gerencial, ranking, bonos, puestos, KPIs y reglas del puntaje.'),
    ('chat.grupos', 'Grupos de chat', 'Empresa', 'empresa', 'Crear, editar y eliminar los grupos del chat por área o departamento (los demás solo participan en los que los agreguen).'),
    ('activos.gestionar', 'Equipos y activos', 'Empresa', 'empresa', 'Registrar, asignar y dar mantenimiento a los equipos y activos de la empresa.'),
    ('personal.directorio', 'Personas', 'Empresa', 'empresa', 'Ver a todas las personas, crear usuarios nuevos y desactivar cuentas, sin poder modificar correos ni cambiar contraseñas.'),
    ('personal.usuarios', 'Personas y accesos', 'Empresa', 'empresa', 'Crear y desactivar personas, cambiar contraseñas, perfiles de acceso y excepciones.'),
    ('personal.salarios', 'Salarios y costo por hora', 'Empresa', 'empresa', 'Ver y editar salarios, costo por hora e historial salarial.'),
    ('talento.rrhh', 'Gestión del Talento', 'Empresa', 'empresa', 'Políticas, documentos laborales, ciclos de evaluación y expedientes de toda la empresa.'),
    ('sistema.configurar', 'Configuración del sistema', 'Empresa', 'empresa', 'Automatizaciones, integraciones y ajustes generales.'),
    ('auditoria.ver', 'Ver la auditoría', 'Empresa', 'empresa', 'Quién cambió qué en la plataforma.'),
]
CODIGOS = {p[0] for p in PERMISOS}
DE_EQUIPO = {p[0] for p in PERMISOS if p[3] == 'equipo'}

GESTION_TAREAS = ['tareas.editar', 'tareas.eliminar', 'tareas.reabrir']
SUPERVISOR = ['tareas.asignar', 'tareas.propias', 'tareas.validar', 'equipo.ver', 'equipo.evaluar', 'asistencia.ver'] + GESTION_TAREAS
# perfil: (descripción, permisos, orden). «Administrador» es el nombre histórico del grupo de Dirección.
PERFILES = {
    'Colaborador': ('Cumple sus tareas y ve solo lo suyo.', [], 10),
    'Supervisor': ('Asigna, valida y evalúa a su equipo y ve su asistencia.', SUPERVISOR, 20),
    'Gerente de Departamento': ('Como supervisor, más expediente, planes de mejora, corrección de marcajes y grupos de chat.',
                                SUPERVISOR + ['equipo.expediente', 'asistencia.corregir', 'chat.grupos', 'tareas.otras_areas'], 30),
    'Administrador': ('Dirección: todo el negocio y toda la empresa.', sorted(CODIGOS), 90),
    'Administrador del sistema': ('Configura personas, accesos, equipos e integraciones. No ve salarios, expedientes ni documentos.',
                                  ['personal.usuarios', 'activos.gestionar', 'sistema.configurar', 'auditoria.ver', 'chat.grupos'], 80),
    'Tecnología': ('Equipos y activos de la empresa.', ['activos.gestionar'], 60),
    'Gestión del Talento': ('Políticas, documentos, evaluaciones, expedientes, personas y salarios.',
                            ['talento.rrhh', 'personal.usuarios', 'personal.salarios'], 70),
    'Finanzas': ('Facturación, gastos, rentabilidad y costo por hora.', ['personal.salarios', 'finanzas.gestionar'], 65),
    'Coordinación': ('Recibe y libera OT, emite órdenes de área y autoriza vales.', GESTION_TAREAS + ['operaciones.coordinar'], 40),
    'Operaciones': ('Asigna, edita, elimina, reabre y valida las tareas de su equipo y las que pide a otras áreas.',
                    SUPERVISOR + ['tareas.otras_areas'], 35),
    'Almacén': ('Inventario, vales de materiales y activos.', ['almacen.gestionar'], 45),
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


def efectivos(user):
    """Permisos con lo que implica Dirección (todos los de equipo)."""
    p = permisos(user)
    return p | DE_EQUIPO if 'direccion' in p else p


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
    mios = efectivos(quien)
    faltan = set(permisos_en_juego) - mios
    if faltan:
        nombres = {p[0]: p[1] for p in PERMISOS}
        return "No puedes dar ni quitar permisos que tú no tienes: " + ', '.join(sorted(nombres.get(c, c) for c in faltan)) + '.'
    if persona is not None and not efectivos(persona) <= mios:
        return "Esta persona tiene permisos que tú no tienes: sus accesos los cambia la Dirección."
    return None
