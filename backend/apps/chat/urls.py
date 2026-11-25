from django.urls import path

from . import views

urlpatterns = [
    path('conversaciones/', views.conversaciones_view),
    path('conversaciones/<int:pk>/mensajes/', views.mensajes_view),
    path('conversaciones/<int:pk>/leido/', views.leido_view),
    path('mensajes/<int:pk>/', views.mensaje_view),
    path('mensajes/<int:pk>/archivo/', views.archivo_view),
    path('mensajes/<int:pk>/vistos/', views.vistos_view),
    path('mensajes/<int:pk>/abierto/', views.abierto_view),
    path('grupos/', views.grupos_view),
    path('grupos/<int:pk>/', views.grupo_view),
    path('personas/', views.personas_view),
    path('resumen/', views.resumen_view),
]
