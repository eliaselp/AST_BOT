import pandas as pd
import MetaTrader5 as mt5
import time
from datetime import datetime, timedelta
import pytz
import os
import numpy as np

def conectar_mt5(servidor=None, numero_cuenta=None, contraseña=None):
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
    fecha_inicio = datetime(ano_inicio, 1, 1, tzinfo=pytz.UTC)
    
    if fecha_fin is None:
        fecha_fin = datetime.now(pytz.UTC)
    elif isinstance(fecha_fin, str):
        fecha_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
    
    return fecha_inicio, fecha_fin

def obtener_datos_con_precios_reales(simbolo, timeframe, fecha_inicio, fecha_fin, timeout_segundos=30):
    print(f"\n📥 Descargando {simbolo} con precios Bid/Ask desde {fecha_inicio.strftime('%Y-%m-%d')} hasta {fecha_fin.strftime('%Y-%m-%d')}")
    
    symbol_info = mt5.symbol_info(simbolo)
    if symbol_info is None:
        print(f"❌ El símbolo {simbolo} no existe")
        return None
    
    if not symbol_info.visible:
        print(f"🔄 Activando símbolo {simbolo}...")
        if not mt5.symbol_select(simbolo, True):
            print(f"❌ No se pudo activar {simbolo}")
            return None
    
    digits = symbol_info.digits
    print(f"   Dígitos del símbolo: {digits}")
    
    todos_los_datos = []
    fecha_actual = fecha_inicio
    
    timeframe_segundos = {
        mt5.TIMEFRAME_M1: 60,
        mt5.TIMEFRAME_M5: 300,
        mt5.TIMEFRAME_M15: 900,
        mt5.TIMEFRAME_M30: 1800,
        mt5.TIMEFRAME_H1: 3600,
        mt5.TIMEFRAME_H4: 14400,
        mt5.TIMEFRAME_D1: 86400,
        mt5.TIMEFRAME_W1: 604800,
        mt5.TIMEFRAME_MN1: 2592000
    }
    
    segundos_por_vela = timeframe_segundos.get(timeframe, 60)
    
    while fecha_actual < fecha_fin:
        try:
            fecha_bloque_fin = min(fecha_actual + timedelta(days=30), fecha_fin)
            
            print(f"   Procesando bloque: {fecha_actual.strftime('%Y-%m-%d')} a {fecha_bloque_fin.strftime('%Y-%m-%d')}")
            
            ticks = mt5.copy_ticks_range(simbolo, fecha_actual, fecha_bloque_fin, mt5.COPY_TICKS_ALL)
            
            if ticks is not None and len(ticks) > 0:
                df_ticks = pd.DataFrame(ticks)
                df_ticks['time'] = pd.to_datetime(df_ticks['time'], unit='s')
                
                columnas_disponibles = df_ticks.columns.tolist()
                print(f"      Columnas disponibles en ticks: {columnas_disponibles}")
                
                df_ticks['time_group'] = (df_ticks['time'].astype(np.int64) // (segundos_por_vela * 10**9)) * (segundos_por_vela * 10**9)
                df_ticks['time_group'] = pd.to_datetime(df_ticks['time_group'])
                
                velas = []
                
                for time_group, grupo in df_ticks.groupby('time_group'):
                    if len(grupo) > 0:
                        if 'bid' in grupo.columns and 'ask' in grupo.columns:
                            bids = grupo['bid']
                            asks = grupo['ask']
                            
                            vela = {
                                'time': time_group,
                                'bid_open': bids.iloc[0],
                                'bid_high': bids.max(),
                                'bid_low': bids.min(),
                                'bid_close': bids.iloc[-1],
                                'ask_open': asks.iloc[0],
                                'ask_high': asks.max(),
                                'ask_low': asks.min(),
                                'ask_close': asks.iloc[-1],
                                'tick_volume': len(grupo),
                                'real_volume': grupo['volume'].sum() if 'volume' in grupo.columns else 0,
                                'spread_mean': (grupo['ask'] - grupo['bid']).mean()
                            }
                            velas.append(vela)
                        
                        elif 'last' in grupo.columns:
                            last = grupo['last']
                            
                            spread_estimado = symbol_info.spread / (10 ** digits) if hasattr(symbol_info, 'spread') else 0.0001
                            
                            vela = {
                                'time': time_group,
                                'bid_open': last.iloc[0] - spread_estimado/2,
                                'bid_high': last.max() - spread_estimado/2,
                                'bid_low': last.min() - spread_estimado/2,
                                'bid_close': last.iloc[-1] - spread_estimado/2,
                                'ask_open': last.iloc[0] + spread_estimado/2,
                                'ask_high': last.max() + spread_estimado/2,
                                'ask_low': last.min() + spread_estimado/2,
                                'ask_close': last.iloc[-1] + spread_estimado/2,
                                'tick_volume': len(grupo),
                                'real_volume': grupo['volume'].sum() if 'volume' in grupo.columns else 0,
                                'spread_mean': spread_estimado
                            }
                            velas.append(vela)
                        
                        elif 'flag' in grupo.columns:
                            try:
                                bids_flag = grupo[grupo['flag'] & mt5.TICK_FLAG_BUY == 0]['bid'] if 'bid' in grupo.columns else None
                                asks_flag = grupo[grupo['flag'] & mt5.TICK_FLAG_SELL == 0]['ask'] if 'ask' in grupo.columns else None
                                
                                if bids_flag is not None and len(bids_flag) > 0:
                                    bids = bids_flag
                                    asks = asks_flag if asks_flag is not None and len(asks_flag) > 0 else bids_flag
                                else:
                                    bids = grupo['bid'] if 'bid' in grupo.columns else grupo['last']
                                    asks = grupo['ask'] if 'ask' in grupo.columns else grupo['last']
                                
                                vela = {
                                    'time': time_group,
                                    'bid_open': bids.iloc[0],
                                    'bid_high': bids.max(),
                                    'bid_low': bids.min(),
                                    'bid_close': bids.iloc[-1],
                                    'ask_open': asks.iloc[0],
                                    'ask_high': asks.max(),
                                    'ask_low': asks.min(),
                                    'ask_close': asks.iloc[-1],
                                    'tick_volume': len(grupo),
                                    'real_volume': grupo['volume'].sum() if 'volume' in grupo.columns else 0,
                                    'spread_mean': (asks - bids).mean() if 'ask' in grupo.columns and 'bid' in grupo.columns else 0
                                }
                                velas.append(vela)
                            except:
                                if 'bid' in grupo.columns and 'ask' in grupo.columns:
                                    bids = grupo['bid']
                                    asks = grupo['ask']
                                else:
                                    bids = asks = grupo['last'] if 'last' in grupo.columns else grupo.iloc[:, 0]
                                
                                vela = {
                                    'time': time_group,
                                    'bid_open': bids.iloc[0],
                                    'bid_high': bids.max(),
                                    'bid_low': bids.min(),
                                    'bid_close': bids.iloc[-1],
                                    'ask_open': asks.iloc[0],
                                    'ask_high': asks.max(),
                                    'ask_low': asks.min(),
                                    'ask_close': asks.iloc[-1],
                                    'tick_volume': len(grupo),
                                    'real_volume': grupo['volume'].sum() if 'volume' in grupo.columns else 0,
                                    'spread_mean': (asks - bids).mean() if 'ask' in grupo.columns and 'bid' in grupo.columns else 0
                                }
                                velas.append(vela)
                
                if velas:
                    df_bloque = pd.DataFrame(velas)
                    todos_los_datos.append(df_bloque)
                    print(f"   ✅ {len(df_bloque)} velas generadas desde {len(ticks)} ticks")
                else:
                    print(f"   ⚠️ No se pudieron generar velas desde los ticks")
            else:
                print(f"   ⚠️ No hay ticks para este bloque, usando OHLCV estándar")
                rates = mt5.copy_rates_range(simbolo, timeframe, fecha_actual, fecha_bloque_fin)
                if rates is not None and len(rates) > 0:
                    df_rates = pd.DataFrame(rates)
                    df_rates['time'] = pd.to_datetime(df_rates['time'], unit='s')
                    
                    spread_valor = df_rates['spread'] / (10 ** digits)
                    
                    df_rates['bid_open'] = df_rates['open'] - spread_valor / 2
                    df_rates['bid_high'] = df_rates['high'] - spread_valor / 2
                    df_rates['bid_low'] = df_rates['low'] - spread_valor / 2
                    df_rates['bid_close'] = df_rates['close'] - spread_valor / 2
                    
                    df_rates['ask_open'] = df_rates['open'] + spread_valor / 2
                    df_rates['ask_high'] = df_rates['high'] + spread_valor / 2
                    df_rates['ask_low'] = df_rates['low'] + spread_valor / 2
                    df_rates['ask_close'] = df_rates['close'] + spread_valor / 2
                    
                    df_rates['spread_mean'] = spread_valor
                    
                    todos_los_datos.append(df_rates)
                    print(f"   ✅ {len(df_rates)} velas obtenidas (estimadas)")
            
            fecha_actual = fecha_bloque_fin
            time.sleep(0.5)
            
        except Exception as e:
            print(f"   ❌ Error en bloque: {str(e)}")
            import traceback
            traceback.print_exc()
            time.sleep(2)
            continue
    
    if todos_los_datos:
        df_final = pd.concat(todos_los_datos, ignore_index=True)
        df_final = df_final.drop_duplicates(subset=['time']).sort_values('time')
        df_final.set_index('time', inplace=True)
        
        if all(col in df_final.columns for col in ['bid_open', 'ask_open']):
            df_final['open'] = (df_final['bid_open'] + df_final['ask_open']) / 2
            df_final['high'] = (df_final['bid_high'] + df_final['ask_high']) / 2
            df_final['low'] = (df_final['bid_low'] + df_final['ask_low']) / 2
            df_final['close'] = (df_final['bid_close'] + df_final['ask_close']) / 2
        
        if 'ask_close' in df_final.columns and 'bid_close' in df_final.columns:
            df_final['spread_points'] = (df_final['ask_close'] - df_final['bid_close']) * (10 ** digits)
            df_final['spread_price'] = df_final['ask_close'] - df_final['bid_close']
        
        if 'real_volume' in df_final.columns and 'tick_volume' in df_final.columns:
            df_final['volume'] = df_final['real_volume'].where(df_final['real_volume'] > 0, df_final['tick_volume'])
        elif 'tick_volume' in df_final.columns:
            df_final['volume'] = df_final['tick_volume']
        
        columnas_posibles = [
            'open', 'high', 'low', 'close',
            'bid_open', 'bid_high', 'bid_low', 'bid_close',
            'ask_open', 'ask_high', 'ask_low', 'ask_close',
            'volume', 'tick_volume', 'real_volume',
            'spread_points', 'spread_price', 'spread_mean'
        ]
        
        columnas_existentes = [col for col in columnas_posibles if col in df_final.columns]
        df_final = df_final[columnas_existentes]
        
        return df_final
    
    return None

def exportar_ohlcv_a_csv(simbolo, temporalidad, ano_inicio=2006, fecha_fin=None, 
                         servidor=None, numero_cuenta=None, contraseña=None, 
                         nombre_archivo=None, usar_precios_reales=True):
    
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
    print(f"📊 EXPORTADOR OHLCV CON PRECIOS BID/ASK")
    print(f"{'='*60}")
    print(f"Símbolo: {simbolo}")
    print(f"Temporalidad: {temporalidad}")
    print(f"Año inicio: {ano_inicio}")
    print(f"Usar precios reales: {usar_precios_reales}")
    
    if not conectar_mt5(servidor, numero_cuenta, contraseña):
        print("❌ No se pudo conectar a MT5")
        return None
    
    try:
        fecha_inicio, fecha_fin_dt = obtener_rango_fechas(ano_inicio, fecha_fin)
        print(f"Rango: {fecha_inicio.strftime('%Y-%m-%d')} a {fecha_fin_dt.strftime('%Y-%m-%d')}")
        
        if usar_precios_reales:
            df = obtener_datos_con_precios_reales(
                simbolo=simbolo,
                timeframe=timeframes[temporalidad],
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin_dt
            )
        else:
            print("⚠️ Usando modo legacy sin precios Bid/Ask")
            return None
        
        if df is None or len(df) == 0:
            print(f"❌ No se obtuvieron datos para {simbolo}")
            return None
        
        print(f"\n✅ Datos obtenidos: {len(df)} velas")
        print(f"   Rango: {df.index[0].strftime('%Y-%m-%d %H:%M')} a {df.index[-1].strftime('%Y-%m-%d %H:%M')}")
        
        if nombre_archivo is None:
            fecha_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            nombre_archivo = f"{simbolo}_{temporalidad}_{ano_inicio}_a_{fecha_fin_dt.strftime('%Y%m%d')}_bidask.csv"
        
        df.to_csv(nombre_archivo)
        print(f"\n💾 Datos guardados en: {nombre_archivo}")
        print(f"   Tamaño del archivo: {os.path.getsize(nombre_archivo) / (1024*1024):.2f} MB")
        
        print(f"\n📋 Primeras 5 filas:")
        print(df.head())
        
        print(f"\n📋 Últimas 5 filas:")
        print(df.tail())
        
        if 'spread_price' in df.columns:
            print(f"\n📊 Estadísticas de Spreads:")
            print(f"   Spread medio: {df['spread_price'].mean():.5f}")
            print(f"   Spread máximo: {df['spread_price'].max():.5f}")
            print(f"   Spread mínimo: {df['spread_price'].min():.5f}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error durante la exportación: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        mt5.shutdown()
        print("\n🔄 Conexión MT5 cerrada")

def main():
    print("🚀 EXPORTADOR DE DATOS OHLCV CON PRECIOS BID/ASK")
    print("="*60)
    
    CONFIG = {
        'servidor': None,
        'numero_cuenta': None,
        'contraseña': None,
    }
    
    SIMBOLO = "EURUSD"
    TEMPORALIDAD = "15min"
    ANO_INICIO = 2000
    FECHA_FIN = None
    USAR_PRECIOS_REALES = True
    
    df = exportar_ohlcv_a_csv(
        simbolo=SIMBOLO,
        temporalidad=TEMPORALIDAD,
        ano_inicio=ANO_INICIO,
        fecha_fin=FECHA_FIN,
        servidor=CONFIG['servidor'],
        numero_cuenta=CONFIG['numero_cuenta'],
        contraseña=CONFIG['contraseña'],
        usar_precios_reales=USAR_PRECIOS_REALES
    )
    
    if df is not None:
        print(f"\n{'='*60}")
        print("✅ EXPORTACIÓN COMPLETADA EXITOSAMENTE")
        print(f"{'='*60}")
        
        print(f"\n📋 Columnas disponibles:")
        for col in df.columns:
            print(f"   - {col}")

if __name__ == "__main__":
    main()
