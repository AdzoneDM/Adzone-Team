from django.urls import path

from . import views

urlpatterns = [
    path('mensajes/', views.mensajes_view),
    path('mensajes/<int:pk>/', views.mensaje_view),
    path('resumen/', views.resumen_view),
    path('leido/', views.leido_view),
]
