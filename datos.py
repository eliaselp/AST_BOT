import pandas as pd
from client import RequestsClient

ACCESS_ID = "47EF17480ECE42F383FF0D1C9F53DA90"
SECRET_KEY = "A7B9861BDCD88BF07930864E587179553BB603F6E5E95703"
SIMBOL = "BTCUSDT"
TEMPORALIDAD = "1hour"
SIZE = 10
INCLUIR_PRECIO_ACTUAL = False

def obtener_velas(par=SIMBOL, intervalo=TEMPORALIDAD, barras=SIZE, incluir_precio_actual=False):
    client = RequestsClient(access_id=ACCESS_ID, secret_key=SECRET_KEY)
    
    request_path = "/futures/kline"
    params = {
        "market": par,
        "limit": barras + 1,
        "period": intervalo
    }
    
    response = client.request(
        "GET",
        "{url}{request_path}".format(url=client.url, request_path=request_path),
        params=params,
    )
    
    data = response.json().get("data")
    ohlcv_df = pd.DataFrame(data)
    
    ohlcv_df['close'] = pd.to_numeric(ohlcv_df['close'])
    ohlcv_df['high'] = pd.to_numeric(ohlcv_df['high'])
    ohlcv_df['low'] = pd.to_numeric(ohlcv_df['low'])
    ohlcv_df['open'] = pd.to_numeric(ohlcv_df['open'])
    ohlcv_df['volume'] = pd.to_numeric(ohlcv_df['volume'])
    
    current_price = ohlcv_df['close'].iloc[-1]
    
    ohlcv_df = ohlcv_df.drop('market', axis=1)
    ohlcv_df = ohlcv_df.drop('created_at', axis=1)
    
    if not incluir_precio_actual:
        ohlcv_df = ohlcv_df.drop(ohlcv_df.index[-1])
    
    return ohlcv_df, current_price

def calcular_pips(par, precio1, precio2):
    multiplicador = 100 if "JPY" in par else 10000
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