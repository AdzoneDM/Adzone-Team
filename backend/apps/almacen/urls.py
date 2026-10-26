from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'materiales', views.MaterialViewSet, basename='material')
router.register(r'vales', views.ValeViewSet, basename='vale')
router.register(r'movimientos', views.MovimientoViewSet, basename='movimiento')

urlpatterns = [path('', include(router.urls))]
