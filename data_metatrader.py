import pandas as pd
import MetaTrader5 as mt5

def conectar_mt5(servidor, numero_cuenta, contraseña):
    if not mt5.initialize():
        print("Error al inicializar MT5:", mt5.last_error())
        return False
    
    autorizado = mt5.login(numero_cuenta, contraseña=contraseña, server=servidor)
    if not autorizado:
        print("Error de login:", mt5.last_error())
        mt5.shutdown()
        return False
    return True

def obtener_velas_mt5(par, intervalo, barras):
    intervalos = {
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
    timeframe = intervalos.get(intervalo, mt5.TIMEFRAME_H1)
    
    rates = mt5.copy_rates_from_pos(par, timeframe, 0, barras)
    if rates is None or len(rates) == 0:
        return None, None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    df.columns = ['open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
    
    tick = mt5.symbol_info_tick(par)
    precio_actual = tick.ask if tick else df['close'].iloc[-1]
    
    return df[['open', 'high', 'low', 'close']], precio_actual


def contar_operaciones_abiertas():
    posiciones = mt5.positions_get()
    return len(posiciones) if posiciones is not None else 0


def obtener_operaciones_abiertas():
    posiciones = mt5.positions_get()
    if posiciones is None or len(posiciones) == 0:
        return []
    
    operaciones = []
    for pos in posiciones:
        operaciones.append({
            'ticket': pos.ticket,
            'simbolo': pos.symbol,
            'tipo': 'COMPRA' if pos.type == 0 else 'VENTA',
            'volumen': pos.volume,
            'precio_apertura': pos.price_open,
            'precio_actual': pos.price_current,
            'sl': pos.sl,
            'tp': pos.tp,
            'beneficio': pos.profit,
            'swap': pos.swap,
            'comision': pos.commission
        })
    return operaciones


def obtener_estado_cuenta():
    cuenta = mt5.account_info()
    if cuenta is None:
        return None
    
    return {
        'numero_cuenta': cuenta.login,
        'nombre': cuenta.name,
        'servidor': cuenta.server,
        'balance': cuenta.balance,
        'equity': cuenta.equity,
        'margen': cuenta.margin,
        'margen_libre': cuenta.margin_free,
        'margen_nivel': cuenta.margin_level,
        'apalancamiento': cuenta.leverage,
        'moneda': cuenta.currency,
        'beneficio': cuenta.profit
    }
    

def calcular_lote_estandar(simbolo, precio_entrada, precio_stop, balance_cuenta, porcentaje_riesgo, apalancamiento):
    riesgo_dinero = balance_cuenta * (porcentaje_riesgo / 100)
    info_simbolo = mt5.symbol_info(simbolo)
    
    if info_simbolo is None:
        print(f"No se encontró información para {simbolo}")
        return 0.0
    
    tick_size = info_simbolo.trade_tick_size
    tick_value = info_simbolo.trade_tick_value
    volumen_min = info_simbolo.volume_min
    volumen_max = info_simbolo.volume_max
    volumen_step = info_simbolo.volume_step
    
    if "JPY" in simbolo:
        pip_value = 0.01
    elif "XAUUSD" in simbolo or "XAGUSD" in simbolo:
        pip_value = 0.1
    else:
        pip_value = 0.0001
    
    distancia_pips = abs(precio_entrada - precio_stop) / pip_value
    valor_pip_por_lote = 10.0
    
    if distancia_pips > 0:
        lotes = riesgo_dinero / (distancia_pips * valor_pip_por_lote)
    else:
        lotes = 0.0
    
    margen_requerido = (lotes * 100000 * precio_entrada) / apalancamiento
    if margen_requerido > balance_cuenta * 0.8:
        lotes = (balance_cuenta * 0.8 * apalancamiento) / (100000 * precio_entrada)
    
    lotes = max(volumen_min, min(volumen_max, lotes))
    lotes = round(lotes / volumen_step) * volumen_step
    
    return round(lotes, 2)


def calcular_pips(simbolo, precio1, precio2):
    simbolo_upper = simbolo.upper()
    if "JPY" in simbolo_upper:
        multiplicador = 100
    elif "XAU" in simbolo_upper or "XAG" in simbolo_upper:
        multiplicador = 10
    elif "BTC" in simbolo_upper or "ETH" in simbolo_upper:
        multiplicador = 1
    else:
        multiplicador = 10000
    return round(abs(precio1 - precio2) * multiplicador, 2)


def abrir_operacion_mercado(simbolo, volumen, sl, tp, tipo_operacion):
    simbolo_info = mt5.symbol_info(simbolo)
    if simbolo_info is None:
        print(f"El símbolo {simbolo} no existe")
        return None
    
    if not simbolo_info.visible:
        if not mt5.symbol_select(simbolo, True):
            print(f"No se pudo seleccionar {simbolo}")
            return None
    
    tick = mt5.symbol_info_tick(simbolo)
    if tick is None:
        print(f"No se pudo obtener tick para {simbolo}")
        return None
    
    point = mt5.symbol_info(simbolo).point
    
    if tipo_operacion == "COMPRA":
        order_type = mt5.ORDER_TYPE_BUY
        precio = tick.ask
        sl_price = precio - sl * point if sl > 0 else 0.0
        tp_price = precio + tp * point if tp > 0 else 0.0
    elif tipo_operacion == "VENTA":
        order_type = mt5.ORDER_TYPE_SELL
        precio = tick.bid
        sl_price = precio + sl * point if sl > 0 else 0.0
        tp_price = precio - tp * point if tp > 0 else 0.0
    else:
        print("Tipo de operación no válido. Use 'COMPRA' o 'VENTA'")
        return None
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": simbolo,
        "volume": volumen,
        "type": order_type,
        "price": precio,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 10,
        "magic": 234000,
        "comment": "Operación Python",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    resultado = mt5.order_send(request)
    
    if resultado.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Error al abrir operación: {resultado.retcode}")
        print(f"Descripción: {mt5.last_error()}")
        return None
    
    return resultado

def abrir_operacion_eurusd(volumen, sl_pips, tp_pips, tipo_operacion):
    return abrir_operacion_mercado("EURUSD", volumen, sl_pips, tp_pips, tipo_operacion)

def cerrar_operacion(ticket):
    posicion = mt5.positions_get(ticket=ticket)
    if posicion is None or len(posicion) == 0:
        print(f"No se encontró operación con ticket {ticket}")
        return False
    
    pos = posicion[0]
    simbolo = pos.symbol
    volumen = pos.volume
    
    tick = mt5.symbol_info_tick(simbolo)
    if tick is None:
        return False
    
    if pos.type == mt5.ORDER_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        precio = tick.bid
    else:
        order_type = mt5.ORDER_TYPE_BUY
        precio = tick.ask
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": simbolo,
        "volume": volumen,
        "type": order_type,
        "position": ticket,
        "price": precio,
        "deviation": 10,
        "magic": 234000,
        "comment": "Cierre Python",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    resultado = mt5.order_send(request)
    
    if resultado.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Error al cerrar operación: {resultado.retcode}")
        return False
    
    return True

def main():
    SERVIDOR = "TuBrokerServer"
    NUMERO_CUENTA = 12345678
    CONTRASEÑA = "TuContraseña"
    
    if not conectar_mt5(SERVIDOR, NUMERO_CUENTA, CONTRASEÑA):
        print("No se pudo conectar a MT5")
        return
    
    try:
        print("=== DATOS DE VELAS ===")
        velas, precio_actual = obtener_velas_mt5("EURUSD", "1hour", 10)
        if velas is not None:
            print(f"Precio actual EURUSD: {precio_actual}")
            print("Últimas velas:")
            print(velas.tail())
        
        print("\n=== OPERACIONES ABIERTAS ===")
        num_ops = contar_operaciones_abiertas()
        print(f"Total operaciones abiertas: {num_ops}")
        
        if num_ops > 0:
            ops = obtener_operaciones_abiertas()
            for op in ops:
                print(f"  {op['simbolo']} {op['tipo']} - {op['volumen']} lotes - Beneficio: ${op['beneficio']:.2f}")
        
        print("\n=== ESTADO DE CUENTA ===")
        estado = obtener_estado_cuenta()
        if estado:
            print(f"Cuenta: {estado['numero_cuenta']}")
            print(f"Servidor: {estado['servidor']}")
            print(f"Balance: ${estado['balance']:.2f}")
            print(f"Equity: ${estado['equity']:.2f}")
            print(f"Margen libre: ${estado['margen_libre']:.2f}")
            print(f"Nivel de margen: {estado['margen_nivel']:.1f}%")
            print(f"Apalancamiento: 1:{estado['apalancamiento']}")
        
        print("\n=== CALCULADORA DE POSICIÓN ===")
        balance = estado['balance'] if estado else 10000
        apalancamiento = estado['apalancamiento'] if estado else 100
        
        lotes = calcular_lote_estandar(
            simbolo="EURUSD",
            precio_entrada=1.0850,
            precio_stop=1.0820,
            balance_cuenta=balance,
            porcentaje_riesgo=2,
            apalancamiento=apalancamiento
        )
        
        pips = calcular_pips("EURUSD", 1.0850, 1.0820)
        print(f"Para operación EURUSD:")
        print(f"  Entrada: 1.0850, Stop: 1.0820 ({pips} pips)")
        print(f"  Balance cuenta: ${balance:.2f}")
        print(f"  Riesgo: 2%")
        print(f"  Apalancamiento: 1:{apalancamiento}")
        print(f"  Lotes calculados: {lotes}")
        
        print("\n=== EJEMPLO DE APERTURA DE OPERACIÓN ===")
        respuesta = input("¿Deseas abrir una operación en EURUSD? (s/n): ")
        
        if respuesta.lower() == 's':
            tipo = input("Tipo (COMPRA/VENTA): ")
            volumen_lotes = float(input("Volumen en lotes (ej: 0.1): "))
            sl_pips = float(input("Stop Loss en pips (ej: 20): "))
            tp_pips = float(input("Take Profit en pips (ej: 40): "))
            
            resultado = abrir_operacion_eurusd(volumen_lotes, sl_pips, tp_pips, tipo)
            
            if resultado is not None:
                print(f"\nOperación abierta exitosamente!")
                print(f"Ticket: {resultado.order}")
                print(f"Precio ejecutado: {resultado.price}")
                print(f"Volumen: {resultado.volume}")
                print(f"SL: {resultado.sl if resultado.sl > 0 else 'No establecido'}")
                print(f"TP: {resultado.tp if resultado.tp > 0 else 'No establecido'}")
        
    finally:
        mt5.shutdown()
        print("\nConexión cerrada")

if __name__ == "__main__":
    main()