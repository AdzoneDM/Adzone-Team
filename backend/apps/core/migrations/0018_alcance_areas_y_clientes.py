from django.db import migrations

PERFIL = ('Gestión de clientes', 'Consulta, crea, edita y completa los datos de los clientes (Marketing).', ['clientes.gestionar'], 42)


def crear_perfil(apps, schema_editor):
    """Perfil «Gestión de clientes» (permiso nuevo). A quién se le da se decide en Accesos y permisos."""
    Group = apps.get_model('auth', 'Group')
    PermisosDePerfil = apps.get_model('core', 'PermisosDePerfil')
    g, _ = Group.objects.get_or_create(name=PERFIL[0])
    PermisosDePerfil.objects.get_or_create(grupo=g, defaults={'descripcion': PERFIL[1], 'permisos': PERFIL[2], 'orden': PERFIL[3]})
    adm = PermisosDePerfil.objects.filter(grupo__name='Administrador').first()
    if adm and 'clientes.gestionar' not in (adm.permisos or []):
        adm.permisos = list(adm.permisos or []) + ['clientes.gestionar']
        adm.save(update_fields=['permisos'])


class Migration(migrations.Migration):
    dependencies = [('core', '0017_eventos_de_acceso')]
    operations = [migrations.RunPython(crear_perfil, migrations.RunPython.noop)]
