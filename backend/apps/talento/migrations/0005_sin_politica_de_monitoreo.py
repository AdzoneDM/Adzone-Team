from django.db import migrations


def desactivar(apps, schema_editor):
    """La política de monitoreo ya no aplica (el módulo se retiró): queda en el historial, pero inactiva y sin pedir aceptación."""
    Politica = apps.get_model('talento', 'Politica')
    Politica.objects.filter(categoria='MONITOREO').update(activa=False, requiere_aceptacion=False)


class Migration(migrations.Migration):
    dependencies = [('talento', '0004_codigo_y_responsable_de_politica')]
    operations = [migrations.RunPython(desactivar, migrations.RunPython.noop)]
