from django.db import migrations


def sembrar(apps, schema_editor):
    """(Módulo retirado) Sembraba reglas que la migración final borra: ya no hace nada."""


class Migration(migrations.Migration):
    dependencies = [('monitoreo', '0005_perfiles_y_reglas'), ('core', '0001_initial')]
    operations = [migrations.RunPython(sembrar, migrations.RunPython.noop)]
