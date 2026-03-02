import pandas as pd
import MetaTrader5 as mt5
import time
from datetime import datetime, timedelta
import pytz
import os

def conectar_mt5(servidor=None, numero_cuenta=None, contraseña=None):
    """Conecta a MT5, opcionalmente a una cuenta específica"""
    if not mt5.initialize():
        print("❌ Error al inicializar MT5:", mt5.last_error())
        return False
    
    if servidor and numero_cuenta and contraseña:
        autorizado = mt5.login(numero_cuenta, password=contraseña, server=servidor)
        if not autorizado:
            print("❌ Error de login:", mt5.last_error())
            return False
        print(f"✅ Conectado a cuenta {numero_cuenta}@{servidor}")
    else:
        print("✅ MT5 inicializado en modo terminal")
    
    return True

def obtener_rango_fechas(ano_inicio=2006, fecha_fin=None):
    """
    Calcula las fechas de inicio y fin para la descarga de datos
    
    Args:
        ano_inicio: Año de inicio (default: 2006)
        fecha_fin: Fecha final (default: fecha actual)
    
    Returns:
        Tuple (fecha_inicio, fecha_fin) como datetime
    """
    # Fecha de inicio (1 de enero del año especificado)
    fecha_inicio = datetime(ano_inicio, 1, 1, tzinfo=pytz.UTC)
    
    # Fecha de fin (hoy o fecha especificada)
    if fecha_fin is None:
        fecha_fin = datetime.now(pytz.UTC)
    elif isinstance(fecha_fin, str):
        fecha_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
    
    return fecha_inicio, fecha_fin

