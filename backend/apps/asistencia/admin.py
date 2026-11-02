from django.contrib import admin

from .models import AsignacionHorario, Ausencia, Feriado, Horario, Marcaje

admin.site.register(Horario)
admin.site.register(AsignacionHorario)
admin.site.register(Feriado)


@admin.register(Marcaje)
class MarcajeAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'momento', 'origen', 'corregido_por')
    list_filter = ('tipo', 'origen')


@admin.register(Ausencia)
class AusenciaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'desde', 'hasta', 'estado')
    list_filter = ('estado', 'tipo')
