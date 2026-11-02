from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'ciclos', views.CicloViewSet, basename='ciclo')
router.register(r'planes', views.PlanViewSet, basename='plan')
router.register(r'expediente', views.ExpedienteViewSet, basename='expediente')

urlpatterns = [
    path('', include(router.urls)),
    path('evaluaciones/', views.mis_evaluaciones_view),
    path('evaluaciones/<int:pk>/enviar/', views.enviar_evaluacion_view),
    path('evaluaciones/por-revisar/', views.por_revisar_view),
    path('evaluaciones/<int:pk>/confirmar/', views.confirmar_evaluacion_view),
    path('resultados/', views.resultados_view),
    path('avance/', views.avance_view),
    path('salarios/', views.salarios_view),
    path('auditoria/', views.auditoria_view),
]
