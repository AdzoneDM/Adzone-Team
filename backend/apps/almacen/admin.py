from django.contrib import admin

from .models import LineaVale, Material, MovimientoInventario, ValeMaterial


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'unidad', 'existencia', 'punto_reposicion', 'costo_unitario', 'activo')
    search_fields = ('codigo', 'nombre')


class LineaInline(admin.TabularInline):
    model = LineaVale
    extra = 0


@admin.register(ValeMaterial)
class ValeAdmin(admin.ModelAdmin):
    list_display = ('numero', 'orden', 'oa', 'estado', 'fecha')
    list_filter = ('estado',)
    inlines = [LineaInline]


@admin.register(MovimientoInventario)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'material', 'tipo', 'cantidad', 'vale', 'usuario')
    list_filter = ('tipo',)
