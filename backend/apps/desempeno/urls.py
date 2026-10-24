from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'tareas', views.TareaViewSet, basename='tarea')
router.register(r'recurrentes', views.TareaRecurrenteViewSet, basename='recurrente')
router.register(r'resultados-kpi', views.ResultadoKPIViewSet, basename='resultadokpi')
router.register(r'empleados-del-mes', views.EmpleadoDelMesViewSet, basename='empleadodelmes')

urlpatterns = [
    path('', include(router.urls)),
    path('evidencias/<int:pk>/archivo/', views.evidencia_archivo_view, name='evidencia_archivo'),
    path('ranking/', views.ranking_view, name='ranking_desempeno'),
    path('ranking/exportar/', views.ranking_exportar_view, name='ranking_exportar'),
    path('mi-resumen/', views.mi_resumen_view, name='mi_resumen_desempeno'),
    path('tablero/', views.tablero_view, name='tablero'),
    path('equipo/', views.equipo_view, name='equipo_desempeno'),
    path('notificaciones/', views.notificaciones_view, name='notificaciones'),
    path('notificaciones/leer/', views.notificaciones_leer_view, name='notificaciones_leer'),
    path('configuracion/', views.configuracion_view, name='configuracion'),
    path('equipo/carga/', views.carga_equipo_view, name='carga_equipo'),
    path('pedir-trabajo/', views.pedir_trabajo_view, name='pedir_trabajo'),
]
