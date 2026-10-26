from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'clientes', views.ClienteViewSet, basename='cliente')
router.register(r'proyectos', views.ProyectoViewSet, basename='proyecto')
router.register(r'ordenes', views.OrdenViewSet, basename='orden')
router.register(r'areas', views.OrdenAreaViewSet, basename='orden-area')
router.register(r'traspasos', views.TraspasoViewSet, basename='traspaso')
router.register(r'actas', views.ActaViewSet, basename='acta')
router.register(r'cambios', views.CambioViewSet, basename='cambio')
router.register(r'config-areas', views.AreaConfigViewSet, basename='config-area')
router.register(r'tiempos', views.TiempoEstandarViewSet, basename='tiempo-estandar')

urlpatterns = [
    path('', include(router.urls)),
    path('archivos/<int:pk>/', views.archivo_view, name='archivo_orden'),
    path('directorio/', views.directorio_view, name='directorio'),
    path('buscar/', views.buscar_view, name='buscar'),
]
