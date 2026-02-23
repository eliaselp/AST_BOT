
import pandas as pd
import MetaTrader5 as mt5
import time
import config
import tiempo
import pytz
from datetime import datetime


def conectar_mt5(servidor, numero_cuenta, contraseña):
    """Conecta a una cuenta MT5 específica"""
    if not mt5.initialize():
        print("Error al inicializar MT5:", mt5.last_error())
        return False
    
    autorizado = mt5.login(numero_cuenta, contraseña=contraseña, server=servidor)
    if not autorizado:
        print("Error de login:", mt5.last_error())
        mt5.shutdown()
        return False
    return True

def obtener_estado_cuenta():
    """Obtiene el estado actual de la cuenta conectada"""
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





def obtener_velas_mt5(par, intervalo, barras, numero_cuenta, servidor, contraseña, incluir_precio_actual=False):
    """Obtiene velas históricas de MT5 incluyendo volumen"""
    limpiar_conexiones_mt5()
    print(f"\n🔗 Conectando a cuenta {numero_cuenta}@{servidor}...")
    
    # Conectar a la cuenta específica
    if not conectar_mt5(servidor, numero_cuenta, contraseña):
        print(f"❌ Error conectando a cuenta {numero_cuenta}")
        return None, None
    
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
    
    # Renombrar columnas al estándar
    df.columns = ['open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
    
    # Crear columna 'volume' combinando tick_volume y real_volume según disponibilidad
    df['volume'] = df['real_volume'].where(df['real_volume'] > 0, df['tick_volume'])
    
    tick = mt5.symbol_info_tick(par)
    precio_actual = tick.ask if tick else df['close'].iloc[-1]
    
    if not incluir_precio_actual:
        df = df.iloc[:-1]
    
    df = df.iloc[::-1]
    
    # Devolver DataFrame con todas las columnas incluyendo 'volume' estandarizada
    return df, precio_actual
def calcular_lote_estandar(simbolo, precio_entrada, precio_stop, balance_cuenta, porcentaje_riesgo, apalancamiento):
    """Calcula el tamaño de lote basado en el balance y riesgo"""
    # Riesgo monetario
    riesgo_dinero = balance_cuenta * (porcentaje_riesgo / 100)
    
    # Obtener información del símbolo
    info_simbolo = mt5.symbol_info(simbolo)
    if info_simbolo is None:
        print(f"❌ No se encontró información para {simbolo}")
        return 0.0
    
    # Parámetros del símbolo
    volumen_min = info_simbolo.volume_min
    volumen_max = info_simbolo.volume_max
    volumen_step = info_simbolo.volume_step
    
    # Determinar valor del pip
    if "JPY" in simbolo:
        pip_value = 0.01
    elif "XAUUSD" in simbolo or "XAGUSD" in simbolo:
        pip_value = 0.1
    else:
        pip_value = 0.0001
    
    # Calcular distancia en pips
    distancia_pips = abs(precio_entrada - precio_stop) / pip_value
    valor_pip_por_lote = 10.0  # $10 por pip por lote estándar
    
    if distancia_pips > 0:
        lotes = riesgo_dinero / (distancia_pips * valor_pip_por_lote)
    else:
        lotes = 0.0
    
    # Validar límites de margen
    margen_requerido = (lotes * 100000 * precio_entrada) / apalancamiento
    if margen_requerido > balance_cuenta * 0.8:
        lotes = (balance_cuenta * 0.8 * apalancamiento) / (100000 * precio_entrada)
    
    # Ajustar a límites y step del broker
    lotes = max(volumen_min, min(volumen_max, lotes))
    if volumen_step > 0:
        lotes = round(lotes / volumen_step) * volumen_step
    return round(lotes, 2)



def abrir_operacion_mercado(type_filling ,servidor, numero_cuenta, contraseña, simbolo, balance_cuenta, precio_sl, tipo_operacion, porcentaje_riesgo=2.0,rr_ratio=1, max_reintentos=1000):
    """
    Conecta a una cuenta y abre una operación calculando volumen automáticamente
    con reintentos infinitos hasta que se ejecute o se alcance el máximo.
    
    Args:
        servidor: Servidor de la cuenta (ej: 'ICMarkets-Demo')
        numero_cuenta: Número de cuenta
        contraseña: Contraseña de la cuenta
        simbolo: Símbolo del par (ej: 'EURUSD')
        balance_cuenta: Balance de la cuenta
        precio_sl: Precio exacto del stop loss
        tipo_operacion: "COMPRA" o "VENTA"
        porcentaje_riesgo: Porcentaje a arriesgar (default: 2%)
        max_reintentos: Máximo número de reintentos (default: 1000)
    
    Returns:
        Resultado de la operación o None si hay error
    """
    limpiar_conexiones_mt5()
    print(f"\n🔗 Conectando a cuenta {numero_cuenta}@{servidor}...")
    
    # Conectar a la cuenta específica
    if not conectar_mt5(servidor, numero_cuenta, contraseña):
        print(f"❌ Error conectando a cuenta {numero_cuenta}")
        return None
    
    # Verificar límite de operaciones simultáneas
    #operaciones_abiertas = contar_operaciones_abiertas()
    #if operaciones_abiertas >= config.MAX_OPERACIONES_SIMULTANEAS:
    #    print(f"⚠️  Cuenta {numero_cuenta}: Límite alcanzado ({operaciones_abiertas}/{config.MAX_OPERACIONES_SIMULTANEAS})")
    #    return None
    
    # Obtener información actualizada de la cuenta
    info_cuenta = obtener_estado_cuenta()
    if not info_cuenta:
        print(f"❌ No se pudo obtener información de la cuenta {numero_cuenta}")
        return None
    
    # Usar el balance actualizado en lugar del pasado como parámetro
    balance_actual = info_cuenta['balance']
    apalancamiento = info_cuenta['apalancamiento']
    
    print(f"✅ Conectado a cuenta {numero_cuenta}")
    print(f"   Balance actual: ${balance_actual:.2f}")
    print(f"   Equity: ${info_cuenta['equity']:.2f}")
    print(f"   Apalancamiento: 1:{apalancamiento}")
    
    # Verificar símbolo
    simbolo_info = mt5.symbol_info(simbolo)
    if simbolo_info is None:
        print(f"❌ El símbolo {simbolo} no existe")
        return None
    
    # Seleccionar símbolo si no está visible
    if not simbolo_info.visible:
        if not mt5.symbol_select(simbolo, True):
            print(f"❌ No se pudo seleccionar {simbolo}")
            return None
    
    # Determinar tipo de orden
    if tipo_operacion == "COMPRA":
        order_type = mt5.ORDER_TYPE_BUY
    elif tipo_operacion == "VENTA":
        order_type = mt5.ORDER_TYPE_SELL
    else:
        print("❌ Tipo de operación no válido. Use 'COMPRA' o 'VENTA'")
        return None
    
    # Variables para reintentos
    intento = 0
    resultado = None
    
    print(f"\n🔄 Iniciando intentos de apertura (máximo: {max_reintentos})...")
    
    while intento < max_reintentos:
        intento += 1
        print(f"\n📊 Intento #{intento}")
        
        try:
            # Obtener tick actual actualizado en cada intento
            tick = mt5.symbol_info_tick(simbolo)
            if tick is None:
                print(f"❌ Intento {intento}: No se pudo obtener tick para {simbolo}")
                time.sleep(0.1)  # Pequeña pausa antes de reintentar
                continue
            
            # Determinar precio actual según tipo de operación
            
            if tipo_operacion == "COMPRA":
                precio_actual = tick.ask
                precio_entrada_final = precio_actual
                precio_tp = precio_entrada_final + abs(precio_entrada_final - precio_sl) * rr_ratio
            else:  # VENTA
                precio_actual = tick.bid
                precio_entrada_final = precio_actual
                precio_tp = precio_entrada_final - abs(precio_entrada_final - precio_sl) * rr_ratio
            
            print(f"   Precio actual: {precio_actual:.5f}")
            
            # Validar precios SL y TP según tipo de operación
            if tipo_operacion == "COMPRA":
                if precio_sl >= precio_actual:
                    print(f"   ⚠️ SL ({precio_sl}) debe ser < precio actual ({precio_actual})")
                    time.sleep(0.1)
                    continue
                if precio_tp <= precio_actual:
                    print(f"   ⚠️ TP ({precio_tp}) debe ser > precio actual ({precio_actual})")
                    time.sleep(0.1)
                    continue
            else:  # VENTA
                if precio_sl <= precio_actual:
                    print(f"   ⚠️ SL ({precio_sl}) debe ser > precio actual ({precio_actual})")
                    time.sleep(0.1)
                    continue
                if precio_tp >= precio_actual:
                    print(f"   ⚠️ TP ({precio_tp}) debe ser < precio actual ({precio_actual})")
                    time.sleep(0.1)
                    continue
            
            # Calcular volumen basado en el balance ACTUAL (actualizado si es necesario)
            volumen = calcular_lote_estandar(
                simbolo=simbolo,
                precio_entrada=precio_actual,
                precio_stop=precio_sl,
                balance_cuenta=balance_cuenta,
                porcentaje_riesgo=porcentaje_riesgo,
                apalancamiento=apalancamiento
            )
            
            if volumen <= 0:
                print(f"   ❌ Volumen calculado inválido: {volumen}")
                time.sleep(0.1)
                continue
            execution_mode = simbolo_info.trade_exemode
            # Preparar solicitud de orden con precio actualizado
            # Nota: El comentario debe ser una cadena simple, sin caracteres especiales
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": simbolo,
                "volume": volumen,
                "type": order_type,
                "deviation": 10,
                "magic": 234000,
                "comment": "",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": type_filling,
            }
            if execution_mode != mt5.SYMBOL_TRADE_EXECUTION_MARKET:
                request["price"] = precio_entrada_final
            
            print("Filling mode:", simbolo_info.filling_mode)
            print("Execution mode:", simbolo_info.trade_exemode)
            input('===============')
            print(f"   📊 Enviando orden {tipo_operacion}")
            print(f"   Precio entrada: {precio_entrada_final:.5f}")
            print(f"   SL: {precio_sl:.5f} | TP: {precio_tp:.5f}")
            print(f"   Volumen: {volumen}")
            print(f"   Riesgo: {porcentaje_riesgo}% (${balance_actual * (porcentaje_riesgo/100):.2f})")
            
            # Validar orden antes del envío
            validacion = mt5.order_check(request)
            if validacion is None:
                print(f"   ❌ Validación fallida. Último error: {mt5.last_error()}")
                time.sleep(0.1)
                continue
            
            # Enviar orden
            resultado = mt5.order_send(request)
            
            # Verificar resultado
            if resultado.retcode == mt5.TRADE_RETCODE_DONE:
        
                modify_request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": resultado.order,
                    "sl": precio_sl,
                    "tp": precio_tp,
                }
                mt5.order_send(modify_request)
                # Operación exitosa
                
                print(f"\n✅ Operación exitosa en intento #{intento} - Ticket {resultado.order}")
                print(f"   Ticket: {resultado.order}")
                print(f"   Volumen ejecutado: {resultado.volume}")
                print(f"   Precio ejecutado: {resultado.price:.5f}")
                print(f"   Beneficio potencial: ${(abs(resultado.price - precio_tp) * volumen * 100000):.2f}")
                break
            else:
                # Mostrar error pero continuar con reintentos
                error_msg = obtener_mensaje_error(resultado.retcode)
                print(f"   ❌ Intento {intento} fallido: {resultado.retcode} - {error_msg}")
                
                # Pausa progresiva: más tiempo después de más intentos
                pausa = min(0.5 + (intento * 0.05), 5.0)  # Máximo 5 segundos
                time.sleep(pausa)
                
        except Exception as e:
            print(f"   ⚠️ Excepción en intento {intento}: {str(e)}")
            time.sleep(0.5)
            continue
    
    if intento >= max_reintentos and resultado is None:
        print(f"\n❌ Se alcanzó el máximo de {max_reintentos} intentos sin éxito")
        return None
    
    if resultado is None:
        print(f"\n❌ No se pudo abrir la operación después de {intento} intentos")
        return None
    
    return resultado



