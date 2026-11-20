from django.db import migrations

PERFILES = ('Supervisor', 'Gerente de Departamento')
PERMISO = 'tareas.propias'


def dar(apps, schema_editor):
    """Quien supervisa (cargos de gerencia y encargados) también puede asignarse tareas a sí mismo. Se cambia en Accesos y permisos."""
    PermisosDePerfil = apps.get_model('core', 'PermisosDePerfil')
    for p in PermisosDePerfil.objects.filter(grupo__name__in=PERFILES):
        lista = list(p.permisos or [])
        if PERMISO not in lista:
            p.permisos = lista + [PERMISO]
            p.save(update_fields=['permisos'])


def quitar(apps, schema_editor):
    PermisosDePerfil = apps.get_model('core', 'PermisosDePerfil')
    for p in PermisosDePerfil.objects.filter(grupo__name__in=PERFILES):
        p.permisos = [c for c in (p.permisos or []) if c != PERMISO]
        p.save(update_fields=['permisos'])


class Migration(migrations.Migration):
    dependencies = [('core', '0009_espacio_de_departamento')]
    operations = [migrations.RunPython(dar, quitar)]
