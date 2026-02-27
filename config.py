import MetaTrader5 as mt5


# Telegram (configura en .env o aquí)
TELEGRAM_TOKEN = "8308676973:AAF8Wh8BFhKzVlNlALd1UBb995ViE5JvVMQ"
TELEGRAM_CHANNEL = "@trades_liranza"
NOMBRE_BOT = "ELIASBOT_1H-15M\n"

room_name="PRIMERA-SALA",
token="9e273534-4fe6-49b5-9b81-45a75912bf57",
dominio="216.226.149.70:8000"

temporalidad_operacion = '15min'
temporalidad_direccion = '4hour'
'''
["1min", "3min", "5min", "15min", "30min", "1hour", "2hour", "4hour", "6hour", "12hour" , "1day", "3day", "1week"]
'''


PARES = {
    'EURUSD':[
        {
            'nombre': 'Elias_100k',
            'broker': 'ORIONFUNDED',
            'tipo': 'challenche',
            'balance': 100000,
            'moneda': 'USD',
            'riesgo': 0.25,
            'activa': True,
            'sufijo': '',
            'type_filling': mt5.ORDER_FILLING_FOK,
            'credenciales': {
                'numero_cuenta': 80557170,
                'contraseña': '24jfur$YgO',
                'servidor': 'OGMInternational-Server',
                
            }
        }
    ]
}




# Configuración de trading
PORCENTAJE_RIESGO = 0.25  # 1% del balance por operación
MODO_OPERACION = "REAL"  # "ANALISIS" o "REAL"

HORAS_PERMITIDAS = [0,1,2,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,21,22,23,3,20]

MIN_BODY_RATIO = 0.60
MAX_WICK_RATIO = 0.40
VOLUME_MULTIPLIER = 0
rr_ratio = 0.5
SL_BUFFER = 1
PIP_VALUE = 0.0001