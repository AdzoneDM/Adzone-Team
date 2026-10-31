from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'departamentos', views.DepartamentoViewSet, basename='departamento')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', views.login_view, name='api_login'),
    path('auth/logout/', views.logout_view, name='api_logout'),
    path('auth/session/', views.session_view, name='api_session_status'),
    path('auth/cambiar-clave/', views.cambiar_clave_view, name='api_cambiar_clave'),
    path('auth/equipo/', views.equipo_view, name='api_equipo'),
    path('auth/directorio/', views.directorio_view, name='api_directorio'),
    path('auth/clave-equipo/', views.clave_equipo_view, name='api_clave_equipo'),
]
