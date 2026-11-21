from django.db import migrations


def crear(apps, schema_editor):
    """(Módulo retirado) Sembraba reglas que la migración final borra: ya no hace nada."""


class Migration(migrations.Migration):
    dependencies = [('monitoreo', '0001_initial'), ('core', '0003_acceso_equipo')]
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
