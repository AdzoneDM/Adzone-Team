from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views, views_accesos as acc

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
    path('accesos/', acc.catalogo_view, name='accesos_catalogo'),
    path('accesos/perfiles/', acc.perfil_crear_view, name='accesos_perfil_crear'),
    path('accesos/perfiles/<int:pk>/', acc.perfil_view, name='accesos_perfil'),
    path('accesos/personas/', acc.personas_view, name='accesos_personas'),
    path('accesos/personas/<int:pk>/perfiles/', acc.persona_perfiles_view, name='accesos_persona_perfiles'),
    path('accesos/excepciones/', acc.excepcion_crear_view, name='accesos_excepcion_crear'),
    path('accesos/excepciones/<int:pk>/', acc.excepcion_view, name='accesos_excepcion'),
    path('accesos/equipo-extra/', acc.equipo_extra_crear_view, name='accesos_equipo_extra_crear'),
    path('accesos/equipo-extra/<int:pk>/', acc.equipo_extra_view, name='accesos_equipo_extra'),
]
