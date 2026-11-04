from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'ciclos', views.CicloViewSet, basename='ciclo')
router.register(r'planes', views.PlanViewSet, basename='plan')
router.register(r'expediente', views.ExpedienteViewSet, basename='expediente')
router.register(r'politicas', views.PoliticaViewSet, basename='politica')
router.register(r'documentos', views.DocumentoViewSet, basename='documento')

urlpatterns = [
    path('politicas/pendientes/', views.politicas_pendientes_view),
    path('politicas/cumplimiento/', views.cumplimiento_view),
    path('documentos/estado/', views.estado_documentos_view),
    path('', include(router.urls)),
    path('evaluaciones/', views.mis_evaluaciones_view),
    path('evaluaciones/<int:pk>/enviar/', views.enviar_evaluacion_view),
    path('evaluaciones/<int:pk>/borrador/', views.borrador_evaluacion_view),
    path('evaluaciones/por-revisar/', views.por_revisar_view),
    path('evaluaciones/<int:pk>/confirmar/', views.confirmar_evaluacion_view),
    path('resultados/', views.resultados_view),
    path('avance/', views.avance_view),
    path('salarios/', views.salarios_view),
    path('auditoria/', views.auditoria_view),
]
