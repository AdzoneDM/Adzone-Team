from django.db import migrations
from django.db.models import Max


def crear_sala(apps, schema_editor):
    Conversacion, Mensaje, Lectura = (apps.get_model('chat', n) for n in ('Conversacion', 'Mensaje', 'Lectura'))
    sala = Conversacion.objects.create(tipo='GLOBAL')
    Mensaje.objects.filter(conversacion__isnull=True).update(conversacion=sala)
    Lectura.objects.filter(conversacion__isnull=True).update(conversacion=sala)
    ultimo = Mensaje.objects.filter(conversacion=sala, eliminado=False).order_by('-id').first()
    if ultimo:
        sala.ultimo_id, sala.ultimo_texto, sala.ultimo_autor_id, sala.ultima_actividad = ultimo.id, ultimo.texto[:140], ultimo.autor_id, ultimo.creado
        sala.save()


class Migration(migrations.Migration):
    dependencies = [('chat', '0002_conversaciones')]
    operations = [migrations.RunPython(crear_sala, migrations.RunPython.noop)]