def obtener_mensaje_error(codigo_error):
    """Traduce códigos de error de MT5 a mensajes legibles"""
    mensajes_error = {
        10004: "Requote",
        10006: "Request rejected",
        10007: "Request canceled by trader",
        10008: "Order placed",
        10009: "Request completed",
        10010: "Only part of the request was completed",
        10011: "Request processing error",
        10012: "Request canceled by timeout",
        10013: "Invalid request",
        10014: "Invalid volume in the request",
        10015: "Invalid price in the request",
        10016: "Invalid stops in the request",
        10017: "Trade is disabled",
        10018: "Market is closed",
        10019: "There is not enough money to complete the request",
        10020: "Prices changed",
        10021: "There are no quotes to process the request",
        10022: "Invalid order expiration date in the request",
        10023: "Order state changed",
        10024: "Too frequent requests",
        10025: "No changes in request",
        10026: "Autotrading disabled by server",
        10027: "Autotrading disabled by client terminal",
        10028: "Request locked for processing",
        10029: "Order or position frozen",
    }
    
    return mensajes_error.get(codigo_error, f"Código desconocido: {codigo_error}")




def contar_operaciones_abiertas():
    """Cuenta las operaciones abiertas en la cuenta conectada"""
    posiciones = mt5.positions_get()
    return len(posiciones) if posiciones is not None else 0

