import json
import requests

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout # Importa la función logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET
from django.conf import settings
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
        'Maps_API_KEY': getattr(settings, 'Maps_API_KEY', ''),
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
    """API para obtener las últimas ubicaciones de los buses activos y recientes."""
    from django.utils import timezone
    from datetime import timedelta
    # Limpiar ubicaciones antiguas (más de 5 minutos)
    UbicacionBus.limpiar_ubicaciones_antiguas(minutos=5)
    locations = []
    hace_5_min = timezone.now() - timedelta(minutes=5)
    for bus in Bus.objects.filter(activo=True):
        # Solo mostrar buses que han actualizado en los últimos 5 minutos
        if not bus.ultima_actualizacion or bus.ultima_actualizacion < hace_5_min:
            continue
        try:
            ultima_ubicacion = UbicacionBus.objects.filter(bus=bus, activo=True).order_by('-timestamp').first()
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
    que sigue las calles usando OSRM y segmentos personalizados.
    """
    from .models import SegmentoPersonalizado
    
    rutas_data = []
    for ruta in Ruta.objects.filter(activa=True):
        # Obtener paraderos agrupados por orientación
        paraderos_ida = list(Paradero.objects.filter(ruta=ruta, orientacion='ida').order_by('orden'))
        paraderos_vuelta = list(Paradero.objects.filter(ruta=ruta, orientacion='vuelta').order_by('orden'))
        
        # Procesar ruta de ida
        ruta_ida = procesar_ruta_con_segmentos(ruta, paraderos_ida, 'ida')
        
        # Procesar ruta de vuelta
        ruta_vuelta = procesar_ruta_con_segmentos(ruta, paraderos_vuelta, 'vuelta')
        
        # Combinar ambas orientaciones
        ruta_completa = {
            'id': ruta.id,
            'nombre': ruta.nombre,
            'color': ruta.color,
            'paraderos': ruta_ida['paraderos'] + ruta_vuelta['paraderos'],
            'ruta_polyline': ruta_ida['ruta_polyline'] + ruta_vuelta['ruta_polyline'],
            'orientaciones': {
                'ida': {
                    'paraderos': ruta_ida['paraderos'],
                    'ruta_polyline': ruta_ida['ruta_polyline']
                },
                'vuelta': {
                    'paraderos': ruta_vuelta['paraderos'],
                    'ruta_polyline': ruta_vuelta['ruta_polyline']
                }
            }
        }
        
        rutas_data.append(ruta_completa)
    
    return JsonResponse({'rutas': rutas_data})

def procesar_ruta_con_segmentos(ruta, paraderos, orientacion):
    """
    Procesa una ruta combinando OSRM con segmentos personalizados.
    """
    from .models import SegmentoPersonalizado
    
    # Obtener segmentos personalizados para esta ruta y orientación
    segmento_inicial = SegmentoPersonalizado.objects.filter(
        ruta=ruta, 
        orientacion=orientacion, 
        tipo_segmento='inicio',
        activo=True
    ).first()
    
    segmento_final = SegmentoPersonalizado.objects.filter(
        ruta=ruta, 
        orientacion=orientacion, 
        tipo_segmento='final',
        activo=True
    ).first()
    
    # Obtener coordenadas de OSRM
    osrm_coords = []
    if len(paraderos) > 1:
        paraderos_coords = [f"{p.longitud},{p.latitud}" for p in paraderos]
        osrm_url = "http://router.project-osrm.org/route/v1/driving/" + ";".join(paraderos_coords)
        osrm_url += "?overview=full&geometries=polyline" 

        try:
            response = requests.get(osrm_url)
            response.raise_for_status() 
            osrm_data = response.json()

            if osrm_data and osrm_data.get('routes'):
                encoded_polyline = osrm_data['routes'][0]['geometry']
                osrm_coords = decode_polyline(encoded_polyline)
            else:
                print(f"No se pudo obtener ruta de OSRM para {ruta.nombre} ({orientacion}): {osrm_data.get('code', 'N/A')} - {osrm_data.get('message', 'No message')}")
        except requests.exceptions.RequestException as e:
            print(f"Error al conectar con OSRM para la ruta {ruta.nombre} ({orientacion}): {e}")
        except Exception as e:
            print(f"Error inesperado al procesar datos de OSRM para {ruta.nombre} ({orientacion}): {e}")
    
    # Combinar segmentos: inicial + OSRM + final
    ruta_completa = []
    
    # Agregar segmento inicial si existe
    if segmento_inicial:
        ruta_completa.extend(segmento_inicial.get_coordenadas_list())
    
    # Agregar coordenadas de OSRM
    ruta_completa.extend(osrm_coords)
    
    # Agregar segmento final si existe
    if segmento_final:
        ruta_completa.extend(segmento_final.get_coordenadas_list())
    
    # Formatear paraderos
    formatted_paraderos = []
    for p in paraderos:
        formatted_paraderos.append({
            'nombre': p.nombre,
            'lat': float(p.latitud),
            'lng': float(p.longitud),
            'orientacion': p.orientacion,
            'orden': p.orden
        })
    
    return {
        'paraderos': formatted_paraderos,
        'ruta_polyline': ruta_completa
    }
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
    from django.utils import timezone
    try:
        data = json.loads(request.body)
        bus = Bus.objects.get(conductor=request.user)
        # Marcar todas las ubicaciones anteriores como inactivas
        UbicacionBus.objects.filter(bus=bus, activo=True).update(activo=False)
        UbicacionBus.objects.create(
            bus=bus,
            latitud=data['lat'],
            longitud=data['lng'],
            activo=True
        )
        # Actualizar la última actualización del bus
        bus.ultima_actualizacion = timezone.now()
        bus.save(update_fields=["ultima_actualizacion"])
        return JsonResponse({'success': True})
    except Bus.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuario no asignado a un bus.'}, status=403)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Formato JSON inválido.'}, status=400)
    except KeyError as e:
        return JsonResponse({'success': False, 'error': f'Dato faltante: {e}. Asegúrate de enviar lat y lng.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def get_bus_eta(request):
    """
    API para obtener información de tiempo estimado de llegada de los buses.
    Incluye velocidad actual y próximo paradero.
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Limpiar ubicaciones antiguas
    UbicacionBus.limpiar_ubicaciones_antiguas(minutos=5)
    
    buses_info = []
    hace_5_min = timezone.now() - timedelta(minutes=5)
    
    for bus in Bus.objects.filter(activo=True):
        # Solo procesar buses activos recientemente
        if not bus.ultima_actualizacion or bus.ultima_actualizacion < hace_5_min:
            continue
        
        try:
            ultima_ubicacion = UbicacionBus.objects.filter(bus=bus, activo=True).order_by('-timestamp').first()
            if not ultima_ubicacion:
                continue
            
            # Calcular velocidad actual
            velocidad_mps = bus.calcular_velocidad_actual()
            velocidad_kmh = velocidad_mps * 3.6 if velocidad_mps else None
            
            # Obtener próximo paradero
            proximo_paradero = bus.obtener_proximo_paradero()
            
            # Calcular tiempo de llegada al próximo paradero
            tiempo_llegada = None
            if proximo_paradero and velocidad_mps:
                tiempo_llegada = bus.calcular_tiempo_llegada_paradero(proximo_paradero, velocidad_mps)
            
            bus_info = {
                'bus_id': bus.id,
                'nombre': bus.nombre,
                'lat': float(ultima_ubicacion.latitud),
                'lng': float(ultima_ubicacion.longitud),
                'ruta': bus.ruta_actual.nombre if bus.ruta_actual else 'Sin ruta',
                'ultima_actualizacion': bus.ultima_actualizacion.isoformat() if bus.ultima_actualizacion else None,
                'velocidad_kmh': round(velocidad_kmh, 1) if velocidad_kmh else None,
                'proximo_paradero': {
                    'id': proximo_paradero.id,
                    'nombre': proximo_paradero.nombre,
                    'lat': float(proximo_paradero.latitud),
                    'lng': float(proximo_paradero.longitud),
                    'orden': proximo_paradero.orden
                } if proximo_paradero else None,
                'tiempo_llegada_minutos': round(tiempo_llegada, 1) if tiempo_llegada else None,
                'estado': 'activo'
            }
            
            buses_info.append(bus_info)
            
        except Exception as e:
            print(f"Error al procesar bus {bus.nombre}: {e}")
            continue
    
    return JsonResponse({'buses': buses_info})

