from django.db import migrations


def dar_a_direccion(apps, schema_editor):
    """Permiso nuevo «Clientes: eliminar y proyectos»: Dirección lo tiene todo; a las demás personas se les da por excepción."""
    PermisosDePerfil = apps.get_model('core', 'PermisosDePerfil')
    adm = PermisosDePerfil.objects.filter(grupo__name='Administrador').first()
    if adm and 'clientes.completo' not in (adm.permisos or []):
        adm.permisos = list(adm.permisos or []) + ['clientes.completo']
        adm.save(update_fields=['permisos'])


class Migration(migrations.Migration):
    dependencies = [('core', '0019_alcance_por_areas')]
    operations = [migrations.RunPython(dar_a_direccion, migrations.RunPython.noop)]
