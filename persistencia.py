"""
MÓDULO DE PERSISTENCIA DE DIRECCIONES
"""
import json
import os
from typing import Dict, Optional

ARCHIVO_DIRECCIONES = "direccion.json"

def cargar_direcciones(temporalidad) -> Dict[str, str]:
    """Carga las direcciones desde el archivo JSON"""
    try:
        if os.path.exists(f"{temporalidad}_{ARCHIVO_DIRECCIONES}"):
            with open(f"{temporalidad}_{ARCHIVO_DIRECCIONES}", 'r', encoding='utf-8') as f:
                datos = json.load(f)
                print(f"✅ Direcciones cargadas desde {temporalidad}_{ARCHIVO_DIRECCIONES}")
                return datos
        else:
            print(f"⚠️  Archivo {temporalidad}_{ARCHIVO_DIRECCIONES} no encontrado, se creará con valores por defecto")
            return {}
    except Exception as e:
        print(f"❌ Error cargando direcciones: {e}")
        return {}

def guardar_direcciones(direcciones: Dict[str, str], temporalidad:str):
    """Guarda las direcciones en el archivo JSON"""
    try:
        with open(f"{temporalidad}_{ARCHIVO_DIRECCIONES}", 'w', encoding='utf-8') as f:
            json.dump(direcciones, f, indent=2, ensure_ascii=False)
        print(f"💾 Direcciones guardadas en {temporalidad}_{ARCHIVO_DIRECCIONES}")
    except Exception as e:
        print(f"❌ Error guardando direcciones: {e}")

def actualizar_direccion(par: str, direccion: str, temporalidad: str):
    """Actualiza la dirección de un par específico"""
    try:
        # Cargar direcciones existentes
        direcciones = cargar_direcciones(temporalidad=temporalidad)
        
        # Actualizar el par
        direcciones[par] = direccion
        
        # Guardar cambios
        guardar_direcciones(direcciones, temporalidad)
        
        print(f"📝 {par}: Dirección actualizada a {direccion}")
        return True
    except Exception as e:
        print(f"❌ Error actualizando dirección para {par}: {e}")
        return False