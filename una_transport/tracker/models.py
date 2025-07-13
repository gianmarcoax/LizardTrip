from django.db import models
from django.contrib.auth.models import User

class Ruta(models.Model):
    nombre = models.CharField(max_length=100)
    origen = models.CharField(max_length=200)
    destino = models.CharField(max_length=200)
    color = models.CharField(max_length=7, default='#FF0000')  # Color hex
    activa = models.BooleanField(default=True)
    
    def __str__(self):
        return self.nombre

class Paradero(models.Model):
    nombre = models.CharField(max_length=100)
    latitud = models.DecimalField(max_digits=10, decimal_places=8)
    longitud = models.DecimalField(max_digits=11, decimal_places=8)
    ruta = models.ForeignKey(Ruta, on_delete=models.CASCADE)
    orden = models.IntegerField()
    # NUEVO CAMPO: orientacion
    ORIENTACION_CHOICES = [
        ('ida', 'Ida'),
        ('vuelta', 'Vuelta'),
    ]
    orientacion = models.CharField(
        max_length=10,
        choices=ORIENTACION_CHOICES,
        default='ida', # Puedes elegir un valor por defecto
        help_text="Indica si el paradero es para la ruta de ida o de vuelta."
    )
    
    class Meta:
        ordering = ['orden']
    
    def __str__(self):
        # Actualizado para incluir la orientación
        return f"{self.nombre} - {self.ruta.nombre} ({self.get_orientacion_display()})"

class Bus(models.Model):
    # CAMBIO: Renombrado de 'placa' a 'nombre' y aumento de max_length
    nombre = models.CharField(max_length=30, unique=True) # Antes era 'placa' con max_length=10
    conductor = models.ForeignKey(User, on_delete=models.CASCADE)
    ruta_actual = models.ForeignKey(Ruta, on_delete=models.SET_NULL, null=True, blank=True)
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        # Actualizado para usar 'nombre' en lugar de 'placa'
        return f"Bus {self.nombre}"

class UbicacionBus(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE)
    latitud = models.DecimalField(max_digits=10, decimal_places=8)
    longitud = models.DecimalField(max_digits=11, decimal_places=8)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']

class Horario(models.Model):
    ruta = models.ForeignKey(Ruta, on_delete=models.CASCADE)
    hora_salida = models.TimeField()
    tipo = models.CharField(max_length=20, choices=[
        ('mañana', 'Mañana'),
        ('mediodia', 'Mediodía'),
        ('tarde', 'Tarde'),
    ])
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.ruta.nombre} - {self.hora_salida}"

# Create your models here.