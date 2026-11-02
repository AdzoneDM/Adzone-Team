from django.contrib import admin

from .models import Actividad, AlertaEnviada, Captura, ConfiguracionMonitoreo, Consentimiento, Dispositivo, ReglaProductividad

admin.site.register(ConfiguracionMonitoreo)
admin.site.register(Consentimiento)
admin.site.register(AlertaEnviada)


@admin.register(Dispositivo)
class DispositivoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'nombre', 'activo', 'ultimo_contacto', 'version_agente')
    exclude = ('token_hash',)


@admin.register(ReglaProductividad)
class ReglaAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'patron', 'categoria', 'departamento')
    list_filter = ('categoria', 'tipo', 'departamento')


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'minuto', 'app', 'categoria', 'activos')
    list_filter = ('categoria',)


@admin.register(Captura)
class CapturaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tomada_en', 'app')
