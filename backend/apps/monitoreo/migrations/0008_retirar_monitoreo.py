# Retira el módulo de monitoreo: borra sus tablas (la actividad, las capturas, las computadoras y sus reglas).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('activos', '0002_sin_computadora_vinculada'),
        ('core', '0012_alerta_enviada_y_sin_permisos_de_monitoreo'),  # copia los avisos enviados antes de borrar la tabla
        ('monitoreo', '0007_ficha_computadora'),
    ]

    operations = [
        migrations.DeleteModel(name='Incidencia'),
        migrations.DeleteModel(name='IPDispositivo'),
        migrations.DeleteModel(name='Justificacion'),
        migrations.DeleteModel(name='Captura'),
        migrations.DeleteModel(name='Actividad'),
        migrations.DeleteModel(name='Consentimiento'),
        migrations.DeleteModel(name='AlertaEnviada'),
        migrations.DeleteModel(name='PerfilMonitoreo'),
        migrations.DeleteModel(name='ReglaComportamiento'),
        migrations.DeleteModel(name='ReglaProductividad'),
        migrations.DeleteModel(name='Dispositivo'),
        migrations.DeleteModel(name='ConfiguracionMonitoreo'),
    ]
