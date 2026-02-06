"""
MÓDULO DE NOTIFICACIONES SIMPLE
"""
import requests
import time
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHANNEL, NOMBRE_BOT

def enviar_mensaje(texto):
    """Envía mensaje simple a Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL:
        print("⚠️ Telegram no configurado")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    datos = {
        "chat_id": TELEGRAM_CHANNEL,
        "text": NOMBRE_BOT + texto,
        "parse_mode": "HTML"
    }
    
    try:
        respuesta = requests.post(url, json=datos, timeout=10)
        if respuesta.status_code == 200:
            return True
        print(respuesta)
    except Exception as e:
        print(e)
        pass
    return False

def notificar_direccion(par, direccion, datos):
    """Notifica cambio de dirección"""
    mensaje = f"""
📊 <b>DIRECCIÓN ACTUALIZADA - {par.replace('=X','')}</b>
{'📈' if direccion=='LONG' else '📉'} <b>{direccion}</b>

• Hora: {datetime.now().strftime('%H:%M:%S')}
• Precio: {datos['close']:.5f}
"""
    enviar_mensaje(mensaje)

def notificar_entrada(señal):
    """Notifica señal de entrada"""
    par = señal['par'].replace('=X','')
    mensaje = f"""
{'📈' if 'LONG' in señal['tipo'] else '📉'} <b>SEÑAL - {par} {señal['temporalidad']}</b>
• Tipo: {señal['tipo']}
• Entrada: {señal['entrada']:.5f}
• SL: {señal['sl']:.5f}
• TP: {señal['tp']:.5f}
• Pips SL: {señal['pips_sl']}
• Ratio: 1:{señal['ratio']}
"""
    enviar_mensaje(mensaje)
    
    
    
    
#enviar_mensaje("ESTO ES UN MENSAJE DE PRUEBA DEL NUEVO BOT")


