"""
CONFIGURACIÓN SIMPLE
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Telegram (configura en .env o aquí)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL", "")

# Pares a operar
PARES = ["BTCUSDT"] 

# Temporizador (segundos)
INTERVALO_1H = 3600    # 1 hora
INTERVALO_15M = 900    # 15 minutos  
INTERVALO_5M = 300     # 5 minutos

# Configuración de riesgo
MAX_PIPS_SL = 100
RATIO_2VELAS = 3
RATIO_1VELA = 2

# Variable global de dirección
direccion_global = {par: None for par in PARES}


'''
["1min", "3min", "5min", "15min", "30min", "1hour", "2hour", "4hour", "6hour", "12hour" , "1day", "3day", "1week"]
'''