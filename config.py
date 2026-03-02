import MetaTrader5 as mt5


# Telegram (configura en .env o aquí)
TELEGRAM_TOKEN = "8308676973:AAF8Wh8BFhKzVlNlALd1UBb995ViE5JvVMQ"
TELEGRAM_CHANNEL = "@trades_liranza"
NOMBRE_BOT = "ELIASBOT_1H-15M\n"

room_name="EURUSD"
token="28c3189f-ff77-4fa2-b6e1-6af6b350c700"
dominio="localhost:8000"

temporalidad_operacion = '15min'
temporalidad_direccion = '4hour'
'''
["1min", "3min", "5min", "15min", "30min", "1hour", "2hour", "4hour", "6hour", "12hour" , "1day", "3day", "1week"]
'''


PARES = {
    'EURUSD':[
        {
            'nombre': 'Elias_100k_Demo',
            'broker': 'MetaQuotesDemo',
            'tipo': 'demo',
            'balance': 100000,
            'moneda': 'USD',
            'riesgo': 0.4,
            'activa': True,
            'sufijo': '',
            'type_filling': mt5.ORDER_FILLING_FOK,
            'credenciales': {
                'numero_cuenta': 103768116,
                'contraseña': '4zVeYe-s',
                'servidor': 'MetaQuotes-Demo',
            }
        }
    ]
}




# Configuración de trading
PORCENTAJE_RIESGO = 0.4  # 1% del balance por operación
MODO_OPERACION = "REAL"  # "ANALISIS" o "REAL"

HORAS_PERMITIDAS = [1, 2, 3, 7, 10, 11, 15, 16, 19, 20, 21, 23]

MIN_BODY_RATIO = 0
MAX_WICK_RATIO = 1
VOLUME_MULTIPLIER = 0
rr_ratio = 0.5
SL_BUFFER = 8
PIP_VALUE = 0.0001