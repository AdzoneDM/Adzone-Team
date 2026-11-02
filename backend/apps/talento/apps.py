from django.apps import AppConfig


class TalentoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.talento'
    verbose_name = 'Gestión del talento'

    def ready(self):
        from .auditoria import conectar
        conectar()
