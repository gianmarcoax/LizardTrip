# services/graphhopper.py
import requests
from django.conf import settings

def get_graphhopper_route(points, vehicle='foot', locale='es'):
    """
    Obtiene una ruta de GraphHopper sin usar urlencode
    :param points: Lista de coordenadas en formato ['lat,lng', 'lat,lng']
    :param vehicle: Tipo de vehículo (car, foot, bike)
    :param locale: Idioma para instrucciones
    :return: Diccionario con datos de la ruta
    """
    params = {
        'point': points,
        'vehicle': vehicle,
        'locale': locale,
        'key': settings.GRAPHOPPER_API_KEY,
        'instructions': False,
        'calc_points': True,
        'points_encoded': False
    }
    
    try:
        response = requests.get(
            settings.GRAPHOPPER_API_URL,
            params=params,
            timeout=10  # Timeout de 10 segundos
        )
        response.raise_for_status()  # Lanza excepción para códigos 4XX/5XX
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con GraphHopper: {e}")
        return None