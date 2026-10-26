from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'reglas', views.ReglaViewSet, basename='regla')

urlpatterns = [
    path('', include(router.urls)),
    path('catalogo/', views.catalogo_view, name='automatizaciones_catalogo'),
    path('ejecuciones/', views.ejecuciones_view, name='automatizaciones_ejecuciones'),
]
