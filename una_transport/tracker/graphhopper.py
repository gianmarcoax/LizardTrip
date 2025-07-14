# services/graphhopper.py
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def get_graphhopper_route(points, vehicle='car', locale='es'):
    """
    Obtiene una ruta de GraphHopper
    :param points: Lista de coordenadas en formato ['lat,lng', 'lat,lng']
    :param vehicle: Tipo de vehículo (car, foot, bike)
    :param locale: Idioma para instrucciones
    :return: Diccionario con datos de la ruta
    """
    # URL base de GraphHopper
    base_url = "https://graphhopper.com/api/1/route"
    
    # Verificar que la API key esté configurada
    api_key = getattr(settings, 'GRAPHHOPPER_API_KEY', None)
    if not api_key:
        logger.error("GRAPHHOPPER_API_KEY no está configurada en settings.py")
        return None
    
    params = {
        'point': points,
        'vehicle': vehicle,
        'key': api_key,  # Corregido: ahora usa la variable
        'instructions': 'false',
        'calc_points': 'true',
        'points_encoded': 'false',
        'locale': locale
    }
    
    try:
        logger.info(f"Solicitando ruta GraphHopper para puntos: {points}")
        response = requests.get(
            base_url,
            params=params,
            timeout=10
        )
        
        logger.info(f"Respuesta GraphHopper - Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'paths' in data and len(data['paths']) > 0:
                logger.info("Ruta obtenida exitosamente de GraphHopper")
                return data
            else:
                logger.warning(f"GraphHopper no encontró rutas: {data}")
                return None
        else:
            logger.error(f"Error en GraphHopper API: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("Timeout al conectar con GraphHopper")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al conectar con GraphHopper: {e}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado con GraphHopper: {e}")
        return None