def obtener_datos_ohlcv(simbolo, timeframe, fecha_inicio, fecha_fin, timeout_segundos=30):
    """
    Obtiene datos OHLCV de MT5 para un período específico
    
    Args:
        simbolo: Par de trading (ej: 'EURUSD')
        timeframe: Temporalidad (mt5.TIMEFRAME_*)
        fecha_inicio: Fecha de inicio (datetime)
        fecha_fin: Fecha de fin (datetime)
        timeout_segundos: Timeout para cada intento
    
    Returns:
        DataFrame con datos OHLCV o None si hay error
    """
    print(f"\n📥 Descargando {simbolo} desde {fecha_inicio.strftime('%Y-%m-%d')} hasta {fecha_fin.strftime('%Y-%m-%d')}")
    
    # Verificar que el símbolo existe
    symbol_info = mt5.symbol_info(simbolo)
    if symbol_info is None:
        print(f"❌ El símbolo {simbolo} no existe")
        return None
    
    # Activar símbolo si no está visible
    if not symbol_info.visible:
        print(f"🔄 Activando símbolo {simbolo}...")
        if not mt5.symbol_select(simbolo, True):
            print(f"❌ No se pudo activar {simbolo}")
            return None
    
    # Obtener datos en bloques para evitar timeouts
    todos_los_datos = []
    fecha_actual = fecha_inicio
    
    while fecha_actual < fecha_fin:
        try:
            # Calcular fecha final para este bloque (máximo 1 año por bloque)
            fecha_bloque_fin = min(fecha_actual + timedelta(days=365), fecha_fin)
            
            print(f"   Procesando bloque: {fecha_actual.strftime('%Y-%m-%d')} a {fecha_bloque_fin.strftime('%Y-%m-%d')}")
            
            # Obtener rates para el bloque
            rates = mt5.copy_rates_range(simbolo, timeframe, fecha_actual, fecha_bloque_fin)
            
            if rates is not None and len(rates) > 0:
                df_bloque = pd.DataFrame(rates)
                todos_los_datos.append(df_bloque)
                print(f"   ✅ {len(rates)} velas obtenidas")
            else:
                print(f"   ⚠️ No hay datos para este bloque")
            
            # Avanzar al siguiente bloque
            fecha_actual = fecha_bloque_fin
            
            # Pequeña pausa para no saturar
            time.sleep(0.5)
            
        except Exception as e:
            print(f"   ❌ Error en bloque: {str(e)}")
            time.sleep(2)
            continue
    
    # Combinar todos los bloques
    if todos_los_datos:
        df_final = pd.concat(todos_los_datos, ignore_index=True)
        df_final = df_final.drop_duplicates(subset=['time']).sort_values('time')
        
        # Convertir timestamp a datetime
        df_final['time'] = pd.to_datetime(df_final['time'], unit='s')
        df_final.set_index('time', inplace=True)
        
        # Renombrar columnas
        df_final.columns = ['open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
        
        # Crear columna 'volume' combinada
        df_final['volume'] = df_final['real_volume'].where(df_final['real_volume'] > 0, df_final['tick_volume'])
        
        # Reordenar columnas
        columnas_ordenadas = ['open', 'high', 'low', 'close', 'volume', 'tick_volume', 'real_volume', 'spread']
        df_final = df_final[columnas_ordenadas]
        
        return df_final
    
    return None

def exportar_ohlcv_a_csv(simbolo, temporalidad, ano_inicio=2006, fecha_fin=None, 
                         servidor=None, numero_cuenta=None, contraseña=None, 
                         nombre_archivo=None):
    """
    Función principal para exportar datos OHLCV a CSV
    
    Args:
        simbolo: Par de trading (ej: 'EURUSD')
        temporalidad: '1min', '5min', '15min', '30min', '1hour', '4hour', '1day', '1week', '1month'
        ano_inicio: Año de inicio (default: 2006)
        fecha_fin: Fecha final (default: hoy)
        servidor: Servidor MT5 (opcional)
        numero_cuenta: Número de cuenta (opcional)
        contraseña: Contraseña (opcional)
        nombre_archivo: Nombre del archivo CSV (opcional)
    
    Returns:
        DataFrame con los datos o None si hay error
    """
    
    # Mapeo de temporalidades
    timeframes = {
        '1min': mt5.TIMEFRAME_M1,
        '5min': mt5.TIMEFRAME_M5,
        '15min': mt5.TIMEFRAME_M15,
        '30min': mt5.TIMEFRAME_M30,
        '1hour': mt5.TIMEFRAME_H1,
        '4hour': mt5.TIMEFRAME_H4,
        '1day': mt5.TIMEFRAME_D1,
        '1week': mt5.TIMEFRAME_W1,
        '1month': mt5.TIMEFRAME_MN1
    }
    
    if temporalidad not in timeframes:
        print(f"❌ Temporalidad '{temporalidad}' no válida")
        print("   Temporalidades disponibles:", list(timeframes.keys()))
        return None
    
    print(f"\n{'='*60}")
    print(f"📊 EXPORTADOR OHLCV")
    print(f"{'='*60}")
    print(f"Símbolo: {simbolo}")
    print(f"Temporalidad: {temporalidad}")
    print(f"Año inicio: {ano_inicio}")
    
    # Conectar a MT5
    if not conectar_mt5(servidor, numero_cuenta, contraseña):
        print("❌ No se pudo conectar a MT5")
        return None
    
    try:
        # Calcular fechas
        fecha_inicio, fecha_fin_dt = obtener_rango_fechas(ano_inicio, fecha_fin)
        print(f"Rango: {fecha_inicio.strftime('%Y-%m-%d')} a {fecha_fin_dt.strftime('%Y-%m-%d')}")
        
        # Obtener datos
        df = obtener_datos_ohlcv(
            simbolo=simbolo,
            timeframe=timeframes[temporalidad],
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin_dt
        )
        
        if df is None or len(df) == 0:
            print(f"❌ No se obtuvieron datos para {simbolo}")
            return None
        
        print(f"\n✅ Datos obtenidos: {len(df)} velas")
        print(f"   Rango: {df.index[0].strftime('%Y-%m-%d %H:%M')} a {df.index[-1].strftime('%Y-%m-%d %H:%M')}")
        
        # Crear nombre de archivo si no se especificó
        if nombre_archivo is None:
            fecha_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            nombre_archivo = f"{simbolo}_{temporalidad}_{ano_inicio}_a_{fecha_fin_dt.strftime('%Y%m%d')}.csv"
        
        # Exportar a CSV
        df.to_csv(nombre_archivo)
        print(f"\n💾 Datos guardados en: {nombre_archivo}")
        print(f"   Tamaño del archivo: {os.path.getsize(nombre_archivo) / (1024*1024):.2f} MB")
        
        # Mostrar primeras filas
        print(f"\n📋 Primeras 5 filas:")
        print(df.head())
        
        print(f"\n📋 Últimas 5 filas:")
        print(df.tail())
        
        # Mostrar estadísticas
        print(f"\n📊 Estadísticas:")
        print(f"   Precio máximo: {df['high'].max():.5f}")
        print(f"   Precio mínimo: {df['low'].min():.5f}")
        print(f"   Volumen total: {df['volume'].sum():,.0f}")
        print(f"   Velas con volumen 0: {(df['volume'] == 0).sum()}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error durante la exportación: {str(e)}")
        return None
    
    finally:
        # Limpiar conexión
        mt5.shutdown()
        print("\n🔄 Conexión MT5 cerrada")

def main():
    """
    Función principal con ejemplos de uso
    """
    print("🚀 EXPORTADOR DE DATOS OHLCV DESDE 2006")
    print("="*60)
    
    # ============================================
    # CONFIGURACIÓN DEL USUARIO
    # ============================================
    
    # Configuración de la cuenta (opcional - dejar en None si no se necesita cuenta específica)
    CONFIG = {
        'servidor': None,  # Ej: 'ICMarkets-Demo'
        'numero_cuenta': None,  # Ej: 12345678
        'contraseña': None,  # Tu contraseña
    }
    
    # Parámetros de descarga
    SIMBOLO = "EURUSD"  # Cambiar por el par deseado
    TEMPORALIDAD = "1day"  # 1min, 5min, 15min, 30min, 1hour, 4hour, 1day, 1week, 1month
    ANO_INICIO = 2006  # Año de inicio
    FECHA_FIN = None  # None para fecha actual, o formato 'YYYY-MM-DD'
    
    # ============================================
    # EJECUTAR EXPORTACIÓN
    # ============================================
    
    df = exportar_ohlcv_a_csv(
        simbolo=SIMBOLO,
        temporalidad=TEMPORALIDAD,
        ano_inicio=ANO_INICIO,
        fecha_fin=FECHA_FIN,
        servidor=CONFIG['servidor'],
        numero_cuenta=CONFIG['numero_cuenta'],
        contraseña=CONFIG['contraseña']
    )
    
    if df is not None:
        print(f"\n{'='*60}")
        print("✅ EXPORTACIÓN COMPLETADA EXITOSAMENTE")
        print(f"{'='*60}")
        
        # Opcional: Mostrar información adicional
        print(f"\nInformación del DataFrame:")
        print(df.info())
    else:
        print(f"\n❌ Error en la exportación")

if __name__ == "__main__":
    main()