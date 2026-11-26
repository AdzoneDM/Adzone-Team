from django.db import migrations

DESCRIPCION = ('Consulta, crea, edita y completa los datos de los clientes y lleva las oportunidades comerciales (Marketing). '
               'Sin facturas, pagos ni cobros.')


def dar_permiso(apps, schema_editor):
    """«Oportunidades comerciales» para el perfil «Gestión de clientes» (Marketing) y para Dirección."""
    PermisosDePerfil = apps.get_model('core', 'PermisosDePerfil')
    for perfil in PermisosDePerfil.objects.filter(grupo__name__in=['Gestión de clientes', 'Administrador']):
        if 'comercial.oportunidades' not in (perfil.permisos or []):
            perfil.permisos = list(perfil.permisos or []) + ['comercial.oportunidades']
        if perfil.grupo.name == 'Gestión de clientes':
            perfil.descripcion = DESCRIPCION
        perfil.save()


class Migration(migrations.Migration):
    dependencies = [('core', '0020_clientes_completo')]
    operations = [migrations.RunPython(dar_permiso, migrations.RunPython.noop)]