def obtener_operaciones_abiertas():
    """Obtiene todas las operaciones abiertas de la cuenta conectada"""
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

def limpiar_conexiones_mt5():
    """Limpia todas las conexiones MT5 existentes"""
    try:
        mt5.shutdown()
        print("🔄 Conexiones MT5 limpiadas")
        return True
    except:
        return False
    
def calcular_pips(simbolo, precio1, precio2):
    """Calcula la diferencia en pips entre dos precios"""
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



def cerrar_operaciones_por_tiempo(type_filling, servidor, numero_cuenta, contraseña, velas_permitidas, temporalidad):
    """
    Cierra operaciones abiertas que superen un tiempo máximo de apertura basado en velas.
    
    Args:
        servidor: Servidor de la cuenta (ej: 'ICMarkets-Demo')
        numero_cuenta: Número de cuenta
        contraseña: Contraseña de la cuenta
        velas_permitidas: Número de velas permitidas antes de cerrar
        temporalidad: Temporalidad de las velas ('1min', '5min', '15min', '30min', '1hour', '4hour', '1day')
    
    Returns:
        Diccionario con resumen de operaciones cerradas
    """
    print(f"\n⏰ Iniciando verificación de tiempo de operaciones...")
    print(f"   Configuración: {velas_permitidas} velas de {temporalidad}")
    
    # Mapeo de temporalidades a minutos
    minutos_por_temporalidad = {
        '1min': 1,
        '5min': 5,
        '15min': 15,
        '30min': 30,
        '1hour': 60,
        '4hour': 240,
        '1day': 1440,
        '1week': 10080,
        '1month': 43200
    }
    
    # Validar temporalidad
    if temporalidad not in minutos_por_temporalidad:
        print(f"❌ Temporalidad '{temporalidad}' no válida")
        return None
    
    # Calcular tiempo máximo permitido en minutos
    minutos_por_vela = minutos_por_temporalidad[temporalidad]
    tiempo_maximo_minutos = velas_permitidas * minutos_por_vela
    
    print(f"   Tiempo máximo permitido: {tiempo_maximo_minutos} minutos")
    
    # Conectar a MT5
    limpiar_conexiones_mt5()
    print(f"\n🔗 Conectando a cuenta {numero_cuenta}@{servidor}...")
    
    if not conectar_mt5(servidor, numero_cuenta, contraseña):
        print(f"❌ Error conectando a cuenta {numero_cuenta}_{servidor}")
        return None
    
    # Obtener operaciones abiertas
    operaciones = obtener_operaciones_abiertas()
    
    if not operaciones:
        print("📭 No hay operaciones abiertas para verificar")
        return {
            'total_operaciones': 0,
            'operaciones_cerradas': 0,
            'operaciones_verificadas': 0,
            'detalle': []
        }
    
    print(f"\n📊 Verificando {len(operaciones)} operaciones abiertas...")
    
    # Obtener hora actual usando nuestro módulo tiempo.py
    hora_actual_utc = tiempo.obtener_hora_actual()
    hora_actual_timestamp = hora_actual_utc.timestamp()
    
    
    # Resultados
    operaciones_cerradas = []
    operaciones_mantenidas = []
    
    for op in operaciones:
        ticket = op['ticket']
        simbolo = op['simbolo']
        tipo = op['tipo']
        beneficio = op['beneficio']
        
        # Obtener tiempo de apertura de la posición
        posicion = mt5.positions_get(ticket=ticket)
        if not posicion or len(posicion) == 0:
            print(f"⚠️ No se pudo obtener información de la operación {ticket}")
            continue
        
        # El tiempo de apertura está en segundos desde 1970 (timestamp UTC)
        tiempo_apertura_timestamp = posicion[0].time
        
        # Convertir a datetime usando nuestro módulo
        hora_apertura_utc = datetime.fromtimestamp(tiempo_apertura_timestamp, pytz.UTC)
        
        # Calcular tiempo transcurrido en minutos usando timestamps
        minutos_transcurridos = (hora_actual_timestamp - tiempo_apertura_timestamp) / 60
        
        # Verificar si supera el tiempo máximo (comparar en minutos)
        if minutos_transcurridos >= tiempo_maximo_minutos:
            print(f"\n⏱️ Operación {ticket} - {simbolo} {tipo}")
            print(f"   Hora apertura: {hora_apertura_utc.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Tiempo transcurrido: {minutos_transcurridos:.1f} minutos")
            print(f"   Tiempo máximo: {tiempo_maximo_minutos} minutos")
            print(f"   Beneficio actual: ${beneficio:.2f}")
            print(f"   ⚠️ SUPERÓ TIEMPO LÍMITE - Cerrando...")
            
            # Cerrar la operación
            resultado_cierre = cerrar_operacion_por_ticket(ticket, type_filling)
            
            if resultado_cierre:
                operaciones_cerradas.append({
                    'ticket': ticket,
                    'simbolo': simbolo,
                    'tipo': tipo,
                    'minutos_transcurridos': round(minutos_transcurridos, 1),
                    'beneficio': beneficio,
                    'resultado_cierre': 'EXITOSO'
                })
                print(f"   ✅ Operación {ticket} cerrada exitosamente")
            else:
                operaciones_cerradas.append({
                    'ticket': ticket,
                    'simbolo': simbolo,
                    'tipo': tipo,
                    'minutos_transcurridos': round(minutos_transcurridos, 1),
                    'beneficio': beneficio,
                    'resultado_cierre': 'FALLIDO'
                })
                print(f"   ❌ Error al cerrar operación {ticket}")
        else:
            print(f"\n✅ Operación {ticket} - {simbolo} {tipo}")
            print(f"   Hora apertura: {hora_apertura_utc.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Tiempo transcurrido: {minutos_transcurridos:.1f} minutos")
            print(f"   Tiempo máximo: {tiempo_maximo_minutos} minutos")
            print(f"   Beneficio actual: ${beneficio:.2f}")
            print(f"   ✓ Dentro del tiempo permitido")
            
            operaciones_mantenidas.append({
                'ticket': ticket,
                'simbolo': simbolo,
                'tipo': tipo,
                'hora_apertura': hora_apertura_utc.strftime('%Y-%m-%d %H:%M:%S'),
                'minutos_transcurridos': round(minutos_transcurridos, 1),
                'beneficio': beneficio
            })
    
    # Resumen final
    print(f"\n{'='*50}")
    print(f"📊 RESUMEN DE VERIFICACIÓN DE TIEMPO")
    print(f"{'='*50}")
    print(f"Total operaciones verificadas: {len(operaciones)}")
    print(f"Operaciones cerradas por tiempo: {len(operaciones_cerradas)}")
    print(f"Operaciones mantenidas: {len(operaciones_mantenidas)}")
    
    if operaciones_cerradas:
        print(f"\n📉 OPERACIONES CERRADAS:")
        for op in operaciones_cerradas:
            estado = "✅" if op['resultado_cierre'] == 'EXITOSO' else "❌"
            print(f"   {estado} Ticket {op['ticket']} - {op['simbolo']} {op['tipo']} - {op['minutos_transcurridos']}min - Beneficio: ${op['beneficio']:.2f}")
    
    return {
        'total_operaciones': len(operaciones),
        'operaciones_cerradas': len(operaciones_cerradas),
        'operaciones_mantenidas': len(operaciones_mantenidas),
        'detalle_cerradas': operaciones_cerradas,
        'detalle_mantenidas': operaciones_mantenidas,
        'tiempo_maximo_minutos': tiempo_maximo_minutos,
        'temporalidad': temporalidad,
        'velas_permitidas': velas_permitidas,
    }


