from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'cotizaciones', views.CotizacionViewSet, basename='cotizacion')
router.register(r'facturas', views.FacturaViewSet, basename='factura')
router.register(r'gastos', views.GastoViewSet, basename='gasto')

urlpatterns = [
    path('', include(router.urls)),
    path('pagos/<int:pk>/', views.borrar_pago_view, name='borrar_pago'),
    path('resumen/', views.resumen_view, name='finanzas_resumen'),
    path('rentabilidad/', views.rentabilidad_view, name='finanzas_rentabilidad'),
]
