from django.contrib import admin
from .models import Ruta, Paradero, Bus, UbicacionBus, Horario

# Registra tus modelos aquí
admin.site.register(Ruta)
admin.site.register(Paradero)
admin.site.register(Bus)
admin.site.register(UbicacionBus)
admin.site.register(Horario)