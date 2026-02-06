"""
BOT PRINCIPAL - MODO CONTINUO
"""

import time
import threading
from datetime import datetime
from config import (
    TELEGRAM_TOKEN, TELEGRAM_CHANNEL, temporalidad_direccion, 
    temporalidad_precision, CUENTA_PRINCIPAL, CUENTAS_SECUNDARIAS,
    PORCENTAJE_RIESGO, MAX_OPERACIONES_SIMULTANEAS, MODO_OPERACION,
    PARES, hora_inicio, hora_fin
)
from direccion import verificar_direccion
from precision import buscar_entradas
from notificacion import enviar_mensaje
from data_metatrader5 import (
    conectar_mt5, obtener_estado_cuenta,
    abrir_operacion_mercado, contar_operaciones_abiertas
)
import pytz

# Lista de todas las cuentas a operar
if CUENTA_PRINCIPAL:
    TODAS_CUENTAS = [CUENTA_PRINCIPAL] + CUENTAS_SECUNDARIAS
else:
    TODAS_CUENTAS = CUENTAS_SECUNDARIAS

# Lock para evitar ejecuciones simultáneas
ejecucion_lock = threading.Lock()

# Almacenar señales detectadas para evitar duplicados
señales_detectadas = {}
ULTIMA_SEÑAL_ID = None


