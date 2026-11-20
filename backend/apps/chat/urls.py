from django.urls import path

from . import views

urlpatterns = [
    path('conversaciones/', views.conversaciones_view),
    path('conversaciones/<int:pk>/mensajes/', views.mensajes_view),
    path('conversaciones/<int:pk>/leido/', views.leido_view),
    path('mensajes/<int:pk>/', views.mensaje_view),
    path('personas/', views.personas_view),
    path('resumen/', views.resumen_view),
]
