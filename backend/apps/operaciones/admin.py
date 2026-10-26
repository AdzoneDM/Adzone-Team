from django.contrib import admin

from .models import (
    Acta, ArchivoOrden, AreaConfig, Cliente, Comentario, EventoOrden, Firma, Incidencia, OrdenArea, OrdenTrabajo, Proyecto,
    SolicitudCambio, TiempoEstandar, Traspaso,
)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'contacto', 'telefono', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('nombre', 'rnc', 'contacto')


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'cliente', 'departamento', 'responsable', 'estado', 'fecha_fin')
    list_filter = ('estado', 'departamento')
    search_fields = ('codigo', 'nombre', 'cliente__nombre')
    filter_horizontal = ('miembros',)


class EventoInline(admin.TabularInline):
    model = EventoOrden
    extra = 0
    readonly_fields = ('fecha', 'usuario', 'texto', 'detalle')


class ArchivoInline(admin.TabularInline):
    model = ArchivoOrden
    extra = 0
    readonly_fields = ('nombre_original', 'tipo', 'tamano', 'subido_por', 'fecha')
    exclude = ('archivo',)


class AreaInline(admin.TabularInline):
    model = OrdenArea
    extra = 0
    fields = ('numero', 'area', 'secuencia', 'que_produce', 'responsable', 'estado', 'fecha_entrega_interna')
    readonly_fields = ('numero',)


@admin.register(OrdenTrabajo)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ('solicitud', 'numero', 'titulo', 'cliente', 'prioridad', 'estado', 'fecha_compromiso')
    list_filter = ('estado', 'prioridad', 'tipo_cliente')
    search_fields = ('numero', 'solicitud', 'titulo', 'cliente__nombre')
    filter_horizontal = ('equipo',)
    inlines = [AreaInline, ArchivoInline, EventoInline]


@admin.register(OrdenArea)
class OrdenAreaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'area', 'que_produce', 'responsable', 'estado', 'fecha_entrega_interna')
    list_filter = ('area', 'estado')
    search_fields = ('numero', 'que_produce', 'orden__titulo')


@admin.register(AreaConfig)
class AreaConfigAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'departamento', 'activa')
    filter_horizontal = ('supervisores',)


@admin.register(Traspaso)
class TraspasoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'orden', 'oa', 'compuerta', 'entrega_area', 'recibe_area', 'resultado', 'entrega_fecha')
    list_filter = ('compuerta', 'resultado')


@admin.register(Acta)
class ActaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'orden', 'modalidad', 'fecha', 'conformidad', 'firmada')


@admin.register(SolicitudCambio)
class CambioAdmin(admin.ModelAdmin):
    list_display = ('numero', 'orden', 'tipo', 'estado', 'costo_retrabajo', 'monto_cliente', 'fecha')
    list_filter = ('tipo', 'estado')


admin.site.register(TiempoEstandar)
admin.site.register(Incidencia)
admin.site.register(Firma)


admin.site.register(Comentario)
