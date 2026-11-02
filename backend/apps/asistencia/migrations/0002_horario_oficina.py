from django.db import migrations

OFICINA = {'0': ['08:00', '17:00'], '1': ['08:00', '17:00'], '2': ['08:00', '17:00'], '3': ['08:00', '17:00'],
           '4': ['08:00', '17:00'], '5': ['08:00', '12:00']}


def crear(apps, schema_editor):
    """Horario de oficina por defecto: lunes a viernes 8:00-17:00 con 1 h de almuerzo y sábado 8:00-12:00 (44 h)."""
    Horario = apps.get_model('asistencia', 'Horario')
    if not Horario.objects.exists():
        Horario.objects.create(nombre='Oficina (L-V 8-5, sáb 8-12)', dias=OFICINA, almuerzo_minutos=60,
                               tolerancia_minutos=10, por_defecto=True)


class Migration(migrations.Migration):
    dependencies = [('asistencia', '0001_initial')]
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
