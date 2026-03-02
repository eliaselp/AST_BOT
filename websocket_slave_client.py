#!/usr/bin/env python3
import asyncio
import websockets
import json
import uuid
import os
from datetime import datetime
import sys

class WebSocketSlave:
    def __init__(self, room_name, token, json_file_path, dominio="localhost:8000"):
        self.room_name = room_name
        self.token = token
        self.json_file_path = json_file_path
        self.ws_url = f"ws://{dominio}/ws/room/{room_name}/{token}/"
        self.websocket = None
        self.running = True
        self.reconnect_delay = 5
        self.last_signal_uuid = None
        self._ensure_directory_exists()
        
    def _ensure_directory_exists(self):
        directory = os.path.dirname(self.json_file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"Directorio creado: {directory}")
    
    def _generate_uuid(self):
        return str(uuid.uuid4())
    
    def _save_signal_to_json(self, signal_data):
        try:
            signal_uuid = self._generate_uuid()
            signal_data['uuid'] = signal_uuid
            signal_data['timestamp'] = datetime.now().isoformat()
            
            with open(self.json_file_path, 'w', encoding='utf-8') as f:
                json.dump(signal_data, f, indent=2, ensure_ascii=False)
            
            print(f"Señal guardada en {self.json_file_path}")
            print(f"UUID: {signal_uuid}")
            print(f"Par: {signal_data.get('par', 'N/A')}")
            print(f"Tipo: {signal_data.get('tipo', 'N/A')}")
            
            self.last_signal_uuid = signal_uuid
            
        except Exception as e:
            print(f"Error guardando señal: {e}")
    
    def _parse_message(self, message):
        try:
            data = json.loads(message)
            
            if data.get('type') == 'command':
                command_str = data.get('command', '{}')
                signal_data = json.loads(command_str)
                
                required_fields = ['par', 'tipo', 'entrada', 'sl', 'tp']
                if all(field in signal_data for field in required_fields):
                    return signal_data
                else:
                    print(f"Comando incompleto, faltan campos requeridos")
                    return None
            else:
                return None
                
        except json.JSONDecodeError as e:
            print(f"Error decodificando JSON: {e}")
            return None
    
    async def connect(self):
        try:
            print(f"Conectando a {self.ws_url}")
            self.websocket = await websockets.connect(self.ws_url)
            print(f"Conectado a '{self.room_name}' como SLAVE")
            print(f"Guardando señales en: {self.json_file_path}")
            return True
        except Exception as e:
            print(f"Error de conexión: {e}")
            return False
    
    async def listen(self):
        while self.running:
            try:
                if not self.websocket:
                    print("Reconectando...")
                    if not await self.connect():
                        await asyncio.sleep(self.reconnect_delay)
                        continue
                
                message = await self.websocket.recv()
                signal_data = self._parse_message(message)
                
                if signal_data:
                    self._save_signal_to_json(signal_data)
                
            except websockets.exceptions.ConnectionClosed:
                print("Conexión cerrada. Intentando reconectar...")
                self.websocket = None
                await asyncio.sleep(self.reconnect_delay)
                
            except Exception as e:
                print(f"Error en la comunicación: {e}")
                self.websocket = None
                await asyncio.sleep(self.reconnect_delay)
    
    async def disconnect(self):
        self.running = False
        if self.websocket:
            await self.websocket.close()
            print("Desconectado")
    
    def stop(self):
        self.running = False

async def main():
    ROOM_NAME = "EURUSD"
    TOKEN = "d519c54e-cb1d-465f-b561-c8013d68b76b"
    DOMINIO = "216.226.149.70:8000"
    JSON_FILE_PATH = "C:\\Users\\InfosaicUser\\AppData\\Roaming\\MetaQuotes\\Terminal\\D0E8209F77C8CF37AD8BF550E51FF075\\MQL5\\Files\\senal.json"
    
    slave = WebSocketSlave(
        room_name=ROOM_NAME,
        token=TOKEN,
        json_file_path=JSON_FILE_PATH,
        dominio=DOMINIO
    )
    
    print("=" * 60)
    print("WEB SOCKET CLIENT SLAVE INICIADO")
    print("=" * 60)
    print(f"Sala: {ROOM_NAME}")
    print(f"Token: {TOKEN}")
    print(f"Servidor: {DOMINIO}")
    print(f"Archivo JSON: {JSON_FILE_PATH}")
    print("=" * 60)
    print("Esperando señales...")
    print("Presiona Ctrl+C para detener")
    print("=" * 60)
    
    try:
        if await slave.connect():
            await slave.listen()
    except KeyboardInterrupt:
        print("\nDeteniendo por solicitud del usuario")
    finally:
        await slave.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPrograma terminado")
