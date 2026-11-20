import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('chat', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name='Conversacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('GLOBAL', 'Sala de toda la empresa'), ('DIRECTA', 'Chat privado')], default='DIRECTA', max_length=7)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('ultimo_id', models.BigIntegerField(default=0)),
                ('ultimo_texto', models.CharField(blank=True, max_length=140)),
                ('ultima_actividad', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('a', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('b', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('ultimo_autor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Conversación', 'verbose_name_plural': 'Conversaciones'},
        ),
        # Nulos por ahora: la migración siguiente los llena con la sala global.
        migrations.AddField(model_name='mensaje', name='conversacion',
                            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='mensajes', to='chat.conversacion')),
        migrations.AlterField(model_name='lectura', name='usuario',
                              field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lecturas_chat', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='lectura', name='conversacion',
                            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='lecturas', to='chat.conversacion')),
    ]
