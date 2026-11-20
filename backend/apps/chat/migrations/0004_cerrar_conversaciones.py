import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    dependencies = [('chat', '0003_sala_global')]

    operations = [
        migrations.AlterField(model_name='mensaje', name='conversacion',
                              field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mensajes', to='chat.conversacion')),
        migrations.AlterField(model_name='lectura', name='conversacion',
                              field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lecturas', to='chat.conversacion')),
        migrations.AddIndex(model_name='mensaje', index=models.Index(fields=['conversacion', 'id'], name='chat_mensaj_convers_6ed025_idx')),
        migrations.AddConstraint(model_name='lectura', constraint=models.UniqueConstraint(fields=('usuario', 'conversacion'), name='chat_lectura_unica')),
        migrations.AddConstraint(model_name='conversacion', constraint=models.UniqueConstraint(fields=('a', 'b'), name='chat_par_unico')),
        migrations.AddConstraint(model_name='conversacion', constraint=models.CheckConstraint(condition=Q(tipo='GLOBAL') | Q(a__isnull=False, b__isnull=False, a__lt=F('b')), name='chat_par_ordenado')),
    ]
