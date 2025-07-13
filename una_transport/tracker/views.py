import json
import requests

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout # Importa la función logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Ruta, Paradero, Bus, UbicacionBus, Horario
from geopy.distance import geodesic

def paradero_info(request, paradero_id):
    """
    Dado un paradero, encuentra el bus más cercano que aún no lo ha pasado,
    considerando el orden y la orientación.
    """
    try:
        paradero = Paradero.objects.get(id=paradero_id)
        ubicaciones = UbicacionBus.objects.select_related('bus', 'bus__ruta_actual').order_by('-timestamp')
        
        buses_validos = []

        for ubicacion in ubicaciones:
            bus = ubicacion.bus

            if not bus.ruta_actual:
                continue

            if bus.ruta_actual != paradero.ruta:
                continue  # El bus está en otra ruta

            # Obtener el paradero más cercano al bus en esta ruta y orientación
            paraderos_misma_ruta = Paradero.objects.filter(
                ruta=paradero.ruta,
                orientacion=paradero.orientacion
            ).order_by('orden')

            # Solo considerar buses que aún no hayan pasado el paradero
            for p in paraderos_misma_ruta:
                distancia = geodesic(
                    (float(ubicacion.latitud), float(ubicacion.longitud)),
                    (float(p.latitud), float(p.longitud))
                ).meters

                if p.orden >= paradero.orden:
                    buses_validos.append((bus, distancia))
                    break

        if not buses_validos:
            return JsonResponse({'success': False, 'message': 'No hay buses cercanos aún no pasaron este paradero.'})

        bus_cercano, distancia_metros = sorted(buses_validos, key=lambda x: x[1])[0]
        velocidad_aprox_mpm = 417  # metros por minuto
        tiempo_estimado = round(distancia_metros / velocidad_aprox_mpm)

        return JsonResponse({
            'success': True,
            'bus': {
                'id': bus_cercano.id,
                'nombre': bus_cercano.nombre
            },
            'distancia_metros': round(distancia_metros),
            'tiempo_minutos': tiempo_estimado
        })

    except Paradero.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Paradero no encontrado'})

# --- Funciones Auxiliares para OSRM ---

