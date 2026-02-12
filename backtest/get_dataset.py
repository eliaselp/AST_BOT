import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime

def conectar_mt5(servidor, numero_cuenta, contraseña):
    """Conecta a una cuenta MT5 específica"""
    if not mt5.initialize():
        print("Error al inicializar MT5:", mt5.last_error())
        return False
    
    autorizado = mt5.login(numero_cuenta, contraseña=contraseña, server=servidor)
    if not autorizado:
        print("Error de login:", mt5.last_error())
        mt5.shutdown()
        return False
    return True

def obtener_datos_eurusd_4h():
    """
    Obtiene datos OHLCV de EURUSD en temporalidad 4H desde 2006
    y los exporta a un archivo CSV
    """
    
    print("🔄 Inicializando MetaTrader 5...")
    if not mt5.initialize():
        print("❌ Error al inicializar MT5:", mt5.last_error())
        return
    
    try:
        # Definir símbolo y temporalidad
        simbolo = "EURUSD"
        timeframe = mt5.TIMEFRAME_H4
        
        # Fecha de inicio: 1 de enero de 2006
        fecha_inicio = datetime(2006, 1, 1)
        fecha_fin = datetime.now()
        
        print(f"📊 Solicitando datos de {simbolo} desde {fecha_inicio.date()} hasta {fecha_fin.date()}")
        print(f"⏰ Temporalidad: 4 horas")
        
        # Obtener datos históricos
        rates = mt5.copy_rates_range(simbolo, timeframe, fecha_inicio, fecha_fin)
        
        if rates is None or len(rates) == 0:
            print("❌ No se pudieron obtener datos")
            mt5.shutdown()
            return
        
        # Crear DataFrame
        df = pd.DataFrame(rates)
        
        # Convertir tiempo a datetime
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Seleccionar y renombrar columnas OHLCV
        df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
        df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        
        # Establecer datetime como índice
        df.set_index('datetime', inplace=True)
        
        # Ordenar cronológicamente
        df.sort_index(inplace=True)
        
        # Mostrar información del dataset
        print(f"\n✅ Datos obtenidos exitosamente:")
        print(f"   Registros: {len(df):,}")
        print(f"   Desde: {df.index[0]}")
        print(f"   Hasta: {df.index[-1]}")
        print(f"   Columnas: {', '.join(df.columns)}")
        
        # Mostrar muestra de los datos
        print("\n📋 Primeros 5 registros:")
        print(df.head())
        print("\n📋 Últimos 5 registros:")
        print(df.tail())
        
        # Exportar a CSV
        nombre_archivo = f"EURUSD_4H_{df.index[0].strftime('%Y%m%d')}_to_{df.index[-1].strftime('%Y%m%d')}.csv"
        df.to_csv(nombre_archivo, float_format='%.5f')
        print(f"\n💾 Datos exportados a: {nombre_archivo}")
        print(f"   Tamaño del archivo: {len(df):,} registros")
        
    except Exception as e:
        print(f"❌ Error durante la obtención de datos: {str(e)}")
    
    finally:
        # Cerrar conexión
        mt5.shutdown()
        print("\n🔌 Conexión con MT5 cerrada")

if __name__ == "__main__":
    obtener_datos_eurusd_4h()