from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'', views.ActivoViewSet, basename='activo')

urlpatterns = [
    path('resumen/', views.resumen_view),
    path('', include(router.urls)),
]
