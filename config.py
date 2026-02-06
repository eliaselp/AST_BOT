"""
CONFIGURACIÓN SIMPLE
"""
import os
from persistencia import cargar_direcciones, guardar_direcciones
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Telegram (configura en .env o aquí)
TELEGRAM_TOKEN = "8308676973:AAF8Wh8BFhKzVlNlALd1UBb995ViE5JvVMQ"
TELEGRAM_CHANNEL = "@trades_liranza"

NOMBRE_BOT = 'ABRAHAM SCALPER 1H + 5min.\n'

# Cuenta principal
CUENTA_PRINCIPAL = {
    'nombre':'Elias_5000',
    'servidor': 'MetaQuotes-Demo',
    'numero_cuenta': 5045818191,
    'contraseña': 'P-5qXqGy',
    'balance':5000
}

# Cuentas secundarias (lista)
CUENTAS_SECUNDARIAS = [
    #{
    #    'nombre': 'Elias_100000',
    #    'servidor': 'MetaQuotes-Demo',
    #    'numero_cuenta': 102350889,
    #    'contraseña': 'EpIy@b2e',
    #    'balance': 100000
    #},
    #{
    #    'nombre': 'Elias_50000',
    #    'servidor': 'MetaQuotes-Demo',
    #    'numero_cuenta': 5045899250,
    #    'contraseña': '*b6jGuNb',
    #    'balance': 50000
    #},
]


# Configuración de trading
PORCENTAJE_RIESGO = 1.0  # 1% del balance por operación
MAX_OPERACIONES_SIMULTANEAS = 1  # Máximo de operaciones por cuenta

# Modo de operación
MODO_OPERACION = "ANALISIS"  # "ANALISIS" o "REAL"
if MODO_OPERACION == 'ANALISIS':
    CUENTA_PRINCIPAL=None
    CUENTAS_SECUNDARIAS = []
# Pares a operar
PARES = ["EURUSD"] 

# Configuración de riesgo
MAX_PIPS_SL = 10
RATIO_2VELAS = 3
RATIO_1VELA = 2

# Variable global de dirección
direccion_global = {par: None for par in PARES}
temporalidad_direccion = '1hour'
temporalidad_precision = '5min'


hora_inicio = 0
hora_fin = 24
'''
["1min", "3min", "5min", "15min", "30min", "1hour", "2hour", "4hour", "6hour", "12hour" , "1day", "3day", "1week"]
'''



# Variable global de dirección (se carga desde archivo o se inicializa)
def inicializar_direcciones(temporalidad_direccion=temporalidad_direccion):
    """Inicializa direcciones desde archivo JSON o crea valores por defecto"""
    # Cargar direcciones guardadas
    direcciones_guardadas = cargar_direcciones(temporalidad=temporalidad_direccion)
    
    
    # Crear diccionario con valores por defecto
    direcciones = {}
    
    for par in PARES:
        if par in direcciones_guardadas:
            # Usar dirección guardada si existe
            direccion_valor = direcciones_guardadas[par]
            if direccion_valor in ["LONG", "SHORT"]:
                direcciones[par] = direccion_valor
                print(f"📖 {par}: Dirección cargada desde archivo - {direccion_valor}")
            else:
                direcciones[par] = None
                print(f"⚠️  {par}: Dirección inválida en archivo, se inicializa como None")
        else:
            # Valor por defecto si no existe en archivo
            direcciones[par] = None
            print(f"🔧 {par}: Sin dirección previa, inicializado como None")
    
    # Si no existe archivo o hay pares nuevos, guardar configuración actual
    if not os.path.exists("direccion.json") or set(PARES) != set(direcciones_guardadas.keys()):
        # Crear archivo con todos los pares actuales
        datos_guardar = {}
        for par in PARES:
            datos_guardar[par] = direcciones.get(par)
        guardar_direcciones(datos_guardar, temporalidad_direccion)
    
    return direcciones

# Inicializar variable global
direccion_global = inicializar_direcciones()


def actualizar_direccion_global(par: str, direccion: str, temporalidad=temporalidad_direccion):
    """Actualiza la dirección global y la guarda en el archivo JSON"""
    global direccion_global
    try:
        # Importar aquí para evitar dependencia circular
        from persistencia import actualizar_direccion
        
        # Actualizar en memoria
        direccion_global[par] = direccion
        
        # Guardar en archivo
        if actualizar_direccion(par, direccion, temporalidad):
            print(f"✅ {par}: Dirección actualizada globalmente y guardada - {direccion}")
            return True
        else:
            print(f"⚠️  {par}: Dirección actualizada solo en memoria - {direccion}")
            return False
    except Exception as e:
        print(f"❌ Error actualizando dirección global: {e}")
        return False