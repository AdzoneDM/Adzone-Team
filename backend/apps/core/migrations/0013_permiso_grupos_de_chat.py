from django.db import migrations

PERMISO = 'chat.grupos'
PERFILES = ('Administrador', 'Administrador del sistema', 'Gerente de Departamento')


def dar(apps, schema_editor):
    """Crear y administrar grupos de chat es de las jefaturas: Dirección, el administrador del sistema y los gerentes de departamento.
    Se puede cambiar en Accesos y permisos (por perfil o por persona)."""
    PermisosDePerfil = apps.get_model('core', 'PermisosDePerfil')
    for p in PermisosDePerfil.objects.filter(grupo__name__in=PERFILES):
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
    dependencies = [('core', '0012_alerta_enviada_y_sin_permisos_de_monitoreo')]
    operations = [migrations.RunPython(dar, quitar)]
