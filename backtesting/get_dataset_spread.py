import pandas as pd
import MetaTrader5 as mt5
import time
from datetime import datetime, timedelta
import pytz
import os
import numpy as np

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
    """
    fecha_inicio = datetime(ano_inicio, 1, 1, tzinfo=pytz.UTC)
    
    if fecha_fin is None:
        fecha_fin = datetime.now(pytz.UTC)
    elif isinstance(fecha_fin, str):
        fecha_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
    
    return fecha_inicio, fecha_fin

def obtener_datos_con_precios_reales(simbolo, timeframe, fecha_inicio, fecha_fin, timeout_segundos=30):
    """
    Obtiene datos OHLCV con precios reales de compra (Bid) y venta (Ask)
    """
    print(f"\n📥 Descargando {simbolo} con precios Bid/Ask desde {fecha_inicio.strftime('%Y-%m-%d')} hasta {fecha_fin.strftime('%Y-%m-%d')}")
    
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
    
    # Obtener información del símbolo para el punto decimal
    digits = symbol_info.digits
    print(f"   Dígitos del símbolo: {digits}")
    
    # Obtener datos en bloques
    todos_los_datos = []
    fecha_actual = fecha_inicio
    
    # Mapeo de timeframes a segundos para agrupar ticks
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
            fecha_bloque_fin = min(fecha_actual + timedelta(days=30), fecha_fin)  # Bloques de 30 días para ticks
            
            print(f"   Procesando bloque: {fecha_actual.strftime('%Y-%m-%d')} a {fecha_bloque_fin.strftime('%Y-%m-%d')}")
            
            # Obtener ticks para el bloque
            ticks = mt5.copy_ticks_range(simbolo, fecha_actual, fecha_bloque_fin, mt5.COPY_TICKS_ALL)
            
            if ticks is not None and len(ticks) > 0:
                df_ticks = pd.DataFrame(ticks)
                df_ticks['time'] = pd.to_datetime(df_ticks['time'], unit='s')
                
                # Crear columna de tiempo para agrupar por vela
                df_ticks['time_group'] = (df_ticks['time'].astype(np.int64) // (segundos_por_vela * 10**9)) * (segundos_por_vela * 10**9)
                df_ticks['time_group'] = pd.to_datetime(df_ticks['time_group'])
                
                # Agrupar por período para crear velas
                velas = []
                
                for time_group, grupo in df_ticks.groupby('time_group'):
                    if len(grupo) > 0:
                        # Precios Bid (compra) - cuando se vende al broker
                        bids = grupo[grupo['flag'] & mt5.TICK_FLAG_BUY == 0]['bid'] if 'bid' in grupo.columns else None
                        # Precios Ask (venta) - cuando se compra al broker
                        asks = grupo[grupo['flag'] & mt5.TICK_FLAG_SELL == 0]['ask'] if 'ask' in grupo.columns else None
                        
                        # Si no tenemos bid/ask separados, usamos el precio genérico
                        if (bids is None or len(bids) == 0) and 'last' in grupo.columns:
                            bids = asks = grupo['last']
                        
                        if bids is not None and len(bids) > 0:
                            vela = {
                                'time': time_group,
                                'bid_open': bids.iloc[0],
                                'bid_high': bids.max(),
                                'bid_low': bids.min(),
                                'bid_close': bids.iloc[-1],
                                'ask_open': asks.iloc[0] if asks is not None and len(asks) > 0 else bids.iloc[0],
                                'ask_high': asks.max() if asks is not None and len(asks) > 0 else bids.max(),
                                'ask_low': asks.min() if asks is not None and len(asks) > 0 else bids.min(),
                                'ask_close': asks.iloc[-1] if asks is not None and len(asks) > 0 else bids.iloc[-1],
                                'tick_volume': len(grupo),
                                'real_volume': grupo['volume'].sum() if 'volume' in grupo.columns else 0,
                                'spread_mean': (grupo['ask'] - grupo['bid']).mean() if 'ask' in grupo.columns and 'bid' in grupo.columns else 0
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
                # Fallback a OHLCV estándar
                rates = mt5.copy_rates_range(simbolo, timeframe, fecha_actual, fecha_bloque_fin)
                if rates is not None and len(rates) > 0:
                    df_rates = pd.DataFrame(rates)
                    df_rates['time'] = pd.to_datetime(df_rates['time'], unit='s')
                    
                    # Estimar bid/ask desde OHLCV
                    df_rates['bid_open'] = df_rates['open'] - df_rates['spread'] / (10 ** digits) / 2
                    df_rates['bid_high'] = df_rates['high'] - df_rates['spread'] / (10 ** digits) / 2
                    df_rates['bid_low'] = df_rates['low'] - df_rates['spread'] / (10 ** digits) / 2
                    df_rates['bid_close'] = df_rates['close'] - df_rates['spread'] / (10 ** digits) / 2
                    
                    df_rates['ask_open'] = df_rates['open'] + df_rates['spread'] / (10 ** digits) / 2
                    df_rates['ask_high'] = df_rates['high'] + df_rates['spread'] / (10 ** digits) / 2
                    df_rates['ask_low'] = df_rates['low'] + df_rates['spread'] / (10 ** digits) / 2
                    df_rates['ask_close'] = df_rates['close'] + df_rates['spread'] / (10 ** digits) / 2
                    
                    df_rates['spread_mean'] = df_rates['spread'] / (10 ** digits)
                    
                    todos_los_datos.append(df_rates)
                    print(f"   ✅ {len(df_rates)} velas obtenidas (estimadas)")
            
            fecha_actual = fecha_bloque_fin
            time.sleep(0.5)
            
        except Exception as e:
            print(f"   ❌ Error en bloque: {str(e)}")
            time.sleep(2)
            continue
    
    # Combinar todos los bloques
    if todos_los_datos:
        df_final = pd.concat(todos_los_datos, ignore_index=True)
        df_final = df_final.drop_duplicates(subset=['time']).sort_values('time')
        df_final.set_index('time', inplace=True)
        
        # Calcular precios medios y spreads
        df_final['open'] = (df_final['bid_open'] + df_final['ask_open']) / 2
        df_final['high'] = (df_final['bid_high'] + df_final['ask_high']) / 2
        df_final['low'] = (df_final['bid_low'] + df_final['ask_low']) / 2
        df_final['close'] = (df_final['bid_close'] + df_final['ask_close']) / 2
        
        # Spread en puntos y en precio
        df_final['spread_points'] = (df_final['ask_close'] - df_final['bid_close']) * (10 ** digits)
        df_final['spread_price'] = df_final['ask_close'] - df_final['bid_close']
        
        # Volumen
        df_final['volume'] = df_final['real_volume'].where(df_final['real_volume'] > 0, df_final['tick_volume'])
        
        # Reordenar columnas
        columnas_ordenadas = [
            'open', 'high', 'low', 'close',
            'bid_open', 'bid_high', 'bid_low', 'bid_close',
            'ask_open', 'ask_high', 'ask_low', 'ask_close',
            'volume', 'tick_volume', 'real_volume',
            'spread_points', 'spread_price', 'spread_mean'
        ]
        
        # Solo mantener columnas que existen
        columnas_existentes = [col for col in columnas_ordenadas if col in df_final.columns]
        df_final = df_final[columnas_existentes]
        
        return df_final
    
    return None

def exportar_ohlcv_a_csv(simbolo, temporalidad, ano_inicio=2006, fecha_fin=None, 
                         servidor=None, numero_cuenta=None, contraseña=None, 
                         nombre_archivo=None, usar_precios_reales=True):
    """
    Función principal para exportar datos OHLCV a CSV con precios Bid/Ask
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
    print(f"📊 EXPORTADOR OHLCV CON PRECIOS BID/ASK")
    print(f"{'='*60}")
    print(f"Símbolo: {simbolo}")
    print(f"Temporalidad: {temporalidad}")
    print(f"Año inicio: {ano_inicio}")
    print(f"Usar precios reales: {usar_precios_reales}")
    
    # Conectar a MT5
    if not conectar_mt5(servidor, numero_cuenta, contraseña):
        print("❌ No se pudo conectar a MT5")
        return None
    
    try:
        # Calcular fechas
        fecha_inicio, fecha_fin_dt = obtener_rango_fechas(ano_inicio, fecha_fin)
        print(f"Rango: {fecha_inicio.strftime('%Y-%m-%d')} a {fecha_fin_dt.strftime('%Y-%m-%d')}")
        
        # Obtener datos con precios reales
        if usar_precios_reales:
            df = obtener_datos_con_precios_reales(
                simbolo=simbolo,
                timeframe=timeframes[temporalidad],
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin_dt
            )
        else:
            # Usar la función anterior si no se quieren precios reales
            print("⚠️ Usando modo legacy sin precios Bid/Ask")
            # Aquí iría tu función anterior obtener_datos_ohlcv
            return None
        
        if df is None or len(df) == 0:
            print(f"❌ No se obtuvieron datos para {simbolo}")
            return None
        
        print(f"\n✅ Datos obtenidos: {len(df)} velas")
        print(f"   Rango: {df.index[0].strftime('%Y-%m-%d %H:%M')} a {df.index[-1].strftime('%Y-%m-%d %H:%M')}")
        
        # Crear nombre de archivo si no se especificó
        if nombre_archivo is None:
            fecha_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            nombre_archivo = f"{simbolo}_{temporalidad}_{ano_inicio}_a_{fecha_fin_dt.strftime('%Y%m%d')}_bidask.csv"
        
        # Exportar a CSV
        df.to_csv(nombre_archivo)
        print(f"\n💾 Datos guardados en: {nombre_archivo}")
        print(f"   Tamaño del archivo: {os.path.getsize(nombre_archivo) / (1024*1024):.2f} MB")
        
        # Mostrar primeras filas
        print(f"\n📋 Primeras 5 filas:")
        print(df.head())
        
        print(f"\n📋 Últimas 5 filas:")
        print(df.tail())
        
        # Mostrar estadísticas de spreads
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
    """
    Función principal con ejemplos de uso
    """
    print("🚀 EXPORTADOR DE DATOS OHLCV CON PRECIOS BID/ASK")
    print("="*60)
    
    # ============================================
    # CONFIGURACIÓN DEL USUARIO
    # ============================================
    
    # Configuración de la cuenta
    CONFIG = {
        'servidor': None,
        'numero_cuenta': None,
        'contraseña': None,
    }
    
    # Parámetros de descarga
    SIMBOLO = "EURUSD"
    TEMPORALIDAD = "15min"  # 1min, 5min, 15min, 30min, 1hour, 4hour, 1day, 1week, 1month
    ANO_INICIO = 2000
    FECHA_FIN = None
    USAR_PRECIOS_REALES = True  # True para obtener Bid/Ask reales, False para solo OHLCV
    
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
        contraseña=CONFIG['contraseña'],
        usar_precios_reales=USAR_PRECIOS_REALES
    )
    
    if df is not None:
        print(f"\n{'='*60}")
        print("✅ EXPORTACIÓN COMPLETADA EXITOSAMENTE")
        print(f"{'='*60}")
        
        # Mostrar columnas disponibles
        print(f"\n📋 Columnas disponibles:")
        for col in df.columns:
            print(f"   - {col}")

if __name__ == "__main__":
    main()