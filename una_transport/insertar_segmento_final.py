#!/usr/bin/env python
"""
Script para insertar el segmento final personalizado en la base de datos.
Ejecutar con: python insertar_segmento_final.py
"""

import os
import sys
import django
import json

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'una_transport.settings')
django.setup()

from tracker.models import Ruta, SegmentoPersonalizado

def insertar_segmento_final():
    """
    Inserta el segmento final personalizado para la ruta que entra al campus universitario.
    """
    
    # Coordenadas del segmento final (dentro del campus)
    coordenadas_final = [
        [-15.827523, -70.01708],
        [-15.827335, -70.017059],
        [-15.82688, -70.016953],
        [-15.82662, -70.016895],
        [-15.826477, -70.016862],
        [-15.82609, -70.016766],
        [-15.825605, -70.016641],
        [-15.825499, -70.016617],
        [-15.82512, -70.016518],
        [-15.824926, -70.016478],
        [-15.82466, -70.016423],
        [-15.824673, -70.016326]
    ]
    
    # Buscar la ruta (asumiendo que es la primera ruta activa)
    # Puedes modificar esto para buscar por nombre específico
    try:
        ruta = Ruta.objects.filter(activa=True).first()
        if not ruta:
            print("❌ No se encontró ninguna ruta activa en la base de datos.")
            return
        
        print(f"✅ Ruta encontrada: {ruta.nombre}")
        
        # Crear o actualizar el segmento final para la orientación 'ida'
        segmento_final_ida, created = SegmentoPersonalizado.objects.get_or_create(
            ruta=ruta,
            orientacion='ida',
            tipo_segmento='final',
            defaults={
                'coordenadas': json.dumps(coordenadas_final),
                'activo': True
            }
        )
        
        if created:
            print(f"✅ Segmento final creado para ruta '{ruta.nombre}' (ida)")
        else:
            # Actualizar coordenadas existentes
            segmento_final_ida.coordenadas = json.dumps(coordenadas_final)
            segmento_final_ida.activo = True
            segmento_final_ida.save()
            print(f"✅ Segmento final actualizado para ruta '{ruta.nombre}' (ida)")
        
        # También crear para la orientación 'vuelta' si es necesario
        segmento_final_vuelta, created = SegmentoPersonalizado.objects.get_or_create(
            ruta=ruta,
            orientacion='vuelta',
            tipo_segmento='final',
            defaults={
                'coordenadas': json.dumps(coordenadas_final),
                'activo': True
            }
        )
        
        if created:
            print(f"✅ Segmento final creado para ruta '{ruta.nombre}' (vuelta)")
        else:
            segmento_final_vuelta.coordenadas = json.dumps(coordenadas_final)
            segmento_final_vuelta.activo = True
            segmento_final_vuelta.save()
            print(f"✅ Segmento final actualizado para ruta '{ruta.nombre}' (vuelta)")
        
        print("\n📋 Resumen de segmentos creados:")
        print(f"   - Ruta: {ruta.nombre}")
        print(f"   - Orientación: Ida y Vuelta")
        print(f"   - Tipo: Segmento Final")
        print(f"   - Coordenadas: {len(coordenadas_final)} puntos")
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

if __name__ == "__main__":
    print("🚌 Insertando segmento final personalizado para campus universitario...")
    
    # Mostrar segmentos existentes
    mostrar_segmentos_existentes()
    
    # Insertar nuevo segmento
    insertar_segmento_final()
    
    # Mostrar segmentos después de la inserción
    mostrar_segmentos_existentes()
    
    print("\n✅ Proceso completado. Puedes verificar en el admin de Django.") 