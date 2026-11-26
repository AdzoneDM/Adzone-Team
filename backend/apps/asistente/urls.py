from django.urls import path

from . import views

urlpatterns = [
    path('estado/', views.estado_view),
    path('conversaciones/', views.conversaciones_view),
    path('conversaciones/<int:pk>/', views.conversacion_view),
    path('preguntar/', views.preguntar_view),
    path('informe/', views.informe_view),
]
