"""
MÓDULO DE ESTRATEGIA DE QUIEBRE (Basada en backtest)
Detecta cuando una vela quiebra el máximo/mínimo de la vela anterior
con la misma dirección que la vela anterior
"""
from datetime import datetime
from data_metatrader5 import obtener_velas_mt5, calcular_pips
import config
# ============ CONFIGURACIÓN DE LA ESTRATEGIA ============
CONFIG_ESTRATEGIA = {
    'temporalidad': config.temporalidad,           # Temporalidad por defecto
    'rr_ratio': config.rr_ratio                  # Ratio Risk/Reward (1:2)
}
# ========================================================

def identificar_tipo_vela(vela):
    """Identifica si una vela es LONG o SHORT"""
    return 'LONG' if vela['close'] > vela['open'] else 'SHORT'

def buscar_entradas_quiebre(par, cuenta, intervalo=None ):
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
            cuenta['numero_cuenta'],
            cuenta['servidor'], 
            cuenta['contraseña']
        )
        
        if df is None or len(df) < 2:
            return None
        
        # La última vela (índice 0) es la más reciente finalizada
        vela_anterior = df.iloc[1]  # Vela anterior (penúltima)
        vela_actual = df.iloc[0]    # Vela actual (última finalizada)
        
        # Verificar condiciones LONG
        señal_long = verificar_condicion_long(par, intervalo, vela_anterior, vela_actual)
        if señal_long:
            print(f"  ✅ {par}: LONG - Entrada: {señal_long['entrada']:.5f}")
            return señal_long
            
            
        
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
    """
    Verifica si se cumple condición para LONG:
    - Vela anterior alcista
    - Vela actual quiebra al alza (cierre > máximo anterior)
    - Vela actual mantiene soporte (mínimo > mínimo anterior)
    """
    
    # Condiciones LONG
    cond2 = vela_actual['close'] > vela_anterior['high']  # Quiebre de máximo
    cond3 = vela_actual['low'] > vela_anterior['low']  # Mantiene soporte
    
    if cond2 and cond3:
        return crear_señal_quiebre(
            tipo='LONG',
            par=par,
            intervalo=intervalo,
            vela_actual=vela_actual,
            vela_anterior=vela_anterior
        )
    
    return None

def verificar_condicion_short(par, intervalo, vela_anterior, vela_actual):
    """
    Verifica si se cumple condición para SHORT:
    - Vela anterior bajista
    - Vela actual quiebra a la baja (cierre < mínimo anterior)
    - Vela actual mantiene resistencia (máximo < máximo anterior)
    """
    # Identificar tipo de vela anterior
    cond2 = vela_actual['close'] < vela_anterior['low']  # Quiebre de mínimo
    cond3 = vela_actual['high'] < vela_anterior['high']  # Mantiene resistencia
    
    if cond2 and cond3:
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
    
    # Calcular SL basado en la vela anterior
    if tipo == 'LONG':
        sl_precio = vela_anterior['low']  # SL en mínimo de vela anterior
    else:  # SHORT
        sl_precio = vela_anterior['high']  # SL en máximo de vela anterior
    
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
