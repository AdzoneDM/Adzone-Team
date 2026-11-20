from django.contrib import admin

from .models import Conversacion, Lectura, Mensaje

admin.site.register(Conversacion)
admin.site.register(Mensaje)
admin.site.register(Lectura)
