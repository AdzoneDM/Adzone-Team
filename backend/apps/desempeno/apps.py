from django.apps import AppConfig


class DesempenoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.desempeno'
    label = 'desempeno'  # se mantiene: las tablas de la base de datos no cambian de nombre
    verbose_name = 'Tareas y desempeño'