def cerrar_operacion_por_ticket(ticket, type_filling):
    """
    Cierra una operación específica por su ticket con reintentos.
    
    Args:
        ticket: Número de ticket de la operación a cerrar
    
    Returns:
        True si se cerró exitosamente, False en caso contrario
    """
    try:
        # Obtener la posición
        posicion = mt5.positions_get(ticket=ticket)
        if not posicion or len(posicion) == 0:
            print(f"❌ No se encontró la posición con ticket {ticket}")
            return False
        
        pos = posicion[0]
        
        # Preparar la solicitud de cierre
        symbol = pos.symbol
        volume = pos.volume
        position_type = pos.type
        
        # Configurar reintentos
        max_reintentos = 100
        intento = 0
        
        while intento < max_reintentos:
            intento += 1
            
            # Determinar tipo de orden de cierre
            if position_type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(symbol).ask
            
            # Crear solicitud de cierre
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 10,
                "magic": 234000,
                "comment": "",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": type_filling,
            }
            
            # Enviar orden de cierre
            result = mt5.order_send(close_request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                # Obtener hora de cierre usando nuestro módulo para el log
                print(f"   ✅ Operación {ticket} cerrada.")
                return True
            else:
                error_msg = obtener_mensaje_error(result.retcode)
                print(f"   ⚠️ Intento {intento}: Error cerrando ticket {ticket}: {error_msg}")
                
                # Pausa progresiva entre reintentos
                time.sleep(0.1 * intento)
                
        print(f"❌ No se pudo cerrar el ticket {ticket} después de {max_reintentos} intentos")
        return False
            
    except Exception as e:
        print(f"❌ Excepción cerrando ticket {ticket}: {str(e)}")
        return False
