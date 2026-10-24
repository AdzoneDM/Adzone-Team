from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'puestos-trabajo', views.PuestoDeTrabajoViewSet, basename='puestotrabajo')
router.register(r'usuarios', views.UserViewSet, basename='usuario')

urlpatterns = [
    path('', include(router.urls)),
    path('organigrama/', views.organigrama_view, name='organigrama'),
]
