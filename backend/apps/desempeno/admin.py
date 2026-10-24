from django.contrib import admin
from .models import Tarea, ResultadoKPI, EmpleadoDelMes


@admin.register(Tarea)
class TareaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'colaborador', 'prioridad', 'estado', 'fecha_limite', 'fecha_completada', 'calificacion_calidad')
    list_filter = ('estado', 'prioridad', 'colaborador')
    search_fields = ('titulo', 'descripcion', 'colaborador__username')
    date_hierarchy = 'fecha_limite'


@admin.register(ResultadoKPI)
class ResultadoKPIAdmin(admin.ModelAdmin):
    list_display = ('kpi_asignado', 'colaborador', 'periodo', 'valor_meta', 'valor_real')
    list_filter = ('periodo', 'colaborador')


@admin.register(EmpleadoDelMes)
class EmpleadoDelMesAdmin(admin.ModelAdmin):
    list_display = ('periodo', 'colaborador', 'departamento', 'puntaje', 'beneficio')
    list_filter = ('periodo', 'departamento')


from .models import ConfiguracionDesempeno, EvidenciaArchivo, HistorialTarea, Notificacion, PasoTarea, TareaRecurrente  # noqa: E402


class EvidenciaInline(admin.TabularInline):
    model = EvidenciaArchivo
    extra = 0
    readonly_fields = ('nombre_original', 'tipo', 'tamano', 'ronda', 'subido_por', 'fecha')


class HistorialInline(admin.TabularInline):
    model = HistorialTarea
    extra = 0
    readonly_fields = ('accion', 'usuario', 'comentario', 'fecha')
    can_delete = False


class PasoInline(admin.TabularInline):
    model = PasoTarea
    extra = 0
    fields = ('orden', 'texto', 'hecho', 'hecho_por', 'fecha_hecho')
    readonly_fields = ('hecho_por', 'fecha_hecho')


TareaAdmin.inlines = [PasoInline, EvidenciaInline, HistorialInline]
TareaAdmin.filter_horizontal = ('companeros',)


@admin.register(TareaRecurrente)
class TareaRecurrenteAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'colaborador', 'frecuencia', 'dia_semana', 'dia_mes', 'activa', 'generada_hasta')
    list_filter = ('frecuencia', 'activa')


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('destinatario', 'tipo', 'titulo', 'leida', 'fecha')
    list_filter = ('tipo', 'leida')


@admin.register(ConfiguracionDesempeno)
class ConfiguracionAdmin(admin.ModelAdmin):
    list_display = ('peso_tareas', 'nota_tarde', 'minimo_tareas_empleado_mes', 'fecha_modificacion')
