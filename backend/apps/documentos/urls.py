from django.urls import path

from . import views

urlpatterns = [
    path('', views.documentos_view),
    path('resumen/', views.resumen_view),
    path('<int:pk>/', views.documento_view),
    path('<int:pk>/archivo/', views.archivo_view),
]
