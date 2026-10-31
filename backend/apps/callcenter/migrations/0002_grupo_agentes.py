from django.db import migrations


def crear_grupo(apps, schema_editor):
    """Crea el acceso «Agente Call Center» y se lo da a quien ya ocupa un puesto de agente."""
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    grupo, _ = Group.objects.get_or_create(name='Agente Call Center')
    for u in User.objects.filter(perfil__puesto_trabajo__nombre__startswith='Agente de Call Center'):
        u.groups.add(grupo)


class Migration(migrations.Migration):
    dependencies = [
        ('callcenter', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('organizacion', '0004_perfilusuario_costo_hora_perfilusuario_horas_semana'),
    ]
    operations = [migrations.RunPython(crear_grupo, migrations.RunPython.noop)]
