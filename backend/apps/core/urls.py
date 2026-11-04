from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views, views_accesos as acc, views_dos_pasos as dp, views_respaldos as resp, views_push

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
    path('auth/dos-pasos/', views.dos_pasos_login_view, name='api_dos_pasos_login'),
    path('respaldos/', resp.respaldos_view, name='respaldos'),
    path('cuenta/push/', views_push.push_view, name='push'),
    path('respaldos/<str:nombre>/', resp.descargar_view, name='respaldo_descargar'),
    path('cuenta/dos-pasos/', dp.estado_view, name='dos_pasos_estado'),
    path('cuenta/dos-pasos/iniciar/', dp.iniciar_view, name='dos_pasos_iniciar'),
    path('cuenta/dos-pasos/confirmar/', dp.confirmar_view, name='dos_pasos_confirmar'),
    path('cuenta/dos-pasos/respaldo/', dp.respaldo_view, name='dos_pasos_respaldo'),
    path('cuenta/dos-pasos/desactivar/', dp.desactivar_view, name='dos_pasos_desactivar'),
    path('accesos/personas/<int:pk>/dos-pasos/', acc.reiniciar_dos_pasos_view, name='accesos_reiniciar_dos_pasos'),
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
