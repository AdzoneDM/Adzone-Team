from django.contrib import admin

from .models import RegistroTiempo


@admin.register(RegistroTiempo)
class RegistroAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'inicio', 'minutos', 'tarea', 'orden', 'proyecto', 'facturable')
    list_filter = ('facturable',)
    search_fields = ('usuario__username', 'descripcion')
