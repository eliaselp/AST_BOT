
# Telegram (configura en .env o aquí)
TELEGRAM_TOKEN = "8308676973:AAF8Wh8BFhKzVlNlALd1UBb995ViE5JvVMQ"
TELEGRAM_CHANNEL = "@trades_liranza"
NOMBRE_BOT = "ELIASBOT_1H\n"


temporalidad = '1hour'
'''
["1min", "3min", "5min", "15min", "30min", "1hour", "2hour", "4hour", "6hour", "12hour" , "1day", "3day", "1week"]
'''
rr_ratio = 2.0

# Cuenta principal
CUENTA_PRINCIPAL = {
    'nombre':'Elias_5000',
    'servidor': 'MetaQuotes-Demo',
    'numero_cuenta': 5045818191,
    'contraseña': 'P-5qXqGy',
    'balance':5000,
    'pares':[
        'EURUSD'
    ]
}
PARES = {
    'EURUSD':[
        {
            'nombre':'Elias_5000',
            'servidor': 'MetaQuotes-Demo',
            'numero_cuenta': 5045818191,
            'contraseña': 'P-5qXqGy',
            'balance':5000,
        }
    ]
}




# Configuración de trading
PORCENTAJE_RIESGO = 0.25  # 1% del balance por operación
MAX_OPERACIONES_SIMULTANEAS = 2
MAX_DURACION_VELAS = 2
MODO_OPERACION = "ANALISIS"  # "ANALISIS" o "REAL"
