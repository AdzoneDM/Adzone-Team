from django.apps import AppConfig


class KpisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.kpis'
    label = 'kpis'  # se mantiene: las tablas de la base de datos no cambian de nombre
    verbose_name = 'KPIs'
