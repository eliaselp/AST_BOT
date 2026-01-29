"""
BOT PRINCIPAL - MODO CONTINUO
"""
import time
import schedule
import threading
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHANNEL
from direccion import verificar_direccion_1h
from precision import buscar_entradas_15m, buscar_entradas_5m
from notificacion import enviar_mensaje

# Lock para evitar ejecuciones simultáneas
ejecucion_lock = threading.Lock()

def inicializar():
    """Inicializa el bot"""
    print("=" * 50)
    print("🤖 BOT DE TRADING - MODO CONTINUO")
    print("=" * 50)
    
    if TELEGRAM_TOKEN and TELEGRAM_CHANNEL:
        enviar_mensaje(f"🤖 Bot iniciado\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def ejecutar_tareas_segun_hora():
    """Ejecuta las tareas correspondientes según la hora actual"""
    with ejecucion_lock:
        ahora = datetime.now()
        minuto_actual = ahora.minute
        hora_actual = ahora.hour
        
        print(f"\n[{ahora.strftime('%H:%M:%S')}] 🔄 Verificando tareas...")
        
        # Siempre en orden: 1H → 15M → 5M
        
        # 1. Verificar si toca ejecutar 1H (cada hora en minuto 0)
        if minuto_actual == 0:
            print(f"[{ahora.strftime('%H:%M:%S')}] 📊 Ejecutando Verificación 1H...")
            verificar_direccion_1h()
            print(f"[{ahora.strftime('%H:%M:%S')}] ✅ Verificación 1H completada")
        
        # 2. Verificar si toca ejecutar 15M (cada 15 minutos: 0, 15, 30, 45)
        if minuto_actual % 15 == 0:
            print(f"[{ahora.strftime('%H:%M:%S')}] 🔍 Ejecutando Búsqueda 15M...")
            buscar_entradas_15m()
            print(f"[{ahora.strftime('%H:%M:%S')}] ✅ Búsqueda 15M completada")
        
        # 3. Verificar si toca ejecutar 5M (cada 5 minutos)
        if minuto_actual % 5 == 0:
            print(f"[{ahora.strftime('%H:%M:%S')}] 🔎 Ejecutando Búsqueda 5M...")
            buscar_entradas_5m()
            print(f"[{ahora.strftime('%H:%M:%S')}] ✅ Búsqueda 5M completada")
        
        # Si no ejecutó nada, mostrar mensaje
        if not (minuto_actual == 0 or minuto_actual % 15 == 0 or minuto_actual % 5 == 0):
            print(f"[{ahora.strftime('%H:%M:%S')}] ⏭️  No hay tareas programadas para este minuto")

def ejecutar_primera_verificacion():
    """Ejecuta la primera verificación completa"""
    with ejecucion_lock:
        ahora = datetime.now()
        print(f"\n[{ahora.strftime('%H:%M:%S')}] 🚀 Ejecutando primera verificación completa...")
        
        print(f"[{ahora.strftime('%H:%M:%S')}] 📊 Verificación 1H...")
        verificar_direccion_1h()
        
        print(f"[{ahora.strftime('%H:%M:%S')}] 🔍 Búsqueda 15M...")
        buscar_entradas_15m()
        
        print(f"[{ahora.strftime('%H:%M:%S')}] 🔎 Búsqueda 5M...")
        buscar_entradas_5m()
        
        print(f"[{ahora.strftime('%H:%M:%S')}] ✅ Verificación inicial COMPLETADA")

def main():
    """Función principal"""
    inicializar()
    
    # Programar UNA SOLA ejecución cada 5 minutos
    print("\n⏰ Programando ejecución única cada 5 minutos...")
    
    # Solo un schedule que se ejecuta cada 5 minutos en :00
    schedule.every(5).minutes.at(":00").do(ejecutar_tareas_segun_hora)
    print("  ✅ Tareas programadas: cada 5 minutos")
    print("     • 1H: cada hora en minuto 0")
    print("     • 15M: cada 15 minutos (0, 15, 30, 45)")
    print("     • 5M: cada 5 minutos")
    
    # Ejecutar primera verificación completa
    ejecutar_primera_verificacion()
    
    # Bucle principal
    print("\n🔄 Entrando en modo continuo...")
    print("🛑 Presiona Ctrl+C para detener\n")
    
    try:
        while True:
            schedule.run_pending()
            
            # Mostrar tiempo para próxima ejecución
            segundos = schedule.idle_seconds()
            if segundos > 0:
                minutos = segundos / 60
                if ejecucion_lock.locked():
                    estado = "⏳ Ejecutando..."
                else:
                    estado = "✅ Listo"
                print(f"⏰ Próxima ejecución en {minutos:.1f} min | {estado}", end='\r')
            
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