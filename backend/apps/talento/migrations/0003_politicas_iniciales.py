from django.db import migrations


def sembrar(apps, schema_editor):
    from apps.monitoreo.models import POLITICA
    from apps.talento.politicas_iniciales import NOTA, POLITICAS
    Politica = apps.get_model('talento', 'Politica')
    Version = apps.get_model('talento', 'VersionPolitica')
    for clave, titulo, cat, resumen, contenido in POLITICAS:
        texto = (contenido or POLITICA) + NOTA
        p, nueva = Politica.objects.get_or_create(clave=clave, defaults={
            'titulo': titulo, 'categoria': cat, 'resumen': resumen, 'contenido': texto, 'borrador': True})
        if nueva:
            Version.objects.create(politica=p, version=1, titulo=titulo, contenido=texto, cambio='Versión inicial')


class Migration(migrations.Migration):
    dependencies = [('talento', '0002_politicas_y_documentos')]
    operations = [migrations.RunPython(sembrar, migrations.RunPython.noop)]
