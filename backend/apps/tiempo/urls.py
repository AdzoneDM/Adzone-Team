from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'registros', views.RegistroViewSet, basename='registro')

urlpatterns = [
    path('', include(router.urls)),
    path('activo/', views.activo_view, name='tiempo_activo'),
    path('iniciar/', views.iniciar_view, name='tiempo_iniciar'),
    path('detener/', views.detener_view, name='tiempo_detener'),
    path('semana/', views.semana_view, name='tiempo_semana'),
    path('equipo/', views.equipo_view, name='tiempo_equipo'),
    path('reporte/', views.reporte_view, name='tiempo_reporte'),
]
