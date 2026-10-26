from django.contrib import admin

from .models import ArchivoOrden, Cliente, Comentario, EventoOrden, OrdenTrabajo, Proyecto


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


@admin.register(OrdenTrabajo)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ('numero', 'tipo', 'titulo', 'cliente', 'departamento', 'responsable', 'estado', 'fecha_compromiso')
    list_filter = ('tipo', 'estado', 'departamento', 'prioridad')
    search_fields = ('numero', 'titulo', 'cliente__nombre')
    filter_horizontal = ('equipo',)
    inlines = [ArchivoInline, EventoInline]


admin.site.register(Comentario)
