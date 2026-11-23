from django.db import migrations

PERMISO = 'tareas.otras_areas'
PERFILES = ('Administrador', 'Gerente de Departamento')


def dar(apps, schema_editor):
    """Asignar tareas a otras áreas es de las jefaturas: Dirección y los gerentes de departamento.
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
    dependencies = [('core', '0013_permiso_grupos_de_chat')]
    operations = [migrations.RunPython(dar, quitar)]
