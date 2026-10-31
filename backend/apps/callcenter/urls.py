from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'campanas', views.CampanaViewSet, basename='campana')

urlpatterns = [
    path('resumen/', views.resumen_view, name='callcenter_resumen'),
    path('', include(router.urls)),
]
