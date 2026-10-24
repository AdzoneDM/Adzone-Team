from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views # Importa PlantillaKPIViewSet y KPIAsignadoViewSet

router = DefaultRouter()
router.register(r'plantillas-kpi', views.PlantillaKPIViewSet, basename='plantillakpi')
router.register(r'kpis-asignados', views.KPIAsignadoViewSet, basename='kpiasignado')

urlpatterns = [
    path('', include(router.urls)),
]
