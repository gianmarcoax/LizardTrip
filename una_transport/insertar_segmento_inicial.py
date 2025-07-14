#!/usr/bin/env python
"""
Script para insertar segmentos iniciales personalizados en la base de datos.
Ejecutar con: python insertar_segmento_inicial.py
"""

import os
import sys
import django
import json

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'una_transport.settings')
django.setup()

from tracker.models import Ruta, SegmentoPersonalizado

def insertar_segmento_inicial(coordenadas_inicial):
    """
    Inserta el segmento inicial personalizado para la ruta.
    
    Args:
        coordenadas_inicial (list): Lista de coordenadas [[lat, lng], [lat, lng], ...]
    """
    
    try:
        ruta = Ruta.objects.filter(activa=True).first()
        if not ruta:
            print("❌ No se encontró ninguna ruta activa en la base de datos.")
            return
        
        print(f"✅ Ruta encontrada: {ruta.nombre}")
        
        # Crear o actualizar el segmento inicial para la orientación 'ida'
        segmento_inicial_ida, created = SegmentoPersonalizado.objects.get_or_create(
            ruta=ruta,
            orientacion='ida',
            tipo_segmento='inicio',
            defaults={
                'coordenadas': json.dumps(coordenadas_inicial),
                'activo': True
            }
        )
        
        if created:
            print(f"✅ Segmento inicial creado para ruta '{ruta.nombre}' (ida)")
        else:
            # Actualizar coordenadas existentes
            segmento_inicial_ida.coordenadas = json.dumps(coordenadas_inicial)
            segmento_inicial_ida.activo = True
            segmento_inicial_ida.save()
            print(f"✅ Segmento inicial actualizado para ruta '{ruta.nombre}' (ida)")
        
        # También crear para la orientación 'vuelta' si es necesario
        segmento_inicial_vuelta, created = SegmentoPersonalizado.objects.get_or_create(
            ruta=ruta,
            orientacion='vuelta',
            tipo_segmento='inicio',
            defaults={
                'coordenadas': json.dumps(coordenadas_inicial),
                'activo': True
            }
        )
        
        if created:
            print(f"✅ Segmento inicial creado para ruta '{ruta.nombre}' (vuelta)")
        else:
            segmento_inicial_vuelta.coordenadas = json.dumps(coordenadas_inicial)
            segmento_inicial_vuelta.activo = True
            segmento_inicial_vuelta.save()
            print(f"✅ Segmento inicial actualizado para ruta '{ruta.nombre}' (vuelta)")
        
        print("\n📋 Resumen de segmentos creados:")
        print(f"   - Ruta: {ruta.nombre}")
        print(f"   - Orientación: Ida y Vuelta")
        print(f"   - Tipo: Segmento Inicial")
        print(f"   - Coordenadas: {len(coordenadas_inicial)} puntos")
        print(f"   - Estado: Activo")
        
    except Exception as e:
        print(f"❌ Error al insertar segmento: {e}")

def mostrar_segmentos_existentes():
    """
    Muestra los segmentos personalizados existentes en la base de datos.
    """
    print("\n📋 Segmentos personalizados existentes:")
    segmentos = SegmentoPersonalizado.objects.all().order_by('ruta', 'orientacion', 'tipo_segmento')
    
    if not segmentos:
        print("   No hay segmentos personalizados registrados.")
        return
    
    for segmento in segmentos:
        coords = segmento.get_coordenadas_list()
        print(f"   - {segmento.ruta.nombre} | {segmento.get_orientacion_display()} | {segmento.get_tipo_segmento_display()} | {len(coords)} puntos | {'✅ Activo' if segmento.activo else '❌ Inactivo'}")

def ejemplo_segmento_inicial():
    """
    Ejemplo de cómo usar el script con coordenadas de ejemplo.
    Reemplaza estas coordenadas con las reales de tu segmento inicial.
    """
    # COORDENADAS DE EJEMPLO - REEMPLAZA CON LAS REALES
    coordenadas_ejemplo = [
        [-15.830000, -70.020000],  # Punto de inicio
        [-15.829500, -70.019500],  # Punto intermedio
        [-15.829000, -70.019000],  # Punto intermedio
        [-15.828500, -70.018500],  # Punto final (conecta con OSRM)
    ]
    
    print("🚌 Insertando segmento inicial personalizado...")
    print("⚠️  NOTA: Usando coordenadas de ejemplo. Reemplaza con las reales.")
    
    # Mostrar segmentos existentes
    mostrar_segmentos_existentes()
    
    # Insertar nuevo segmento
    insertar_segmento_inicial(coordenadas_ejemplo)
    
    # Mostrar segmentos después de la inserción
    mostrar_segmentos_existentes()
    
    print("\n✅ Proceso completado. Puedes verificar en el admin de Django.")
    print("\n📝 Para usar coordenadas reales, modifica la función ejemplo_segmento_inicial()")

if __name__ == "__main__":
    ejemplo_segmento_inicial() 