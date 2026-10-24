from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    label = 'core'  # se mantiene: las tablas de la base de datos no cambian de nombre
    verbose_name = 'Departamentos y sesión'
