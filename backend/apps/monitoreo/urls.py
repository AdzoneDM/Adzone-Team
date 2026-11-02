from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'dispositivos', views.DispositivoViewSet, basename='dispositivo')
router.register(r'reglas', views.ReglaViewSet, basename='regla')

urlpatterns = [
    path('', include(router.urls)),
    path('agente/estado/', views.agente_estado_view),
    path('agente/actividad/', views.agente_actividad_view),
    path('agente/marcar/', views.agente_marcar_view),
    path('agente/captura/', views.agente_captura_view),
    path('politica/', views.politica_view),
    path('configuracion/', views.configuracion_view),
    path('reclasificar/', views.reclasificar_view),
    path('dia/', views.dia_view),
    path('periodo/', views.periodo_view),
    path('equipo/', views.equipo_view),
    path('capturas/<int:pk>/', views.captura_view),
]
