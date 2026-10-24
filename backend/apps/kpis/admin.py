from django.contrib import admin
from .models import PlantillaKPI, KPIAsignado # Importa KPIAsignado

@admin.register(PlantillaKPI)
class PlantillaKPIAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'unidad_medida', 'fecha_creacion', 'fecha_modificacion')
    search_fields = ('nombre', 'descripcion', 'unidad_medida')
    list_filter = ('unidad_medida',)
    list_per_page = 25

@admin.register(KPIAsignado)
class KPIAsignadoAdmin(admin.ModelAdmin):
    list_display = (
        'get_plantilla_kpi_nombre', 
        'get_puesto_trabajo_nombre', 
        'ponderacion', 
        'objetivo_meta', 
        'periodicidad_objetivo', 
        'es_entrada_manual',
        'activo'
    )
    list_filter = ('puesto_trabajo__departamento', 'puesto_trabajo', 'plantilla_kpi', 'periodicidad_objetivo', 'es_entrada_manual', 'activo')
    search_fields = ('plantilla_kpi__nombre', 'puesto_trabajo__nombre', 'puesto_trabajo__departamento__nombre')
    list_editable = ('ponderacion', 'objetivo_meta', 'periodicidad_objetivo', 'es_entrada_manual', 'activo') # Campos editables en la lista
    list_per_page = 25
    raw_id_fields = ('puesto_trabajo', 'plantilla_kpi') # Útil para ForeignKeys con muchos elementos

    # Funciones para mostrar nombres en list_display en lugar de IDs o el __str__ del modelo relacionado
    def get_plantilla_kpi_nombre(self, obj):
        return obj.plantilla_kpi.nombre
    get_plantilla_kpi_nombre.short_description = 'Plantilla KPI' # Nombre de la columna
    get_plantilla_kpi_nombre.admin_order_field = 'plantilla_kpi__nombre' # Permite ordenar por este campo

    def get_puesto_trabajo_nombre(self, obj):
        return obj.puesto_trabajo.nombre
    get_puesto_trabajo_nombre.short_description = 'Puesto de Trabajo'
    get_puesto_trabajo_nombre.admin_order_field = 'puesto_trabajo__nombre'