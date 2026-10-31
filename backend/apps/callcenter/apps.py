from django.apps import AppConfig


class CallCenterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.callcenter'
    label = 'callcenter'
    verbose_name = 'Call Center'
