from django.db import migrations


def sembrar(apps, schema_editor):
    from apps.monitoreo.comportamiento import REGLAS_INICIALES
    Regla = apps.get_model('monitoreo', 'ReglaComportamiento')
    Departamento = apps.get_model('core', 'Departamento')
    for nombre, cat, campo, patrones, minutos, riesgo, accion, desc, excluir in REGLAS_INICIALES:
        regla, nueva = Regla.objects.get_or_create(nombre=nombre, defaults={
            'categoria': cat, 'campo': campo, 'patrones': '\n'.join(patrones), 'minutos_minimos': minutos,
            'riesgo': riesgo, 'accion': accion, 'descripcion': desc})
        if nueva:
            for texto in excluir:
                regla.excluir_departamentos.add(*Departamento.objects.filter(nombre__icontains=texto))


class Migration(migrations.Migration):
    dependencies = [('monitoreo', '0005_perfiles_y_reglas'), ('core', '0001_initial')]
    operations = [migrations.RunPython(sembrar, migrations.RunPython.noop)]
