from django.urls import path

from . import views

urlpatterns = [
    path('', views.casos_view),
    path('opciones/', views.opciones_view),
    path('<int:pk>/', views.caso_view),
    path('<int:pk>/accion/', views.accion_view),
    path('<int:pk>/evidencias/<int:eid>/', views.evidencia_view),
]
