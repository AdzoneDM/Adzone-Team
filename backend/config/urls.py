"""URLs de Adzone Team: la API bajo /api/ y, en producción, la app web en todo lo demás."""
from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponseNotFound
from django.urls import include, path, re_path
from django.views.decorators.cache import never_cache


@never_cache
def app_web(request, *args, **kwargs):
    """Devuelve index.html de la app compilada para cualquier ruta que no sea de la API."""
    indice = settings.FRONTEND_DIST / 'index.html'
    if not indice.exists():
        return HttpResponseNotFound("La app web no está compilada. Ejecuta «npm run build» en frontend/.")
    return FileResponse(open(indice, 'rb'), content_type='text/html; charset=utf-8')


admin.site.site_header = "Adzone Team · Administración avanzada"
admin.site.site_title = "Adzone Team"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.core.urls')),
    path('api/organizacion/', include('apps.organizacion.urls')),
    path('api/kpis/', include('apps.kpis.urls')),
    path('api/desempeno/', include('apps.desempeno.urls')),
    path('api/operaciones/', include('apps.operaciones.urls')),
    path('api/tiempo/', include('apps.tiempo.urls')),
    path('api/finanzas/', include('apps.finanzas.urls')),
    path('api/automatizaciones/', include('apps.automatizaciones.urls')),
    # Todo lo demás es la app web (React). Los archivos (JS, CSS, íconos) los sirve WhiteNoise.
    re_path(r'^(?!api/|admin/|static/).*$', app_web),
]
