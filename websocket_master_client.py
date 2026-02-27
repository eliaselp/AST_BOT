#!/usr/bin/env python3
"""
Cliente WebSocket Master - Versión Simple
"""

import asyncio
import websockets
import json

class WebSocketMaster:
    """Cliente simple para conectarse como master a una sala WebSocket"""
    
    def __init__(self, room_name, token, dominio="localhost:8000"):
        self.room_name = room_name
        self.token = token
        self.ws_url = f"ws://{dominio}/ws/room/{room_name}/{token}/"
        self.websocket = None
    
    async def connect(self):
        """Establece la conexión WebSocket"""
        self.websocket = await websockets.connect(self.ws_url)
        print(f"✅ Conectado a '{self.room_name}' como MASTER")
        return self.websocket
    
    async def send(self, data_dict):
        """
        Envía un diccionario como comando
        
        Args:
            data_dict (dict): Diccionario con los datos a enviar
        """
        if not self.websocket:
            raise Exception("No hay conexión. Ejecuta connect() primero")
        
        mensaje = {
            'type': 'command',
            'command': json.dumps(data_dict)
        }
        
        await self.websocket.send(json.dumps(mensaje))
        print(f"📤 Enviado: {json.dumps(data_dict, indent=2)}")
    
    async def disconnect(self):
        """Cierra la conexión"""
        if self.websocket:
            await self.websocket.close()
            print("🔌 Desconectado")






async def ejemplo_uso():
    """Ejemplo de cómo usar el cliente"""
    
    # Diccionario con tu formato específico
    señal_trading = {
        'par': 'EUR/USD',
        'tipo': 'COMPRA',
        'temporalidad': '1h',
        'entrada': 1.12345,
        'sl': 1.12000,
        'tp': 1.13500,
        'pips_sl': 34.5,
        'ratio': 3.0
    }
    
    # Crear cliente y conectar
    cliente = WebSocketMaster(
        room_name="PRIMERA-SALA",
        token="9e273534-4fe6-49b5-9b81-45a75912bf57",
        dominio="216.226.149.70:8000"
    )
    
    try:
        await cliente.connect()
        await cliente.send(señal_trading)
        await asyncio.sleep(1)  # Esperar un momento
    finally:
        await cliente.disconnect()

if __name__ == "__main__":
    asyncio.run(ejemplo_uso())