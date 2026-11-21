from django.db import migrations

PERMISO = 'personal.directorio'


def dar(apps, schema_editor):
    """Dirección conserva todo (el permiso nuevo es una parte de «Personas y accesos»): se agrega al perfil Administrador."""
    PermisosDePerfil = apps.get_model('core', 'PermisosDePerfil')
    for p in PermisosDePerfil.objects.filter(grupo__name='Administrador'):
        lista = list(p.permisos or [])
        if PERMISO not in lista:
            p.permisos = lista + [PERMISO]
            p.save(update_fields=['permisos'])


def quitar(apps, schema_editor):
    PermisosDePerfil = apps.get_model('core', 'PermisosDePerfil')
    for p in PermisosDePerfil.objects.all():
        if PERMISO in (p.permisos or []):
            p.permisos = [c for c in p.permisos if c != PERMISO]
            p.save(update_fields=['permisos'])


class Migration(migrations.Migration):
    dependencies = [('core', '0010_supervisores_se_asignan_tareas')]
    operations = [migrations.RunPython(dar, quitar)]
