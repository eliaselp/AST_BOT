"""
MÓDULO DE ESTRATEGIA DE QUIEBRE (Basada en backtest)
Detecta cuando una vela quiebra el máximo/mínimo de la vela anterior
con la misma dirección que la vela anterior
"""
from datetime import datetime
from data_metatrader5 import obtener_velas_mt5, calcular_pips
import config
import pandas as pd
# ============ CONFIGURACIÓN DE LA ESTRATEGIA ============
CONFIG_ESTRATEGIA = {
    'temporalidad': config.temporalidad_operacion,           # Temporalidad por defecto
    'rr_ratio': config.rr_ratio                  # Ratio Risk/Reward (1:2)
}
# ========================================================

def identificar_tipo_vela(vela):
    """Identifica si una vela es LONG o SHORT"""
    return 'LONG' if vela['close'] > vela['open'] else 'SHORT'

def buscar_entradas_quiebre(par, cuenta,intervalo=None):
    
    """
    Busca entradas según estrategia de quiebre
    Si no se especifica intervalo, usa el de configuración
    """
    if not cuenta:
        print("❌ Error: No se proporcionó configuración de cuenta")
        return None
    
    if intervalo is None:
        intervalo = CONFIG_ESTRATEGIA['temporalidad']
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔎 Buscando entradas ESTRATEGIA QUIEBRE {intervalo}")
    
    try:
        # Obtener velas (necesitamos al menos 2 velas para la estrategia)
        df, precio_actual = obtener_velas_mt5(
            par, 
            intervalo, 
            3,  # Pedimos 3 velas para tener contexto
            cuenta['credenciales']['numero_cuenta'],
            cuenta['credenciales']['servidor'], 
            cuenta['credenciales']['contraseña'],
            ruta=None
        )
        
        if df is None or len(df) < 2:
            return None
        
        # La última vela (índice 0) es la más reciente finalizada
        vela_anterior = df.iloc[1]  # Vela anterior (penúltima)
        vela_actual = df.iloc[0]    # Vela actual (última finalizada)
        
        # Verificar condiciones LONG
        df, precio_actual = obtener_velas_mt5(
            par, 
            config.temporalidad_direccion, 
            3,  # Pedimos 3 velas para tener contexto
            cuenta['credenciales']['numero_cuenta'],
            cuenta['credenciales']['servidor'], 
            cuenta['credenciales']['contraseña'],
            ruta=None,
            incluir_precio_actual=True
        )
        if precio_actual > df.iloc[0]['open']:
            señal_long = verificar_condicion_long(par, intervalo, vela_anterior, vela_actual)
            if señal_long:
                print(f"  ✅ {par}: LONG - Entrada: {señal_long['entrada']:.5f}")
                return señal_long
            
            
        if precio_actual < df.iloc[0]['open']:
            # Verificar condiciones SHORT
            señal_short = verificar_condicion_short(par, intervalo, vela_anterior, vela_actual)
            if señal_short:
                print(f"  ✅ {par}: SHORT - Entrada: {señal_short['entrada']:.5f}")
                return señal_short
        
        return None
            
    except Exception as e:
        print(f"  ❌ Error {par}: {e}")
    return None

def verificar_condicion_long(par, intervalo, vela_anterior, vela_actual):
    
    rango = vela_actual['high'] - vela_actual['low']
    if rango <= 0 or pd.isna(rango):
        return None
    
    cuerpo = abs(vela_actual['close'] - vela_actual['open'])
    body_ratio = cuerpo / rango
    if (vela_actual['close'] > vela_anterior['high'] and
        body_ratio >= config.MIN_BODY_RATIO and
        (vela_actual['high'] - vela_actual['close']) / rango <= config.MAX_WICK_RATIO and
        vela_actual['volume'] > vela_anterior['volume'] * config.VOLUME_MULTIPLIER):
    
        return crear_señal_quiebre(
            tipo='LONG',
            par=par,
            intervalo=intervalo,
            vela_actual=vela_actual,
            vela_anterior=vela_anterior
        )    
    return None

def verificar_condicion_short(par, intervalo, vela_anterior, vela_actual):
    rango = vela_actual['high'] - vela_actual['low']
    if rango <= 0 or pd.isna(rango):
        return None
    
    cuerpo = abs(vela_actual['close'] - vela_actual['open'])
    body_ratio = cuerpo / rango
    if (vela_actual['close'] < vela_anterior['low'] and
        body_ratio >= config.MIN_BODY_RATIO and
        (vela_actual['close'] - vela_actual['low']) / rango <= config.MAX_WICK_RATIO and
        vela_actual['volume'] > vela_anterior['volume'] * config.VOLUME_MULTIPLIER):

        return crear_señal_quiebre(
            tipo='SHORT',
            par=par,
            intervalo=intervalo,
            vela_actual=vela_actual,
            vela_anterior=vela_anterior
        )
    
    return None

def crear_señal_quiebre(tipo, par, intervalo, vela_actual, vela_anterior):
    """
    Crea señal con el mismo formato que el primer script
    """
    # Punto de entrada: cierre de la vela actual
    entrada = vela_actual['close']
    buffer = config.SL_BUFFER * config.PIP_VALUE
    
    
    # Calcular SL basado en la vela anterior
    if tipo == 'LONG':
        sl_precio = vela_anterior['low'] - buffer  # SL en mínimo de vela anterior
    else:  # SHORT
        sl_precio = vela_anterior['high'] + buffer  # SL en máximo de vela anterior
    
    # Obtener ratio de configuración
    ratio = CONFIG_ESTRATEGIA['rr_ratio']
    
    # Calcular riesgo
    riesgo = abs(entrada - sl_precio)
    
    # Calcular TP
    if tipo == 'LONG':
        tp = entrada + (riesgo * ratio)
    else:
        tp = entrada - (riesgo * ratio)
    
    # Calcular pips
    pips_sl = calcular_pips(par, entrada, sl_precio)
    
    # Mostrar información de la señal
    print(f"   📊 {par}: {tipo} - SL: {sl_precio:.5f} ({pips_sl:.1f} pips) - TP: {tp:.5f}")
    
    return {
        'par': par,
        'tipo': tipo,
        'temporalidad': intervalo,
        'entrada': float(entrada),
        'sl': float(sl_precio),
        'tp': float(tp),
        'pips_sl': float(pips_sl),
        'ratio': float(ratio)
    }
