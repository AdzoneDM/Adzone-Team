"""Crea los perfiles de acceso con sus permisos y asigna los iniciales según el organigrama de hoy."""
from django.db import migrations


def sembrar(apps, schema_editor):
    from apps.core.permisos import PERFILES
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    Permisos = apps.get_model('core', 'PermisosDePerfil')
    Puesto = apps.get_model('organizacion', 'PuestoDeTrabajo')
    grupos = {}
    for nombre, (desc, lista, orden) in PERFILES.items():
        g, _ = Group.objects.get_or_create(name=nombre)
        Permisos.objects.get_or_create(grupo=g, defaults={'descripcion': desc, 'permisos': list(lista), 'orden': orden})
        grupos[nombre] = g
    hijos = {}
    for pid, sup in Puesto.objects.values_list('id', 'supervisor_id'):
        hijos.setdefault(sup, []).append(pid)

    def debajo(pid):
        vistos, pend = set(), list(hijos.get(pid, []))
        while pend:
            x = pend.pop()
            if x not in vistos:
                vistos.add(x)
                pend.extend(hijos.get(x, []))
        return vistos

    for u in User.objects.filter(is_active=True).select_related('perfil__puesto_trabajo__departamento', 'perfil__puesto_trabajo__supervisor'):
        nombres = set(u.groups.values_list('name', flat=True))
        if u.is_staff and 'Administrador' not in nombres:
            u.groups.add(grupos['Administrador'])  # antes el staff era administrador: no se le quita acceso sin revisarlo
            nombres.add('Administrador')
        if 'RRHH' in nombres:
            u.groups.add(grupos['Gestión del Talento'])  # el grupo «RRHH» de v10 pasa al perfil nuevo
        puesto = getattr(getattr(u, 'perfil', None), 'puesto_trabajo', None)
        if puesto is None:
            if not u.groups.exists():
                u.groups.add(grupos['Colaborador'])
            continue
        gente_debajo = User.objects.filter(is_active=True, perfil__puesto_trabajo__in=debajo(puesto.pk)).exclude(pk=u.pk).exists()
        if gente_debajo and not nombres & {'Administrador', 'Gerente de Departamento', 'Supervisor'}:
            u.groups.add(grupos['Supervisor'])
        depto = (puesto.departamento.nombre if puesto.departamento_id else '').lower()
        jefe_de_area = puesto.supervisor_id is None or puesto.supervisor.departamento_id != puesto.departamento_id
        if 'tecnolog' in depto and jefe_de_area:
            u.groups.add(grupos['Tecnología'])
        if 'talento' in depto or 'recursos humanos' in depto:
            u.groups.add(grupos['Gestión del Talento'])
        if not u.groups.exists():
            u.groups.add(grupos['Colaborador'])
        elif u.groups.exclude(name='Colaborador').filter(permisos_acceso__isnull=False).exists():
            u.groups.remove(grupos['Colaborador'])


class Migration(migrations.Migration):
    dependencies = [('core', '0004_perfiles_de_acceso'), ('organizacion', '0005_descripcion_oficial_y_salario'), ('auth', '0012_alter_user_first_name_max_length')]
    operations = [migrations.RunPython(sembrar, migrations.RunPython.noop)]
