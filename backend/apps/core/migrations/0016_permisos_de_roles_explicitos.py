from django.db import migrations

# Roles que antes se daban por estar en un área o en un grupo y ahora son permisos de Accesos y permisos
POR_PERFIL = {
    'Finanzas': ['finanzas.gestionar'],
    'Coordinación': ['operaciones.coordinar'],
    'Almacén': ['almacen.gestionar'],
    'Administrador': ['finanzas.gestionar', 'operaciones.coordinar', 'almacen.gestionar', 'callcenter.gestionar'],
}
MOTIVO = 'Lo tenía por su área antes de la 12.67 (revisar en Accesos y permisos)'


def dar(apps, schema_editor):
    PermisosDePerfil = apps.get_model('core', 'PermisosDePerfil')
    ExcepcionPermiso = apps.get_model('core', 'ExcepcionPermiso')
    User = apps.get_model('auth', 'User')
    for p in PermisosDePerfil.objects.select_related('grupo'):
        extra = [c for c in POR_PERFIL.get(p.grupo.name, []) if c not in (p.permisos or [])]
        if extra:
            p.permisos = list(p.permisos or []) + extra
            p.save(update_fields=['permisos'])
    # Nadie pierde acceso hoy: quien lo tenía solo por su área queda con una excepción a su nombre, visible y revocable
    reglas = [('finanzas.gestionar', 'Administración', 'Finanzas'), ('callcenter.gestionar', 'Call Center', 'Agente Call Center')]
    for codigo, depto, excluir in reglas:
        for u in User.objects.filter(is_active=True, perfil__puesto_trabajo__departamento__nombre=depto).exclude(groups__name=excluir):
            ExcepcionPermiso.objects.get_or_create(usuario=u, permiso=codigo, defaults={'conceder': True, 'motivo': MOTIVO})


class Migration(migrations.Migration):
    dependencies = [('core', '0015_permisos_editar_eliminar_reabrir_tareas'), ('organizacion', '0001_initial')]
    operations = [migrations.RunPython(dar, migrations.RunPython.noop)]