def get_paradero_eta(request, paradero_id):
    """
    API para obtener información de tiempo de llegada de buses a un paradero específico.
    """
    try:
        paradero = Paradero.objects.get(id=paradero_id)
        
        # Obtener buses que van hacia este paradero
        buses_hacia_paradero = []
        
        for bus in Bus.objects.filter(activo=True, ruta_actual=paradero.ruta):
            if not bus.esta_activo():
                continue
            
            # Calcular tiempo de llegada a este paradero específico
            tiempo_llegada = bus.calcular_tiempo_llegada_paradero(paradero)
            
            if tiempo_llegada is not None and tiempo_llegada > 0:
                ultima_ubicacion = UbicacionBus.objects.filter(bus=bus, activo=True).order_by('-timestamp').first()
                
                buses_hacia_paradero.append({
                    'bus_id': bus.id,
                    'nombre': bus.nombre,
                    'tiempo_llegada_minutos': round(tiempo_llegada, 1),
                    'distancia_metros': round(tiempo_llegada * 60 * 5.56),  # Aproximación
                    'ultima_ubicacion': {
                        'lat': float(ultima_ubicacion.latitud),
                        'lng': float(ultima_ubicacion.longitud)
                    } if ultima_ubicacion else None
                })
        
        # Ordenar por tiempo de llegada
        buses_hacia_paradero.sort(key=lambda x: x['tiempo_llegada_minutos'])
        
        return JsonResponse({
            'paradero': {
                'id': paradero.id,
                'nombre': paradero.nombre,
                'lat': float(paradero.latitud),
                'lng': float(paradero.longitud),
                'ruta': paradero.ruta.nombre,
                'orientacion': paradero.orientacion
            },
            'buses_proximos': buses_hacia_paradero[:3],  # Solo los 3 más próximos
            'total_buses': len(buses_hacia_paradero)
        })
        
    except Paradero.DoesNotExist:
        return JsonResponse({'error': 'Paradero no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_GET
def get_buses_with_next_stop(request):
    """
    API que devuelve todos los buses activos con su próximo paradero REAL (más cercano), orientación y ETA.
    """
    from django.utils import timezone
    buses_info = []
    for bus in Bus.objects.filter(activo=True):
        if not bus.esta_activo():
            continue
        # CAMBIO: Usar el próximo paradero más cercano, no el secuencial
        proximo_paradero = bus.obtener_proximo_paradero()
        orientacion = bus.determinar_orientacion_bus()
        # Ícono de orientación
        icono = '⬆️' if orientacion == 'ida' else '⬇️' if orientacion == 'vuelta' else ''
        buses_info.append({
            'bus_id': bus.id,
            'nombre': bus.nombre,
            'ruta': bus.ruta_actual.nombre if bus.ruta_actual else None,
            'orientacion': orientacion,
            'orientacion_icono': icono,
            'proximo_paradero': {
                'id': proximo_paradero.id,
                'nombre': proximo_paradero.nombre,
                'orden': proximo_paradero.orden
            } if proximo_paradero else None,
            'eta_minutos': bus.calcular_tiempo_llegada_paradero(proximo_paradero) if proximo_paradero else None
        })
    return JsonResponse({'buses': buses_info})

@require_GET
def get_buses_with_next_stop_mejorado(request):
    """
    API mejorada que devuelve buses con próximo paradero usando lógica inteligente
    """
    from django.utils import timezone
    buses_info = []
    for bus in Bus.objects.filter(activo=True):
        if not bus.esta_activo():
            continue
        try:
            proximo_paradero = bus.obtener_proximo_paradero_inteligente()
            siguientes_paraderos = bus.obtener_siguientes_paraderos(3)
            ultima_ubicacion = UbicacionBus.objects.filter(bus=bus, activo=True).order_by('-timestamp').first()
            velocidad_kmh = bus.calcular_velocidad_actual() * 3.6 if bus.calcular_velocidad_actual() else None
            orientacion = bus.determinar_orientacion_bus()
            icono = '⬆️' if orientacion == 'ida' else '⬇️' if orientacion == 'vuelta' else '🔄'
            buses_info.append({
                'bus_id': bus.id,
                'nombre': bus.nombre,
                'ruta': bus.ruta_actual.nombre if bus.ruta_actual else None,
                'orientacion': orientacion,
                'orientacion_icono': icono,
                'ubicacion': {
                    'lat': float(ultima_ubicacion.latitud),
                    'lng': float(ultima_ubicacion.longitud),
                    'timestamp': ultima_ubicacion.timestamp.isoformat()
                } if ultima_ubicacion else None,
                'velocidad_kmh': velocidad_kmh,
                'proximo_paradero': {
                    'id': proximo_paradero.id,
                    'nombre': proximo_paradero.nombre,
                    'lat': float(proximo_paradero.latitud),
                    'lng': float(proximo_paradero.longitud),
                    'orden': proximo_paradero.orden
                } if proximo_paradero else None,
                'siguientes_paraderos': [
                    {
                        'id': p.id,
                        'nombre': p.nombre,
                        'orden': p.orden
                    } for p in siguientes_paraderos
                ] if siguientes_paraderos else [],
                'eta_minutos': bus.calcular_tiempo_llegada_paradero(proximo_paradero) if proximo_paradero else None
            })
        except Exception as e:
            print(f"Error al procesar bus {bus.nombre}: {e}")
            continue
    return JsonResponse({'buses': buses_info, 'total': len(buses_info), 'timestamp': timezone.now().isoformat()})
