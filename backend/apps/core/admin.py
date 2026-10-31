from django.contrib import admin
from .models import AccesoEquipo, Departamento

admin.site.register(Departamento)


@admin.register(AccesoEquipo)
class AccesoEquipoAdmin(admin.ModelAdmin):
    """Solo informativo: la clave se cambia desde «Mi cuenta» o con `manage.py clave_equipo`."""
    readonly_fields = ('clave', 'fecha_modificacion')
