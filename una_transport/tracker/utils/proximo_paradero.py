import math
from django.utils import timezone
from datetime import timedelta
from geopy.distance import geodesic

class ProximoParaderoCalculator:
    """
    Clase para calcular el próximo paradero de manera más inteligente
    considerando dirección de movimiento, orden secuencial y orientación
    """
    
    def __init__(self, bus):
        self.bus = bus
        self.umbral_distancia_maxima = 500  # metros
        self.umbral_paradero_pasado = 50   # metros
        self.ventana_historial = 3         # minutos
    
    def obtener_proximo_paradero_inteligente(self):
        """
        Determina el próximo paradero usando múltiples criterios
        """
        if not self.bus.ruta_actual:
            return None
        
        # 1. Obtener orientación actual
        orientacion = self.bus.determinar_orientacion_bus()
        if not orientacion:
            return self._fallback_paradero_mas_cercano()
        
        # 2. Obtener ubicación actual
        ubicacion_actual = self._obtener_ubicacion_actual()
        if not ubicacion_actual:
            return None
        
        # 3. Obtener dirección de movimiento
        direccion_movimiento = self._calcular_direccion_movimiento()
        
        # 4. Obtener paraderos de la orientación actual
        paraderos = self._obtener_paraderos_orientacion(orientacion)
        if not paraderos:
            return None
        
        # 5. Calcular próximo paradero usando múltiples criterios
        proximo_paradero = self._calcular_proximo_paradero_avanzado(
            ubicacion_actual, 
            paraderos, 
            direccion_movimiento
        )
        
        return proximo_paradero
    
    def _obtener_ubicacion_actual(self):
        """Obtiene la ubicación más reciente del bus"""
        from tracker.models import UbicacionBus
        return UbicacionBus.objects.filter(
            bus=self.bus, 
            activo=True
        ).order_by('-timestamp').first()
    
    def _obtener_paraderos_orientacion(self, orientacion):
        """Obtiene paraderos de la orientación específica ordenados"""
        from tracker.models import Paradero
        return list(Paradero.objects.filter(
            ruta=self.bus.ruta_actual,
            orientacion=orientacion
        ).order_by('orden'))
    
    def _calcular_direccion_movimiento(self):
        """
        Calcula la dirección de movimiento basada en historial reciente
        Retorna ángulo en grados (0-360)
        """
        from tracker.models import UbicacionBus
        
        ubicaciones = UbicacionBus.objects.filter(
            bus=self.bus,
            activo=True,
            timestamp__gte=timezone.now() - timedelta(minutes=self.ventana_historial)
        ).order_by('-timestamp')[:5]
        
        if ubicaciones.count() < 2:
            return None
        
        ubicaciones_list = list(ubicaciones)
        
        # Calcular vector de movimiento promedio
        vectores = []
        for i in range(len(ubicaciones_list) - 1):
            actual = ubicaciones_list[i]
            anterior = ubicaciones_list[i + 1]
            
            # Calcular diferencias en coordenadas
            dlat = float(actual.latitud) - float(anterior.latitud)
            dlng = float(actual.longitud) - float(anterior.longitud)
            
            # Calcular ángulo
            angulo = math.atan2(dlng, dlat)
            vectores.append(angulo)
        
        if not vectores:
            return None
        
        # Promedio de ángulos (considerando circularidad)
        x_sum = sum(math.cos(angulo) for angulo in vectores)
        y_sum = sum(math.sin(angulo) for angulo in vectores)
        
        angulo_promedio = math.atan2(y_sum, x_sum)
        
        # Convertir a grados (0-360)
        angulo_grados = (math.degrees(angulo_promedio) + 360) % 360
        
        return angulo_grados
    
    def _calcular_proximo_paradero_avanzado(self, ubicacion_actual, paraderos, direccion_movimiento):
        """
        Calcula el próximo paradero usando múltiples criterios avanzados
        """
        candidatos = []
        
        for paradero in paraderos:
            # Calcular distancia
            distancia = geodesic(
                (float(ubicacion_actual.latitud), float(ubicacion_actual.longitud)),
                (float(paradero.latitud), float(paradero.longitud))
            ).meters
            
            # Filtrar paraderos muy lejanos
            if distancia > self.umbral_distancia_maxima:
                continue
            
            # Calcular ángulo hacia el paradero
            angulo_paradero = self._calcular_angulo_hacia_paradero(
                ubicacion_actual, paradero
            )
            
            # Calcular alineación con dirección de movimiento
            alineacion = self._calcular_alineacion_direccion(
                direccion_movimiento, angulo_paradero
            ) if direccion_movimiento else 0.5
            
            # Determinar si el paradero ya fue pasado
            fue_pasado = self._paradero_fue_pasado(paradero)
            
            # Calcular puntuación del candidato
            puntuacion = self._calcular_puntuacion_candidato(
                distancia, alineacion, paradero.orden, fue_pasado
            )
            
            candidatos.append({
                'paradero': paradero,
                'distancia': distancia,
                'alineacion': alineacion,
                'puntuacion': puntuacion,
                'fue_pasado': fue_pasado
            })
        
        if not candidatos:
            return self._fallback_paradero_mas_cercano()
        
        # Ordenar por puntuación y seleccionar el mejor
        candidatos.sort(key=lambda x: x['puntuacion'], reverse=True)
        
        return candidatos[0]['paradero']
    
    def _calcular_angulo_hacia_paradero(self, ubicacion_actual, paradero):
        """Calcula el ángulo desde la ubicación actual hacia el paradero"""
        dlat = float(paradero.latitud) - float(ubicacion_actual.latitud)
        dlng = float(paradero.longitud) - float(ubicacion_actual.longitud)
        
        angulo = math.atan2(dlng, dlat)
        return (math.degrees(angulo) + 360) % 360
    
    def _calcular_alineacion_direccion(self, direccion_movimiento, angulo_paradero):
        """
        Calcula qué tan alineado está el paradero con la dirección de movimiento
        Retorna valor entre 0 (opuesto) y 1 (perfectamente alineado)
        """
        if direccion_movimiento is None:
            return 0.5  # Neutral si no hay dirección
        
        # Calcular diferencia angular
        diff = abs(direccion_movimiento - angulo_paradero)
        if diff > 180:
            diff = 360 - diff
        
        # Convertir a factor de alineación (0-1)
        alineacion = 1 - (diff / 180)
        
        return max(0, alineacion)
    
    def _paradero_fue_pasado(self, paradero):
        """
        Determina si el bus ya pasó por este paradero recientemente
        """
        from tracker.models import UbicacionBus
        
        # Obtener ubicaciones recientes cerca del paradero
        ubicaciones_recientes = UbicacionBus.objects.filter(
            bus=self.bus,
            activo=True,
            timestamp__gte=timezone.now() - timedelta(minutes=10)
        ).order_by('-timestamp')
        
        paradero_visitado = False
        for ubicacion in ubicaciones_recientes:
            distancia = geodesic(
                (float(ubicacion.latitud), float(ubicacion.longitud)),
                (float(paradero.latitud), float(paradero.longitud))
            ).meters
            
            if distancia <= self.umbral_paradero_pasado:
                paradero_visitado = True
                break
        
        return paradero_visitado
    
    def _calcular_puntuacion_candidato(self, distancia, alineacion, orden, fue_pasado):
        """
        Calcula puntuación del candidato basada en múltiples factores
        """
        puntuacion = 0
        
        # Factor distancia (más cerca = mejor, pero no lineal)
        if distancia <= 100:
            factor_distancia = 1.0
        elif distancia <= 200:
            factor_distancia = 0.8
        elif distancia <= 300:
            factor_distancia = 0.6
        else:
            factor_distancia = max(0.1, 1 - (distancia / 500))
        
        # Factor alineación (dirección de movimiento)
        factor_alineacion = alineacion
        
        # Factor orden (preferir paraderos con orden mayor si es secuencial)
        factor_orden = 0.1  # Peso menor
        
        # Penalización si ya fue pasado
        penalizacion_pasado = -0.5 if fue_pasado else 0
        
        # Cálculo final
        puntuacion = (
            factor_distancia * 0.4 +
            factor_alineacion * 0.4 +
            factor_orden * 0.1 +
            penalizacion_pasado
        )
        
        return max(0, puntuacion)
    
    def _fallback_paradero_mas_cercano(self):
        """Método de respaldo: retorna el paradero más cercano"""
        return self.bus.obtener_proximo_paradero()
    
    def obtener_paraderos_siguientes(self, cantidad=3):
        """
        Obtiene los siguientes N paraderos en secuencia
        """
        proximo = self.obtener_proximo_paradero_inteligente()
        if not proximo:
            return []
        
        orientacion = self.bus.determinar_orientacion_bus()
        if not orientacion:
            return [proximo]
        
        paraderos = self._obtener_paraderos_orientacion(orientacion)
        if not paraderos:
            return [proximo]
        
        try:
            indice_actual = paraderos.index(proximo)
            siguientes = []
            
            for i in range(cantidad):
                siguiente_indice = (indice_actual + i) % len(paraderos)
                siguientes.append(paraderos[siguiente_indice])
            
            return siguientes
        except ValueError:
            return [proximo] 