def inicializar():
    """Inicializa el bot"""
    print("=" * 50)
    print("BOT DE TRADING - MODO CONTINUO")
    print("=" * 50)
    
    print(f"Pares configurados: {', '.join(PARES)}")
    print(f"Modo: {MODO_OPERACION}")
    print(f"Temporalidad dirección: {temporalidad_direccion}")
    print(f"Temporalidad precisión: {temporalidad_precision}")
    print(f"Riesgo por operación: {PORCENTAJE_RIESGO}%")
    print(f"Máx. operaciones por cuenta: {MAX_OPERACIONES_SIMULTANEAS}")
    if CUENTA_PRINCIPAL:
        conectar_mt5(servidor=CUENTA_PRINCIPAL['servidor'],numero_cuenta=CUENTA_PRINCIPAL['numero_cuenta'],contraseña=CUENTA_PRINCIPAL['contraseña'])
    if TODAS_CUENTAS:
        print("\n📋 Cuentas configuradas:")
        for i, cuenta in enumerate(TODAS_CUENTAS, 1):
            nombre = cuenta.get('nombre', f"Cuenta {i}")
            servidor = cuenta['servidor']
            num_cuenta = cuenta['numero_cuenta']
            balance = cuenta.get('balance', 'No especificado')
            print(f"  {i}. {nombre}")
            print(f"     {num_cuenta}@{servidor}")
            print(f"     Balance: ${balance if isinstance(balance, (int, float)) else 'N/A'}")
        
    if TELEGRAM_TOKEN and TELEGRAM_CHANNEL:
        enviar_mensaje(f"🤖 Bot iniciado\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def generar_id_señal(señal):
    """Genera un ID único para la señal"""
    return f"{señal['par']}_{señal['tipo']}_{señal['entrada']:.5f}"


def ejecutar_señales_en_cuentas(señales):
    """Ejecuta las señales en todas las cuentas configuradas"""
    global ULTIMA_SEÑAL_ID
    
    if not señales:
        print("   ⚠️  No hay señales para ejecutar")
        return False
    
    resultados = {}
    
    for señal in señales:
        señal_id = generar_id_señal(señal)
        
        # Evitar duplicados (solo procesar señales nuevas)
        if señal_id == ULTIMA_SEÑAL_ID:
            print(f"   ⏭️  Señal ya procesada: {señal['par']} {señal['tipo']}")
            continue
        
        ULTIMA_SEÑAL_ID = señal_id
        resultados[señal['par']] = {}
        
        print(f"\n   🎯 Procesando señal para {señal['par']}:")
        print(f"      Tipo: {señal['tipo']}")
        print(f"      Entrada: {señal['entrada']:.5f}")
        print(f"      SL: {señal['sl']:.5f}")
        print(f"      TP: {señal['tp']:.5f}")
        print(f"      Pips SL: {señal['pips_sl']}")
        print(f"      Ratio: {señal['ratio']}:1")
        
        # Ejecutar en cada cuenta
        for cuenta_config in TODAS_CUENTAS:
            nombre_cuenta = cuenta_config.get('nombre', f"Cuenta {cuenta_config['numero_cuenta']}")
            servidor = cuenta_config['servidor']
            numero_cuenta = cuenta_config['numero_cuenta']
            contraseña = cuenta_config['contraseña']
            balance_cuenta = cuenta_config.get('balance', 0)
            
            print(f"\n      🔄 Procesando en {nombre_cuenta}...")
            
            # Determinar tipo de operación
            tipo_operacion = "COMPRA" if "LONG" in señal['tipo'] else "VENTA"
            
            if MODO_OPERACION == "REAL":
                # Ejecutar operación REAL usando el método de data_metatrader5
                resultado = abrir_operacion_mercado(
                    servidor=servidor,
                    numero_cuenta=numero_cuenta,
                    contraseña=contraseña,
                    simbolo=señal['par'],
                    balance_cuenta=balance_cuenta,
                    precio_sl=señal['sl'],
                    precio_tp=señal['tp'],
                    tipo_operacion=tipo_operacion,
                    porcentaje_riesgo=PORCENTAJE_RIESGO,
                )
                                
                if resultado:
                    print(f"      ✅ {nombre_cuenta}: Operación exitosa - Ticket {resultado.order}")
                    resultados[señal['par']][nombre_cuenta] = {
                        'exito': True,
                        'ticket': resultado.order,
                        'volumen': resultado.volume,
                        'precio_ejecutado': resultado.price
                    }
                    
                else:
                    print(f"      ❌ {nombre_cuenta}: Error ejecutando operación")
                    resultados[señal['par']][nombre_cuenta] = {'exito': False}
    return resultados


def ejecutar_tareas_segun_hora():
    """Ejecuta las tareas correspondientes según la hora actual"""
    with ejecucion_lock:
        ahora = datetime.now()
        minuto_actual = ahora.minute
        hora_actual = ahora.hour
        
        print(f"\n[{ahora.strftime('%H:%M:%S')}] 🔄 Verificando tareas...")
        
        # Siempre en orden: 1H → 15M → 5M
        
        # 1. Verificar si toca ejecutar 1H (cada hora en minuto 0)
        acceso_direccion = False
        if temporalidad_direccion == "1hour" and minuto_actual == 0:
            acceso_direccion = True
        elif temporalidad_direccion == "15min" and minuto_actual % 15 == 0:
            acceso_direccion = True
        elif temporalidad_direccion == "5min" and minuto_actual % 5 == 0:
            acceso_direccion = True
            
        if acceso_direccion:
            print(f"[{ahora.strftime('%H:%M:%S')}] 📊 Ejecutando Verificación {temporalidad_direccion}...")
            verificar_direccion(temporalidad=temporalidad_direccion)
            print(f"[{ahora.strftime('%H:%M:%S')}] ✅ Verificación {temporalidad_direccion} completada")
        
        
        
        acceso_precision = False
        if acceso_precision == "1hour" and minuto_actual == 0:
            acceso_precision = True
        elif acceso_precision == "15min" and minuto_actual % 15 == 0:
            acceso_precision = True
        elif acceso_precision == "5min" and minuto_actual % 5 == 0:
            acceso_precision = True
        
        if acceso_precision:
            print(f"[{ahora.strftime('%H:%M:%S')}] 🔍 Ejecutando Búsqueda {temporalidad_precision}...")
            señales = buscar_entradas(intervalo=temporalidad_precision)
            print(f"[{ahora.strftime('%H:%M:%S')}] ✅ Búsqueda {temporalidad_precision} completada")
            
            # Si hay señales, ejecutarlas en todas las cuentas
            ny_tz = pytz.timezone('America/New_York')
            hora_ny = datetime.now(ny_tz).hour
            if señales and MODO_OPERACION == 'REAL' and hora_inicio <= hora_ny < hora_fin:
                print(f"\n[{ahora.strftime('%H:%M:%S')}] 🚀 Ejecutando señales encontradas...")
                resultados = ejecutar_señales_en_cuentas(señales)
                
                # Resumen de resultados
                print(f"\n[{ahora.strftime('%H:%M:%S')}] 📊 Resumen de ejecución:")
                for par, cuentas in resultados.items():
                    print(f"   {par}:")
                    for cuenta, resultado in cuentas.items():
                        if resultado.get('exito'):
                            if resultado.get('simulado'):
                                print(f"     {cuenta}: ✅ SIMULADO")
                            else:
                                ticket = resultado.get('ticket', 'N/A')
                                print(f"     {cuenta}: ✅ REAL (Ticket: {ticket})")
                        else:
                            print(f"     {cuenta}: ❌ FALLÓ")
            else:
                print(f"\n[{ahora.strftime('%H:%M:%S')}] ⚠️  No se encontraron señales válidas")
        
        # 3. Verificar si toca ejecutar 5M (cada 5 minutos)
        #if minuto_actual % 5 == 0:
        #    print(f"[{ahora.strftime('%H:%M:%S')}] 🔎 Ejecutando Búsqueda 5M...")
        #    buscar_entradas(intervalo=temporalidad_precision)
        #    print(f"[{ahora.strftime('%H:%M:%S')}] ✅ Búsqueda 5M completada")
        
        # Si no ejecutó nada, mostrar mensaje
        if not (minuto_actual == 0 or minuto_actual % 15 == 0 or minuto_actual % 5 == 0):
            print(f"[{ahora.strftime('%H:%M:%S')}] ⏭️  No hay tareas programadas para este minuto")


def ejecutar_primera_verificacion():
    """Ejecuta la primera verificación completa"""
    with ejecucion_lock:
        ahora = datetime.now()
        print(f"\n[{ahora.strftime('%H:%M:%S')}] 🚀 Ejecutando primera verificación completa...")
        
        print(f"[{ahora.strftime('%H:%M:%S')}] 📊 Verificación {temporalidad_direccion}...")
        verificar_direccion(temporalidad=temporalidad_direccion)
        
        print(f"[{ahora.strftime('%H:%M:%S')}] 🔍 Búsqueda {temporalidad_precision}...")
        señales = buscar_entradas(intervalo=temporalidad_precision)
        
        # Ejecutar señales si existen
        ny_tz = pytz.timezone('America/New_York')
        hora_ny = datetime.now(ny_tz).hour
        if señales and MODO_OPERACION == 'REAL' and hora_inicio <= hora_ny < hora_fin:
            print(f"\n[{ahora.strftime('%H:%M:%S')}] 🚀 Ejecutando señales de primera verificación...")
            resultados = ejecutar_señales_en_cuentas(señales)
        else:
            print(f"\n[{ahora.strftime('%H:%M:%S')}] ⚠️  No se encontraron señales en primera verificación")
        
        print(f"[{ahora.strftime('%H:%M:%S')}] ✅ Verificación inicial COMPLETADA")


def main():
    """Función principal"""
    inicializar()
    
    print("\n⏰ Ejecutando en modo continuo (verificación cada minuto)...")
    
    # Ejecutar primera verificación completa
    ejecutar_primera_verificacion()
    
    # Bucle principal que verifica cada minuto
    print("\n🔄 Entrando en modo continuo...")
    print("🛑 Presiona Ctrl+C para detener\n")
    
    ultima_verificacion = datetime.now()
    
    try:
        while True:
            ahora = datetime.now()
            
            # Verificar si ha pasado 1 minuto desde la última ejecución
            if (ahora - ultima_verificacion).seconds >= 60:
                ultima_verificacion = ahora
                ejecutar_tareas_segun_hora()
            
            # Mostrar estado
            segundos_restantes = 60 - (ahora - ultima_verificacion).seconds
            minutos_restantes = segundos_restantes / 60
            
            if ejecucion_lock.locked():
                estado = "⏳ Ejecutando..."
            else:
                estado = "✅ Listo"
            
            print(f"⏰ Próxima verificación en {minutos_restantes:.1f} min | {estado}", end='\r')
            
            time.sleep(1)
                        
    except KeyboardInterrupt:
        print("\n\n🛑 Bot detenido por usuario")
        
        # Esperar si hay ejecución en curso
        if ejecucion_lock.locked():
            print("⏳ Esperando a que termine la ejecución actual...")
            # Esperar máximo 30 segundos
            for i in range(30):
                if not ejecucion_lock.locked():
                    break
                print(f"⏳ Esperando... {29-i}s restantes", end='\r')
                time.sleep(1)
        
        if TELEGRAM_TOKEN and TELEGRAM_CHANNEL:
            enviar_mensaje(f"🛑 Bot detenido\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()