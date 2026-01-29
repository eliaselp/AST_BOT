"""
MÓDULO DE DIRECCIÓN (1H)
"""
import time
from datetime import datetime
from datos import obtener_velas, calcular_pips
from config import direccion_global, PARES
from notificacion import notificar_direccion

def verificar_direccion_1h():
    """Verifica dirección cada 1 hora"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Revisando dirección 1H")
    
    for par in PARES:
        try:
            # Obtener velas 1H
            df = obtener_velas(par, '1hour', 5)
            if df is None or len(df) < 3:
                continue
                
            # Últimas 3 velas
            vela = df.iloc[-1]
            vela1 = df.iloc[-2]
            vela2 = df.iloc[-3]
            
            # Condiciones
            es_alcista = vela['close'] > vela['open']
            es_bajista = vela['close'] < vela['open']
            
            max_anterior = max(vela1['high'], vela2['high'])
            min_anterior = min(vela1['low'], vela2['low'])
            
            # Determinar dirección
            nueva_direccion = None
            if es_alcista and vela['close'] >= max_anterior:
                nueva_direccion = "LONG"
            elif es_bajista and vela['close'] <= min_anterior:
                nueva_direccion = "SHORT"
            
            # Actualizar si hay cambio
            if nueva_direccion and direccion_global[par] != nueva_direccion:
                direccion_global[par] = nueva_direccion
                notificar_direccion(par, nueva_direccion, {
                    'close': vela['close'],
                    'open': vela['open'],
                    'high': vela['high'],
                    'low': vela['low']
                })
                print(f"  ✅ {par}: {nueva_direccion}")
                
        except Exception as e:
            print(f"  ❌ Error {par}: {e}")