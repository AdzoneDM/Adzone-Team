from django.contrib import admin

from .models import Ejecucion, Regla


@admin.register(Regla)
class ReglaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'evento', 'accion', 'activa', 'veces', 'ultima_vez')
    list_filter = ('evento', 'accion', 'activa')


@admin.register(Ejecucion)
class EjecucionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'regla', 'objeto', 'resultado', 'exito')
    list_filter = ('exito',)
