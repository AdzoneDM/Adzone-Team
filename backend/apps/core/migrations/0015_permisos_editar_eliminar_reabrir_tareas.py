from django.db import migrations

NUEVOS = ['tareas.editar', 'tareas.eliminar', 'tareas.reabrir']
# Requerimiento de mejora (edición, eliminación y reapertura): estos perfiles gestionan las tareas de su equipo sin ser administradores
PERFILES = ('Supervisor', 'Gerente de Departamento', 'Coordinación', 'Operaciones', 'Administrador')
OPERACIONES = ('Asigna, edita, elimina, reabre y valida las tareas de su equipo y las que pide a otras áreas.',
               ['tareas.asignar', 'tareas.propias', 'tareas.validar', 'equipo.ver', 'equipo.evaluar', 'asistencia.ver',
                'tareas.otras_areas'] + NUEVOS, 35)


def dar(apps, schema_editor):
    """Antes «Asignar tareas» incluía editar y «Validar tareas» incluía reabrir: quien los tenía conserva lo que podía hacer.
    Supervisor, Gerente de Departamento, Coordinación y Operaciones reciben editar, eliminar y reabrir. Todo se cambia en Accesos y permisos."""
    Group = apps.get_model('auth', 'Group')
    PermisosDePerfil = apps.get_model('core', 'PermisosDePerfil')
    ExcepcionPermiso = apps.get_model('core', 'ExcepcionPermiso')
    grupo, _ = Group.objects.get_or_create(name='Operaciones')
    PermisosDePerfil.objects.get_or_create(grupo=grupo, defaults={'descripcion': OPERACIONES[0], 'permisos': OPERACIONES[1], 'orden': OPERACIONES[2]})
    for p in PermisosDePerfil.objects.select_related('grupo'):
        lista = list(p.permisos or [])
        sumar = []
        if 'tareas.asignar' in lista:
            sumar.append('tareas.editar')
        if 'tareas.validar' in lista:
            sumar.append('tareas.reabrir')
        if p.grupo.name in PERFILES:
            sumar += NUEVOS
        nuevos = [c for c in dict.fromkeys(sumar) if c not in lista]
        if nuevos:
            p.permisos = lista + nuevos
            p.save(update_fields=['permisos'])
    # Las excepciones por persona siguen igual: a quien se le dio (o quitó) asignar se le da (o quita) editar; validar → reabrir
    for origen, destino in (('tareas.asignar', 'tareas.editar'), ('tareas.validar', 'tareas.reabrir')):
        for e in ExcepcionPermiso.objects.filter(permiso=origen):
            ExcepcionPermiso.objects.get_or_create(usuario_id=e.usuario_id, permiso=destino,
                                                   defaults={'conceder': e.conceder, 'motivo': (e.motivo or '')[:200], 'creado_por_id': e.creado_por_id})


def quitar(apps, schema_editor):
    PermisosDePerfil = apps.get_model('core', 'PermisosDePerfil')
    for p in PermisosDePerfil.objects.all():
        if any(c in (p.permisos or []) for c in ('tareas.editar', 'tareas.reabrir')):
            p.permisos = [c for c in p.permisos if c not in ('tareas.editar', 'tareas.reabrir')]
            p.save(update_fields=['permisos'])


class Migration(migrations.Migration):
    dependencies = [('core', '0014_permiso_asignar_a_otras_areas'), ('auth', '0012_alter_user_first_name_max_length')]
    operations = [migrations.RunPython(dar, quitar)]
