import pandas as pd
from tvDatafeed import TvDatafeed, Interval
## Instalación (desde el repositorio de GitHub)
#pip install --upgrade --no-cache-dir git+https://github.com/rongardF/tvdatafeed.git

SIMBOL = "EURUSD"
TEMPORALIDAD = "1hour"
SIZE = 10
INCLUIR_PRECIO_ACTUAL = False
FOREX_BROKER = "OANDA"

#BINANCE OANDA

def obtener_velas(par=SIMBOL, intervalo=TEMPORALIDAD, barras=SIZE, incluir_precio_actual=False,forex_broker=FOREX_BROKER):
    # Inicializar TvDatafeed
    tv = TvDatafeed(username=None, password=None)
    
    # Mapear el intervalo a los valores de tvDatafeed
    interval_mapping = {
        '1min': Interval.in_1_minute,
        '3min': Interval.in_3_minute,
        '5min': Interval.in_5_minute,
        '15min': Interval.in_15_minute,
        '30min': Interval.in_30_minute,
        '1hour': Interval.in_1_hour,
        '2hour': Interval.in_2_hour,
        '4hour': Interval.in_4_hour,
        '1day': Interval.in_daily,
        '1week': Interval.in_weekly,
        '1month': Interval.in_monthly
    }
    
    # Determinar el exchange basado en el símbolo
    if "EURUSD" in par or any(x in par.upper() for x in ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']):
        exchange = forex_broker
    else:
        exchange = "BINANCE"  # Por defecto
    
    # Convertir intervalo
    tv_interval = interval_mapping.get(intervalo, Interval.in_1_hour)
    
    # Obtener datos
    data = tv.get_hist(symbol=par, exchange=exchange, 
                       interval=tv_interval, n_bars=barras + 1)
    
    # Obtener precio actual (último close)
    current_price = data['close'].iloc[-1]
    
    # Si no se incluye el precio actual, eliminar la última vela
    if not incluir_precio_actual:
        data = data.iloc[:-1]
    
    # Renombrar el índice si es necesario
    data = data.reset_index()
    
    # Asegurar que tenemos las columnas correctas
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    for col in required_columns:
        if col not in data.columns:
            raise ValueError(f"Columna {col} no encontrada en los datos")
    
    df_reversed = data.iloc[::-1].reset_index(drop=True)
    return df_reversed[required_columns], current_price




def calcular_pips(par, precio1, precio2):
    if "BTCUSDT" in par or "BTC-USDT" in par:
        multiplicador = 100  # Para BTCUSDT (generalmente 2 decimales)
    else:
        multiplicador = 100000
    
    return round(abs(precio1 - precio2) * multiplicador, 2)


if __name__ == "__main__":
    candles, current_price = obtener_velas()
    
    print(f"Precio actual: {current_price}")
    print(f"\nÚltimas 10 velas:")
    print(candles)
    
    if candles is not None and not candles.empty:
        print(f"\nPrimera vela de las últimas 10:")
        print(f"Open: {candles.iloc[0]['open']}")
        print(f"Close: {candles.iloc[0]['close']}")
        
        print(f"\nÚltima vela (la más reciente):")
        print(f"Open: {candles.iloc[-1]['open']}")
        print(f"Close: {candles.iloc[-1]['close']}")