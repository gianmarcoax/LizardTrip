from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from geopy.distance import geodesic
from tracker.utils.proximo_paradero import ProximoParaderoCalculator

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
    ultima_actualizacion = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        # Actualizado para usar 'nombre' en lugar de 'placa'
        return f"Bus {self.nombre}"
    
    def esta_activo(self):
        """Verifica si el bus ha enviado ubicación en los últimos 5 minutos"""
        if not self.ultima_actualizacion:
            return False
        return timezone.now() - self.ultima_actualizacion < timedelta(minutes=5)
    
    def calcular_velocidad_actual(self, minutos_atras=2):
        """
        Calcula la velocidad actual del bus basada en las últimas ubicaciones.
        Retorna velocidad en metros por segundo.
        """
        from datetime import timedelta
        
        # Obtener ubicaciones de los últimos X minutos
        tiempo_limite = timezone.now() - timedelta(minutes=minutos_atras)
        ubicaciones = UbicacionBus.objects.filter(
            bus=self,
            timestamp__gte=tiempo_limite,
            activo=True
        ).order_by('timestamp')
        
        if ubicaciones.count() < 2:
            return None  # No hay suficientes datos
        
        # Calcular distancia total recorrida
        distancia_total = 0
        tiempo_total = 0
        
        ubicaciones_list = list(ubicaciones)
        for i in range(1, len(ubicaciones_list)):
            ubicacion_anterior = ubicaciones_list[i-1]
            ubicacion_actual = ubicaciones_list[i]
            
            # Calcular distancia entre puntos
            distancia = geodesic(
                (float(ubicacion_anterior.latitud), float(ubicacion_anterior.longitud)),
                (float(ubicacion_actual.latitud), float(ubicacion_actual.longitud))
            ).meters
            
            # Calcular tiempo entre puntos
            tiempo = (ubicacion_actual.timestamp - ubicacion_anterior.timestamp).total_seconds()
            
            # Filtrar datos anómalos (velocidades muy altas o muy bajas)
            if tiempo > 0 and distancia > 0:
                velocidad_instantanea = distancia / tiempo
                # Filtrar velocidades entre 0.5 m/s (1.8 km/h) y 20 m/s (72 km/h)
                if 0.5 <= velocidad_instantanea <= 20:
                    distancia_total += distancia
                    tiempo_total += tiempo
        
        if tiempo_total == 0:
            return None
        
        # Velocidad promedio en metros por segundo
        velocidad_mps = distancia_total / tiempo_total
        
        # Limitar velocidad máxima a 15 m/s (54 km/h) para buses urbanos
        velocidad_mps = min(velocidad_mps, 15.0)
        
        return velocidad_mps
    
    def calcular_tiempo_llegada_paradero(self, paradero, velocidad_mps=None):
        """
        Calcula el tiempo estimado de llegada a un paradero específico.
        Retorna tiempo en minutos.
        """
        if not self.ultima_actualizacion:
            return None
        
        # Obtener la última ubicación del bus
        ultima_ubicacion = UbicacionBus.objects.filter(bus=self, activo=True).order_by('-timestamp').first()
        if not ultima_ubicacion:
            return None
        
        # Calcular distancia al paradero
        distancia = geodesic(
            (float(ultima_ubicacion.latitud), float(ultima_ubicacion.longitud)),
            (float(paradero.latitud), float(paradero.longitud))
        ).meters
        
        # Usar velocidad calculada o velocidad por defecto
        if velocidad_mps is None:
            velocidad_mps = self.calcular_velocidad_actual()
        
        if velocidad_mps is None:
            # Velocidad por defecto: 25 km/h = 6.94 m/s para buses urbanos
            velocidad_mps = 6.94
        
        # Ajustar velocidad según la distancia (buses van más lento en distancias cortas)
        if distancia < 500:  # Menos de 500 metros
            velocidad_mps *= 0.7  # 30% más lento para distancias cortas
        elif distancia < 1000:  # Entre 500m y 1km
            velocidad_mps *= 0.85  # 15% más lento
        
        # Calcular tiempo en segundos
        tiempo_segundos = distancia / velocidad_mps
        
        # Agregar tiempo adicional por paradas y semáforos (aproximadamente 30 segundos por km)
        tiempo_adicional = (distancia / 1000) * 30
        tiempo_segundos += tiempo_adicional
        
        # Convertir a minutos
        tiempo_minutos = tiempo_segundos / 60
        
        # Limitar tiempo mínimo a 1 minuto
        tiempo_minutos = max(tiempo_minutos, 1.0)
        
        return tiempo_minutos
    
    def obtener_proximo_paradero(self):
        """
        Determina cuál es el próximo paradero al que llegará el bus (más cercano en distancia).
        """
        if not self.ruta_actual:
            return None
        
        # Obtener la última ubicación del bus
        ultima_ubicacion = UbicacionBus.objects.filter(bus=self, activo=True).order_by('-timestamp').first()
        if not ultima_ubicacion:
            return None
        
        # Obtener paraderos de la ruta actual
        paraderos = Paradero.objects.filter(ruta=self.ruta_actual).order_by('orden')
        if not paraderos:
            return None
        
        # Encontrar el paradero más cercano
        paradero_mas_cercano = None
        distancia_minima = float('inf')
        for paradero in paraderos:
            distancia = geodesic(
                (float(ultima_ubicacion.latitud), float(ultima_ubicacion.longitud)),
                (float(paradero.latitud), float(paradero.longitud))
            ).meters
            if distancia < distancia_minima:
                distancia_minima = distancia
                paradero_mas_cercano = paradero
        return paradero_mas_cercano

    def determinar_orientacion_bus(self):
        """
        Determina si el bus va en orientación 'ida' o 'vuelta' basándose en:
        1. Historial de ubicaciones recientes
        2. Proximidad a paraderos de cada orientación
        3. Dirección de movimiento
        """
        # Obtener últimas ubicaciones (últimos 2-3 minutos)
        ubicaciones_recientes = UbicacionBus.objects.filter(
            bus=self,
            activo=True,
            timestamp__gte=timezone.now() - timedelta(minutes=3)
        ).order_by('-timestamp')[:5]
        if ubicaciones_recientes.count() < 2:
            return None  # No hay suficientes datos
        ubicaciones_list = list(ubicaciones_recientes)
        paraderos_ida = Paradero.objects.filter(ruta=self.ruta_actual, orientacion='ida').order_by('orden')
        paraderos_vuelta = Paradero.objects.filter(ruta=self.ruta_actual, orientacion='vuelta').order_by('orden')
        puntuacion_ida = 0
        puntuacion_vuelta = 0
        for ubicacion in ubicaciones_list:
            min_dist_ida = float('inf')
            for paradero in paraderos_ida:
                dist = geodesic(
                    (float(ubicacion.latitud), float(ubicacion.longitud)),
                    (float(paradero.latitud), float(paradero.longitud))
                ).meters
                min_dist_ida = min(min_dist_ida, dist)
            min_dist_vuelta = float('inf')
            for paradero in paraderos_vuelta:
                dist = geodesic(
                    (float(ubicacion.latitud), float(ubicacion.longitud)),
                    (float(paradero.latitud), float(paradero.longitud))
                ).meters
                min_dist_vuelta = min(min_dist_vuelta, dist)
            if min_dist_ida < min_dist_vuelta:
                puntuacion_ida += 1
            else:
                puntuacion_vuelta += 1
        return 'ida' if puntuacion_ida > puntuacion_vuelta else 'vuelta'

    def obtener_proximo_paradero_secuencial(self):
        """
        Retorna el siguiente paradero en la secuencia SOLO si el bus ya pasó el más cercano (según el orden y la orientación).
        Si no, retorna el más cercano. Así la lógica es secuencial pero realista.
        """
        if not self.ruta_actual:
            return None
        orientacion_actual = self.determinar_orientacion_bus()
        if not orientacion_actual:
            return None
        ultima_ubicacion = UbicacionBus.objects.filter(bus=self, activo=True).order_by('-timestamp').first()
        if not ultima_ubicacion:
            return None
        paraderos = list(Paradero.objects.filter(
            ruta=self.ruta_actual,
            orientacion=orientacion_actual
        ).order_by('orden'))
        if not paraderos:
            return None
        # Buscar el paradero más cercano
        paradero_mas_cercano = paraderos[0]
        distancia_minima = float('inf')
        for paradero in paraderos:
            distancia = geodesic(
                (float(ultima_ubicacion.latitud), float(ultima_ubicacion.longitud)),
                (float(paradero.latitud), float(paradero.longitud))
            ).meters
            if distancia < distancia_minima:
                distancia_minima = distancia
                paradero_mas_cercano = paradero
        idx = paraderos.index(paradero_mas_cercano)
        # Lógica: si el bus ya está más cerca del siguiente paradero (según la dirección de avance), devolver ese
        # Si está cerca del último, el siguiente es el primero (circular)
        siguiente_idx = (idx + 1) % len(paraderos)
        siguiente_paradero = paraderos[siguiente_idx]
        # Calcular distancia al siguiente paradero
        distancia_siguiente = geodesic(
            (float(ultima_ubicacion.latitud), float(ultima_ubicacion.longitud)),
            (float(siguiente_paradero.latitud), float(siguiente_paradero.longitud))
        ).meters
        # Si el bus está más cerca del siguiente que del actual, devolver el siguiente
        if distancia_siguiente < distancia_minima:
            return siguiente_paradero
        # Si no, devolver el más cercano
        return paradero_mas_cercano

    def obtener_proximo_paradero_inteligente(self):
        """
        Método mejorado para obtener el próximo paradero
        Considera dirección de movimiento, orden y orientación
        """
        calculator = ProximoParaderoCalculator(self)
        return calculator.obtener_proximo_paradero_inteligente()

    def obtener_siguientes_paraderos(self, cantidad=3):
        """
        Obtiene los próximos N paraderos en secuencia
        """
        calculator = ProximoParaderoCalculator(self)
        return calculator.obtener_paraderos_siguientes(cantidad)

