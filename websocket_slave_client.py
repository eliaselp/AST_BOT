#!/usr/bin/env python3
"""
WebSocket Client Slave - Escucha señales y las guarda en archivo JSON con UUID
"""

import asyncio
import websockets
import json
import uuid
import os
import time
from datetime import datetime
import signal
import sys

class WebSocketSlave:
    """Cliente esclavo que escucha señales y las guarda en archivo JSON"""
    
    def __init__(self, room_name, token, json_file_path, dominio="localhost:8000"):
        """
        Inicializa el cliente esclavo
        
        Args:
            room_name (str): Nombre de la sala
            token (str): Token de autenticación
            json_file_path (str): Ruta del archivo JSON donde guardar las señales
            dominio (str): Dominio y puerto del servidor
        """
        self.room_name = room_name
        self.token = token
        self.json_file_path = json_file_path
        self.ws_url = f"ws://{dominio}/ws/room/{room_name}/{token}/"
        self.websocket = None
        self.running = True
        self.reconnect_delay = 5  # Segundos antes de reconectar
        self.last_signal_uuid = None
        
        # Asegurar que el directorio existe
        self._ensure_directory_exists()
        
    def _ensure_directory_exists(self):
        """Crea el directorio para el archivo JSON si no existe"""
        directory = os.path.dirname(self.json_file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"📁 Directorio creado: {directory}")
    
    def _generate_uuid(self):
        """Genera un UUID único para la señal"""
        return str(uuid.uuid4())
    
    def _save_signal_to_json(self, signal_data):
        """
        Guarda la señal en el archivo JSON
        
        Args:
            signal_data (dict): Datos de la señal a guardar
        """
        try:
            # Agregar UUID a la señal
            signal_uuid = self._generate_uuid()
            signal_data['uuid'] = signal_uuid
            signal_data['timestamp'] = datetime.now().isoformat()
            
            # Guardar en archivo
            with open(self.json_file_path, 'w', encoding='utf-8') as f:
                json.dump(signal_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Señal guardada en {self.json_file_path}")
            print(f"   UUID: {signal_uuid}")
            print(f"   Par: {signal_data.get('par', 'N/A')}")
            print(f"   Tipo: {signal_data.get('tipo', 'N/A')}")
            
            self.last_signal_uuid = signal_uuid
            
        except Exception as e:
            print(f"❌ Error guardando señal: {e}")
    
    def _parse_message(self, message):
        """
        Parsea el mensaje recibido del WebSocket
        
        Args:
            message (str): Mensaje recibido
            
        Returns:
            dict or None: Datos de la señal o None si no es un comando válido
        """
        try:
            data = json.loads(message)
            
            # Verificar si es un comando
            if data.get('type') == 'command':
                command_str = data.get('command', '{}')
                signal_data = json.loads(command_str)
                
                # Validar que tiene los campos mínimos requeridos
                required_fields = ['par', 'tipo', 'entrada', 'sl', 'tp']
                if all(field in signal_data for field in required_fields):
                    return signal_data
                else:
                    print(f"⚠️ Comando incompleto, faltan campos requeridos")
                    return None
            else:
                print(f"ℹ️ Mensaje recibido (no es comando): {data}")
                return None
                
        except json.JSONDecodeError as e:
            print(f"❌ Error decodificando JSON: {e}")
            print(f"   Mensaje: {message}")
            return None
    
    async def connect(self):
        """Establece la conexión WebSocket"""
        try:
            print(f"🔄 Conectando a {self.ws_url}")
            self.websocket = await websockets.connect(self.ws_url)
            print(f"✅ Conectado a '{self.room_name}' como SLAVE")
            print(f"📁 Guardando señales en: {self.json_file_path}")
            return True
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            return False
    
    async def listen(self):
        """
        Escucha mensajes del WebSocket y los procesa
        """
        while self.running:
            try:
                # Verificar si hay conexión
                if not self.websocket:
                    print("🔄 Reconectando...")
                    if not await self.connect():
                        await asyncio.sleep(self.reconnect_delay)
                        continue
                
                # Esperar mensaje
                message = await self.websocket.recv()
                
                # Procesar mensaje
                signal_data = self._parse_message(message)
                if signal_data:
                    self._save_signal_to_json(signal_data)
                
            except websockets.exceptions.ConnectionClosed:
                print("🔌 Conexión cerrada. Intentando reconectar...")
                self.websocket = None
                await asyncio.sleep(self.reconnect_delay)
                
            except Exception as e:
                print(f"❌ Error en la comunicación: {e}")
                self.websocket = None
                await asyncio.sleep(self.reconnect_delay)
    
    async def disconnect(self):
        """Cierra la conexión"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            print("🔌 Desconectado")
    
    def stop(self):
        """Detiene el cliente (para uso con señales)"""
        self.running = False

def signal_handler(slave_client):
    """Manejador de señales para cierre graceful"""
    print("\n🛑 Recibida señal de terminación")
    slave_client.stop()

async def main():
    """Función principal"""
    
    # CONFIGURACIÓN - AJUSTA ESTOS VALORES
    ROOM_NAME = "PRIMERA-SALA"
    TOKEN = ""
    DOMINIO = "localhost:8000"
    
    # Ruta del archivo JSON (DEBE COINCIDIR CON LA DEL EA)
    JSON_FILE_PATH = "C:\\señales\\senal.json"  # Windows
    # JSON_FILE_PATH = "/home/user/senales/senal.json"  # Linux/Mac
    
    # Crear cliente esclavo
    slave = WebSocketSlave(
        room_name=ROOM_NAME,
        token=TOKEN,
        json_file_path=JSON_FILE_PATH,
        dominio=DOMINIO
    )
    
    # Configurar manejo de señales para cierre graceful
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(slave.disconnect()))
    
    print("=" * 60)
    print("🚀 WEB SOCKET CLIENT SLAVE INICIADO")
    print("=" * 60)
    print(f"📡 Sala: {ROOM_NAME}")
    print(f"🔑 Token: {TOKEN}")
    print(f"🌐 Servidor: {DOMINIO}")
    print(f"📁 Archivo JSON: {JSON_FILE_PATH}")
    print("=" * 60)
    print("Esperando señales...")
    print("Presiona Ctrl+C para detener")
    print("=" * 60)
    
    try:
        # Conectar y empezar a escuchar
        if await slave.connect():
            await slave.listen()
    except KeyboardInterrupt:
        print("\n👋 Deteniendo por solicitud del usuario")
    finally:
        await slave.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Programa terminado")