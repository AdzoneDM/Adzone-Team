from django.apps import AppConfig


class OrganizacionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.organizacion'
    label = 'organizacion'  # se mantiene: las tablas de la base de datos no cambian de nombre
    verbose_name = 'Organización'

    def ready(self):
        from . import signals  # noqa: F401  crea el perfil de cada usuario nuevo
