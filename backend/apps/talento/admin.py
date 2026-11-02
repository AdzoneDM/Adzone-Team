from django.contrib import admin

from .models import AuditoriaCambio, CambioSalarial, CicloEvaluacion, EventoExpediente, Evaluacion, PlanMejora

for m in (CicloEvaluacion, Evaluacion, PlanMejora, EventoExpediente, CambioSalarial):
    admin.site.register(m)


@admin.register(AuditoriaCambio)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'usuario', 'accion', 'objeto')
    search_fields = ('accion', 'objeto')

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
