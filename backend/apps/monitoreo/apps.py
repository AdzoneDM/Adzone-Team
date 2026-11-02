from django.apps import AppConfig


class MonitoreoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.monitoreo'
    verbose_name = 'Monitoreo de actividad'

    def ready(self):
        from django.db.models.signals import post_save

        def _atribuir(sender, instance, raw=False, **kwargs):
            if not raw:
                from .servicios import atribuir_registro
                atribuir_registro(instance)

        post_save.connect(_atribuir, sender='tiempo.RegistroTiempo', dispatch_uid='monitoreo-atribuir-registro')
