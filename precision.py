"""
MÓDULO DE PRECISIÓN (15M y 5M)
"""
import time
from datetime import datetime
from data_metatrader5 import obtener_velas_mt5, calcular_pips
from config import direccion_global, PARES, MAX_PIPS_SL, RATIO_2VELAS, RATIO_1VELA
from notificacion import notificar_entrada

def buscar_entradas(intervalo):
    """Busca entradas en el intervalo especificado"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔎 Buscando entradas {intervalo}")
    
    señales = []
    
    for par in PARES:
        direccion = direccion_global[par]
        if not direccion:
            continue
            
        try:
            # Obtener velas
            data = obtener_velas_mt5(par, intervalo, 6)
            df = data[0]
            if df is None or len(df) < 4:
                continue
            
            # Buscar según dirección
            if direccion == "LONG":
                señal = buscar_patron_long(df, par, intervalo)
            elif direccion == "SHORT":
                señal = buscar_patron_short(df, par, intervalo)
                
            if señal:
                señales.append(señal)
                notificar_entrada(señal)
                print(f"  ✅ {par}: {señal['tipo']}")
                
        except Exception as e:
            print(f"  ❌ Error {par}: {e}")
    
    return señales

def buscar_patron_long(df, par, intervalo):
    """Busca patrón LONG en las últimas velas"""
    # Verificar que hay suficientes velas
    if len(df) < 3:
        return None
    
    # Tomar las últimas 3 velas
    vela1 = df.iloc[2]  # Antepenúltima
    vela2 = df.iloc[1]  # Penúltima
    vela3 = df.iloc[0]  # Última
    
    # Patrón 1: Última vela alcista y 2 anteriores bajistas
    if (vela1['close'] < vela1['open'] and  # Primera vela bajista
        vela2['close'] < vela2['open'] and  # Segunda vela bajista
        vela3['close'] > vela3['open']):    # Última vela alcista
        # Verificar que la última vela cierra arriba del máximo anterior
        if vela3['close'] >= vela2['high']:
            return crear_señal('LONG_2VELAS', par, intervalo, vela3, df, len(df)-1, RATIO_2VELAS)
    
    # Patrón 2: Última vela alcista y la anterior bajista
    elif (vela2['close'] < vela2['open'] and  # Vela anterior bajista
          vela3['close'] > vela3['open']):    # Última vela alcista
        # Verificar que la última vela cierra arriba del máximo de la vela anterior
        if vela3['close'] >= vela2['high']:
            return crear_señal('LONG_1VELA', par, intervalo, vela3, df, len(df)-1, RATIO_1VELA)
    
    return None

def buscar_patron_short(df, par, intervalo):
    """Busca patrón SHORT en las últimas velas"""
    # Verificar que hay suficientes velas
    if len(df) < 3:
        return None
    
    # Tomar las últimas 3 velas
    vela1 = df.iloc[2]  # Penúltima
    vela2 = df.iloc[1]  # Antepenúltima
    vela3 = df.iloc[0]  # Última
    
    # Patrón 1: Última vela bajista y 2 anteriores alcistas
    if (vela1['close'] > vela1['open'] and  # Primera vela alcista
        vela2['close'] > vela2['open'] and  # Segunda vela alcista
        vela3['close'] < vela3['open']):    # Última vela bajista
        
        # Verificar que la última vela cierra abajo del mínimo anterior
        if vela3['close'] <= vela2['low']:
            return crear_señal('SHORT_2VELAS', par, intervalo, vela3, df, len(df)-1, RATIO_2VELAS, False)
    
    # Patrón 2: Última vela bajista y la anterior alcista
    elif (vela2['close'] > vela2['open'] and  # Vela anterior alcista
          vela3['close'] < vela3['open']):    # Última vela bajista
        
        # Verificar que la última vela cierra abajo del mínimo de la vela anterior
        if vela3['close'] <= vela2['low']:
            return crear_señal('SHORT_1VELA', par, intervalo, vela3, df, len(df)-1, RATIO_1VELA, False)
    
    return None


def crear_señal(tipo, par, intervalo, vela_entrada, df, idx, ratio, es_long=True):
    """Crea señal con todos los parámetros"""
    entrada = vela_entrada['close']
    
    # Calcular SL
    if es_long:
        sl_precio = min(df.iloc[0]['low'],df.iloc[1]['low'],df.iloc[2]['low'])
    else:
        sl_precio = max(df.iloc[0]['high'],df.iloc[1]['high'],df.iloc[2]['high'])
        
    
    # ============ MODIFICACIÓN: AJUSTE SL PARA FOREX ============
    # Verificar si es un par Forex
    es_forex = any(major in par.upper() for major in [
        "EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD"
    ]) and any(divisa in par.upper() for divisa in [
        "EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD"
    ])
    
    # Aplicar restricción de máximo 0.00100 para pares Forex
    if es_forex:
        diferencia = abs(entrada - sl_precio)
        
        # Si la diferencia es mayor a 0.00100, ajustar el SL
        if diferencia > 0.00100:
            if es_long:
                sl_precio = entrada - 0.00100
            else:
                sl_precio = entrada + 0.00100
            
            print(f"⚠️  SL ajustado para {par} (Forex): Diferencia reducida a 0.00100")
    # ============ FIN DE MODIFICACIÓN ============
    
    # Ajustar SL por pips máximos (configuración general)
    pips = calcular_pips(par, entrada, sl_precio)
    if pips > MAX_PIPS_SL:
        ajuste = MAX_PIPS_SL / 100000
        if es_long:
            sl_precio = entrada - ajuste
        else:
            sl_precio = entrada + ajuste
        pips = MAX_PIPS_SL
    
    # Calcular TP
    riesgo = abs(entrada - sl_precio)
    if es_long:
        tp = entrada + (riesgo * ratio)
    else:
        tp = entrada - (riesgo * ratio)
    
    # Mostrar información de ajuste si fue necesario
    if es_forex and abs(entrada - sl_precio) == 0.00100:
        print(f"   📊 {par}: SL limitado a 0.00100 de diferencia ({abs(entrada - sl_precio):.5f})")
    
    return {
        'par': par,
        'tipo': tipo,
        'temporalidad': intervalo,
        'entrada': float(entrada),
        'sl': float(sl_precio),
        'tp': float(tp),
        'pips_sl': pips,
        'ratio': ratio
    }