def decode_polyline(polyline_str):
    """Decodifica una cadena de polilínea codificada en una lista de coordenadas [lat, lng]."""
    index, lat, lng = 0, 0, 0
    coordinates = []
    
    while index < len(polyline_str):
        b, shift, result = 0, 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else (result >> 1)
        lat += dlat

        b, shift, result = 0, 0, 0
        while True:
            b = ord(polyline_str[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if result & 1 else (result >> 1)
        lng += dlng

        coordinates.append((lat / 1e5, lng / 1e5))
    return coordinates

# --- Vistas de la Aplicación ---

def home(request):
    """Renderiza la página principal con información de rutas y horarios."""
    rutas = Ruta.objects.filter(activa=True)
    horarios = Horario.objects.filter(activo=True)
    context = {
        'rutas': rutas,
        'horarios': horarios,
    }
    return render(request, 'tracker/home.html', context)

def login_view(request):
    """Maneja el inicio de sesión para el personal (conductores)."""
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('staff_dashboard')
    return render(request, 'tracker/login.html')

@login_required
def staff_dashboard(request):
    """
    Muestra el panel de control para el personal (conductores).
    Al acceder, borra las ubicaciones anteriores del bus asignado al conductor.
    """
    try:
        bus = Bus.objects.get(conductor=request.user)
        # Borra todas las entradas de UbicacionBus asociadas a este bus
        UbicacionBus.objects.filter(bus=bus).delete()
        print(f"Ubicaciones anteriores borradas para el Bus {bus.nombre}.")
        return render(request, 'tracker/staff_dashboard.html', {'bus': bus})
    except Bus.DoesNotExist:
        return redirect('home')

# NUEVA VISTA: Maneja el cierre de sesión y borra las ubicaciones del bus
def driver_logout_view(request):
    """
    Vista personalizada para cerrar la sesión del conductor.
    Al cerrar sesión, borra todas las ubicaciones del bus asociado
    para que ya no aparezca en el mapa público.
    """
    if request.user.is_authenticated:
        try:
            bus = Bus.objects.get(conductor=request.user)
            # Borrar todas las ubicaciones del bus al cerrar sesión
            UbicacionBus.objects.filter(bus=bus).delete()
            print(f"Ubicaciones del Bus {bus.nombre} borradas al cerrar sesión.")
        except Bus.DoesNotExist:
            print(f"Usuario {request.user.username} no tiene un bus asignado al cerrar sesión.")
        
        logout(request) # Cierra la sesión de Django
    return redirect('home') # Redirige a la página principal después de cerrar sesión

def get_bus_locations(request):
    """API para obtener las últimas ubicaciones de los buses activos."""
    locations = []
    for bus in Bus.objects.filter(activo=True):
        try:
            ultima_ubicacion = UbicacionBus.objects.filter(bus=bus).order_by('-timestamp').first()
            if ultima_ubicacion:
                locations.append({
                    'bus_id': bus.id,
                    'nombre': bus.nombre,
                    'lat': float(ultima_ubicacion.latitud),
                    'lng': float(ultima_ubicacion.longitud),
                    'ruta': bus.ruta_actual.nombre if bus.ruta_actual else 'Sin ruta'
                })
        except Exception as e:
            print(f"Error al obtener ubicación para bus {bus.nombre}: {e}")
            pass 
    return JsonResponse({'locations': locations})

def get_rutas(request):
    """
    API para obtener las rutas y sus paraderos, incluyendo la polilínea detallada
    que sigue las calles usando OSRM.
    """
    rutas_data = []
    for ruta in Ruta.objects.filter(activa=True):
        paraderos = list(Paradero.objects.filter(ruta=ruta).order_by('orden'))
        paraderos_coords = []
        for p in paraderos:
            paraderos_coords.append(f"{p.longitud},{p.latitud}") 

        detailed_route_coords = []
        if len(paraderos_coords) > 1:
            osrm_url = "http://router.project-osrm.org/route/v1/driving/" + ";".join(paraderos_coords)
            osrm_url += "?overview=full&geometries=polyline" 

            try:
                response = requests.get(osrm_url)
                response.raise_for_status() 
                osrm_data = response.json()

                if osrm_data and osrm_data.get('routes'):
                    encoded_polyline = osrm_data['routes'][0]['geometry']
                    detailed_route_coords = decode_polyline(encoded_polyline)
                else:
                    print(f"No se pudo obtener ruta de OSRM para {ruta.nombre}: {osrm_data.get('code', 'N/A')} - {osrm_data.get('message', 'No message')}")
            except requests.exceptions.RequestException as e:
                print(f"Error al conectar con OSRM para la ruta {ruta.nombre}: {e}")
            except Exception as e:
                print(f"Error inesperado al procesar datos de OSRM para {ruta.nombre}: {e}")

        formatted_paraderos = []
        for p in paraderos:
            formatted_paraderos.append({
                'nombre': p.nombre,
                'lat': float(p.latitud),
                'lng': float(p.longitud),
            })
            
        rutas_data.append({
            'id': ruta.id,
            'nombre': ruta.nombre,
            'color': ruta.color,
            'paraderos': formatted_paraderos, 
            'ruta_polyline': detailed_route_coords 
        })
    return JsonResponse({'rutas': rutas_data})
def get_paraderos(request):
    """
    Devuelve todos los paraderos con su información básica para mostrarlos en el mapa.
    """
    paraderos = Paradero.objects.all().order_by('orden')
    data = []
    for p in paraderos:
        data.append({
            'id': p.id,
            'nombre': p.nombre,
            'lat': float(p.latitud),
            'lng': float(p.longitud),
            'ruta': p.ruta.nombre,
            'orientacion': p.orientacion,
            'orden': p.orden
        })
    return JsonResponse({'paraderos': data})

@csrf_exempt 
@require_http_methods(["POST"])
@login_required
def update_location(request):
    """API para que los buses (personal) envíen sus actualizaciones de ubicación."""
    try:
        data = json.loads(request.body)
        bus = Bus.objects.get(conductor=request.user)
        
        UbicacionBus.objects.create(
            bus=bus,
            latitud=data['lat'],
            longitud=data['lng']
        )
        
        return JsonResponse({'success': True})
    except Bus.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuario no asignado a un bus.'}, status=403)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Formato JSON inválido.'}, status=400)
    except KeyError as e:
        return JsonResponse({'success': False, 'error': f'Dato faltante: {e}. Asegúrate de enviar lat y lng.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
