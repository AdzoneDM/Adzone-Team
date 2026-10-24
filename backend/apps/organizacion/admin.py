from django.contrib import admin
from .models import PuestoDeTrabajo, PerfilUsuario

@admin.register(PuestoDeTrabajo)
class PuestoDeTrabajoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'departamento', 'supervisor', 'fecha_creacion') # Añadido 'supervisor'
    list_filter = ('departamento', 'supervisor') # Añadido 'supervisor'
    search_fields = ('nombre', 'departamento__nombre', 'supervisor__nombre') # Añadido 'supervisor__nombre'
    list_per_page = 25
    raw_id_fields = ('departamento', 'supervisor') # Añadido 'supervisor'

# ... (PerfilUsuarioAdmin se mantiene igual) ...
@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'puesto_trabajo', 'fecha_creacion_perfil')
    list_filter = ('puesto_trabajo', 'puesto_trabajo__departamento')
    search_fields = ('user__username', 'user__email', 'puesto_trabajo__nombre')
    list_per_page = 25
    raw_id_fields = ('user', 'puesto_trabajo')