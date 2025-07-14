from django.contrib import admin
from .models import Ruta, Paradero, Bus, UbicacionBus, Horario, SegmentoPersonalizado

# Registra tus modelos aquí
admin.site.register(Ruta)
admin.site.register(Paradero)
admin.site.register(Bus)
admin.site.register(UbicacionBus)
admin.site.register(Horario)

@admin.register(SegmentoPersonalizado)
class SegmentoPersonalizadoAdmin(admin.ModelAdmin):
    list_display = ['ruta', 'orientacion', 'tipo_segmento', 'activo']
    list_filter = ['ruta', 'orientacion', 'tipo_segmento', 'activo']
    search_fields = ['ruta__nombre']
    ordering = ['ruta', 'orientacion', 'tipo_segmento']