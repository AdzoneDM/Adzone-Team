from django.contrib import admin

from .models import Cotizacion, Factura, Gasto, LineaCotizacion, LineaFactura, Pago


class LineaCotizacionInline(admin.TabularInline):
    model = LineaCotizacion
    extra = 0


class LineaFacturaInline(admin.TabularInline):
    model = LineaFactura
    extra = 0


class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ('numero', 'cliente', 'titulo', 'fecha', 'total', 'estado')
    list_filter = ('estado',)
    search_fields = ('numero', 'cliente__nombre', 'titulo')
    inlines = [LineaCotizacionInline]


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'ncf', 'cliente', 'fecha', 'vencimiento', 'total', 'pagado', 'estado')
    list_filter = ('estado',)
    search_fields = ('numero', 'ncf', 'cliente__nombre')
    inlines = [LineaFacturaInline, PagoInline]


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'concepto', 'categoria', 'monto', 'proveedor', 'proyecto')
    list_filter = ('categoria',)
    search_fields = ('concepto', 'proveedor')
