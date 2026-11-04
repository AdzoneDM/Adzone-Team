from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'marcajes', views.MarcajeViewSet, basename='marcaje')
router.register(r'horarios', views.HorarioViewSet, basename='horario')
router.register(r'feriados', views.FeriadoViewSet, basename='feriado')
router.register(r'sitios', views.SitioViewSet, basename='sitio')
router.register(r'ausencias', views.AusenciaViewSet, basename='ausencia')

urlpatterns = [
    path('', include(router.urls)),
    path('estado/', views.estado_view),
    path('marcar/', views.marcar_view),
    path('sitios/<int:pk>/nueva-clave/', views.sitio_nueva_clave_view),
    path('pantalla/<str:clave>/', views.pantalla_qr_view),
    path('mes/', views.mi_mes_view),
    path('hoy/', views.hoy_view),
    path('reporte/', views.reporte_view),
    path('asignaciones/', views.asignaciones_view),
    path('ausencias/<int:pk>/revisar/', views.revisar_ausencia_view),
]
