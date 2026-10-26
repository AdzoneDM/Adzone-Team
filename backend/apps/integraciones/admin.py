from django.contrib import admin

from .models import SincronizacionCashflow


@admin.register(SincronizacionCashflow)
class SincronizacionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'operacion', 'objeto', 'exito', 'modo', 'usuario')
    list_filter = ('exito', 'modo', 'operacion')
    readonly_fields = [f.name for f in SincronizacionCashflow._meta.fields]
