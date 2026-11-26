from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'oportunidades', views.OportunidadViewSet, basename='oportunidad')
router.register(r'solicitudes', views.SolicitudViewSet, basename='solicitud')

urlpatterns = [path('', include(router.urls))]
