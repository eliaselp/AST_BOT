"""
BOT PRINCIPAL - MODO CONTINUO
"""

import time
import threading
from datetime import datetime
from tiempo import obtener_hora_actual
import config
import asyncio
import signals as signals
from notificacion import enviar_mensaje, notificar_entrada
import websocket_master_client


async def notificar_signal_websocket(señal_trading):
    """Ejemplo de cómo usar el cliente"""
    
    # Crear cliente y conectar
    cliente = websocket_master_client.WebSocketMaster(
        room_name=config.room_name,
        token=config.token,
        dominio=config.dominio
    )
    
    try:
        await cliente.connect()
        await cliente.send(señal_trading)
        await asyncio.sleep(1)  # Esperar un momento
    finally:
        await cliente.disconnect()


# Lock para evitar ejecuciones simultáneas
ejecucion_lock = threading.Lock()

def inicializar():
    """Inicializa el bot"""
    print("=" * 50)
    print("BOT DE TRADING - MODO CONTINUO")
    print("=" * 50)
    
    print(f"Pares configurados: {', '.join(config.PARES.keys())}")
    print(f"Modo: {config.MODO_OPERACION}")
    print(f"Temporalidad: {config.temporalidad_operacion}")
    print(f"Riesgo por operación: {config.PORCENTAJE_RIESGO}%")
    if config.TELEGRAM_TOKEN and config.TELEGRAM_CHANNEL:
        enviar_mensaje(f"🤖 Bot iniciado\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def ejecutar_tareas_segun_hora(ahora):
    """Ejecuta las tareas correspondientes según la hora actual"""
    with ejecucion_lock:
        minuto_actual = ahora.minute
        hora_actual = ahora.hour
        en_horario = False
        if config.HORAS_PERMITIDAS:
            if hora_actual in config.HORAS_PERMITIDAS:
                en_horario = True
        else:
            en_horario =True
        
        if en_horario:
            print(f"\n[{ahora.strftime('%H:%M:%S')}] 🔄 Verificando tareas...")
            
            ejecutar = False
            if config.temporalidad_operacion == "1hour" and minuto_actual == 0:
                ejecutar = True
            elif config.temporalidad_operacion == "15min" and minuto_actual % 15 == 0:
                ejecutar = True
            elif config.temporalidad_operacion == "5min" and minuto_actual % 5 == 0:
                ejecutar = True
            
            if ejecutar:
                print(f"[{ahora.strftime('%H:%M:%S')}] 🔍 Ejecutando Búsqueda {config.temporalidad_operacion}...")
                señales = []
                for par, cuentas in config.PARES.items():
                    if len(cuentas) > 0:
                        señal = signals.buscar_entradas_quiebre(par=par,cuenta=cuentas[0],intervalo=config.temporalidad_operacion)
                        print(f"[{ahora.strftime('%H:%M:%S')}] ✅ Búsqueda {config.temporalidad_operacion} completada")

                    if señal:
                        señales.append(señal)
                        if config.MODO_OPERACION == 'REAL':
                            print(f"\n[{ahora.strftime('%H:%M:%S')}] 🚀 Ejecutando señales encontradas...")
                            asyncio.run(notificar_signal_websocket(señal_trading=señal))
                            
                if señales:
                    for señal in señales:
                        notificar_entrada(señal=señal)
                if not señales:
                    print(f"\n[{ahora.strftime('%H:%M:%S')}] ⚠️  No se encontraron señales válidas")
            
            else:
                # Si no ejecutó nada, mostrar mensaje
                print(f"[{ahora.strftime('%H:%M:%S')}] ⏭️  No hay tareas programadas para este minuto")



def main():
    """Función principal"""
    inicializar()
    print("\n⏰ Ejecutando en modo continuo (verificación cada minuto)...")
    print("🛑 Presiona Ctrl+C para detener\n")
    
    ultima_verificacion = obtener_hora_actual()
    
    try:
        while True:
            #ahora = datetime.now()
            ahora = obtener_hora_actual()
            # Verificar si el minuto actual es diferente al de la última verificación
            if ahora.minute != ultima_verificacion.minute:
                ultima_verificacion = ahora
                ejecutar_tareas_segun_hora(ahora)
            
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
        
        if config.TELEGRAM_TOKEN and config.TELEGRAM_CHANNEL:
            enviar_mensaje(f"🛑 Bot detenido\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()