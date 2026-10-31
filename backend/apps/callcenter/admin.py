from django.contrib import admin

from .models import Campana


@admin.register(Campana)
class CampanaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cliente', 'tipo', 'activa', 'fecha_inicio', 'fecha_fin')
    list_filter = ('activa', 'tipo')
    filter_horizontal = ('agentes',)
