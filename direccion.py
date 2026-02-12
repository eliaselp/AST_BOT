"""
MÓDULO DE DIRECCIÓN (1H) - VENTANA DESLIZANTE
"""
import time
from datetime import datetime
from data_metatrader5 import obtener_velas_mt5
from config import direccion_global, PARES, actualizar_direccion_global, CUENTA_PRINCIPAL
from notificacion import notificar_direccion

def verificar_direccion(temporalidad):
    """Verifica dirección cada 1 hora con ventana deslizante de 3 velas"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Revisando dirección {temporalidad} (Ventana: 3 velas)")
    
    for par in PARES:
        try:
            # Obtener más datos para asegurar ventana deslizante
            data = obtener_velas_mt5(par,temporalidad, 50, CUENTA_PRINCIPAL['numero_cuenta'], CUENTA_PRINCIPAL['servidor'], CUENTA_PRINCIPAL['contraseña'])  # Más datos para analizar
            df = data[0]
            
            if df is None or len(df) < 3:
                print(f"  ⚠️  {par}: Datos insuficientes")
                continue
            
            # Buscar dirección desde la vela más reciente hacia atrás
            direccion_encontrada = None
            
            # Iterar desde la vela más reciente hacia atrás
            for i in range(len(df) - 2):  # -2 porque necesitamos al menos 3 velas
                # Obtener ventana de 3 velas: i (más reciente), i+1, i+2 (más antigua)
                vela_actual = df.iloc[i]
                vela_anterior1 = df.iloc[i + 1]
                vela_anterior2 = df.iloc[i + 2]
                
                # Determinar dirección de la vela actual
                es_alcista = vela_actual['close'] > vela_actual['open']
                es_bajista = vela_actual['close'] < vela_actual['open']
                
                # Calcular máximos y mínimos de las velas anteriores
                max_anterior = max(vela_anterior1['high'], vela_anterior2['high'])
                min_anterior = min(vela_anterior1['low'], vela_anterior2['low'])
                
                # Verificar condiciones de dirección
                if es_alcista and vela_actual['close'] >= max_anterior:
                    direccion_encontrada = "LONG"
                    break  # Salir al encontrar primera dirección
                    
                elif es_bajista and vela_actual['close'] <= min_anterior:
                    direccion_encontrada = "SHORT"
                    break  # Salir al encontrar primera dirección
            
            # Si no se encontró dirección en ninguna ventana
            if direccion_encontrada is None:
                print(f"  ⚪ {par}: Sin dirección clara")
                continue
            
            # Obtener dirección actual desde la variable global
            direccion_actual = direccion_global.get(par)
            
            # Actualizar si hay cambio o si no hay dirección previa
            if direccion_encontrada and direccion_actual != direccion_encontrada:
                # Obtener vela actual para notificación
                vela_actual = df.iloc[0]
                
                # Actualizar dirección global y guardar en archivo
                if actualizar_direccion_global(par, direccion_encontrada):
                    notificar_direccion(par, direccion_encontrada, {
                        'close': vela_actual['close'],
                        'open': vela_actual['open'],
                        'high': vela_actual['high'],
                        'low': vela_actual['low'],
                        'ventana_velas': 3,
                        'posicion_ventana': i,  # Posición donde se encontró la dirección
                        'timestamp': datetime.now().isoformat()
                    })
                    print(f"  ✅ {par}: {direccion_encontrada} (en ventana {i}) - Guardado en archivo")
                else:
                    print(f"  ⚠️  {par}: {direccion_encontrada} (en ventana {i}) - Error guardando")
            elif direccion_actual == direccion_encontrada:
                print(f"  🔄 {par}: Mantiene {direccion_encontrada}")
                
        except Exception as e:
            print(f"  ❌ Error {par}: {e}")
            import traceback
            traceback.print_exc()