class UbicacionBus(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE)
    latitud = models.DecimalField(max_digits=10, decimal_places=8)
    longitud = models.DecimalField(max_digits=11, decimal_places=8)
    timestamp = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    @classmethod
    def limpiar_ubicaciones_antiguas(cls, minutos=5):
        """Marca como inactivas las ubicaciones más antiguas que X minutos"""
        tiempo_limite = timezone.now() - timedelta(minutes=minutos)
        cls.objects.filter(
            timestamp__lt=tiempo_limite,
            activo=True
        ).update(activo=False)

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

class SegmentoPersonalizado(models.Model):
    """
    Modelo para almacenar segmentos de ruta personalizados que OSRM no puede calcular
    (ej: trayectos dentro del campus universitario)
    """
    ruta = models.ForeignKey(Ruta, on_delete=models.CASCADE)
    orientacion = models.CharField(
        max_length=10,
        choices=Paradero.ORIENTACION_CHOICES,
        help_text="Orientación de la ruta (ida o vuelta)"
    )
    tipo_segmento = models.CharField(
        max_length=20,
        choices=[
            ('inicio', 'Segmento Inicial'),
            ('final', 'Segmento Final'),
        ],
        help_text="Indica si es el segmento inicial o final de la ruta"
    )
    coordenadas = models.TextField(
        help_text="JSON con array de coordenadas [[lat, lng], [lat, lng], ...]"
    )
    activo = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['ruta', 'orientacion', 'tipo_segmento']
        ordering = ['ruta', 'orientacion', 'tipo_segmento']
    
    def __str__(self):
        return f"{self.ruta.nombre} - {self.get_orientacion_display()} - {self.get_tipo_segmento_display()}"
    
    def get_coordenadas_list(self):
        """Convierte el JSON de coordenadas en una lista de tuplas"""
        import json
        try:
            coords = json.loads(self.coordenadas)
            return [(float(coord[0]), float(coord[1])) for coord in coords]
        except (json.JSONDecodeError, IndexError, ValueError):
            return []

# Create your models here.