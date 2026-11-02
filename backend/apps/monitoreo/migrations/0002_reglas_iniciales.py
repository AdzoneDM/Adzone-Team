from django.db import migrations


def crear(apps, schema_editor):
    from apps.monitoreo.reglas_iniciales import sembrar
    sembrar(apps.get_model('monitoreo', 'ReglaProductividad'), apps.get_model('core', 'Departamento'))


class Migration(migrations.Migration):
    dependencies = [('monitoreo', '0001_initial'), ('core', '0003_acceso_equipo')]
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
