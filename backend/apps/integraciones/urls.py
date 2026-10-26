from django.urls import path

from . import views

urlpatterns = [
    path('cashflow/', views.estado_view, name='cashflow_estado'),
    path('cashflow/probar/', views.probar_view, name='cashflow_probar'),
    path('cashflow/sincronizar/', views.sincronizar_view, name='cashflow_sincronizar'),
    path('cashflow/clientes/<int:pk>/', views.cliente_view, name='cashflow_cliente'),
]
