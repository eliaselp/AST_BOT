# tiempo.py
"""
Módulo simplificado para manejo de tiempo en trading.
Solo 2 funciones esenciales: obtener hora actual y convertir a NY.
"""

import pytz
from datetime import datetime
from dateutil import parser
import MetaTrader5 as mt5

def obtener_hora_actual():
    """
    Obtiene la hora actual del servidor MT5 si está disponible, 
    de lo contrario usa la hora local del sistema.
    
    Returns:
        datetime: Hora actual en UTC
    """
    try:
        # Intentar obtener hora del último tick de EURUSD
        if mt5.initialize():
            tick = mt5.symbol_info_tick("EURUSD")
            mt5.shutdown()
            
            if tick and hasattr(tick, 'time'):
                # tick.time es timestamp UTC en segundos
                return datetime.fromtimestamp(tick.time, pytz.UTC)
    except:
        pass
    
    # Fallback: hora del sistema en UTC
    return datetime.now(pytz.UTC)

def convertir_a_hora_ny(hora_input):
    """
    Convierte cualquier hora a hora de Nueva York.
    Acepta: datetime, string, timestamp (int/float)
    
    Args:
        hora_input: Hora en cualquier formato común
    
    Returns:
        datetime: Hora en zona horaria de Nueva York
    """
    tz_ny = pytz.timezone('America/New_York')
    
    # Si ya es datetime
    if isinstance(hora_input, datetime):
        dt = hora_input
    
    # Si es timestamp numérico
    elif isinstance(hora_input, (int, float)):
        dt = datetime.fromtimestamp(hora_input, pytz.UTC)
    
    # Si es string
    elif isinstance(hora_input, str):
        dt = parser.parse(hora_input)
    
    else:
        raise TypeError(f"Formato no soportado: {type(hora_input)}")
    
    # Asegurar que tenga zona horaria (asumir UTC si no la tiene)
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    
    # Convertir a Nueva York
    return dt.astimezone(tz_ny)

# Uso directo sin necesidad de funciones adicionales
if __name__ == "__main__":
    # Ejemplo 1: Hora actual del servidor en NY
    hora_actual = obtener_hora_actual()
    hora_ny = convertir_a_hora_ny(hora_actual)
    print(f"Hora actual NY: {hora_ny.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Ejemplo 2: Convertir string cualquiera
    ejemplo = convertir_a_hora_ny("2024-01-15 14:30:00")
    print(f"String a NY: {ejemplo.strftime('%H:%M %Z')}")