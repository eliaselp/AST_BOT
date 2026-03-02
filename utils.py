
import config
from data_metatrader5 import abrir_operacion_mercado

def ejecutar_señales_en_cuentas(señal,CUENTAS):
    """Ejecuta las señales en todas las cuentas configuradas"""
    if not señal:
        print("   ⚠️  No hay señales para ejecutar")
        return False
    
    resultados = {}
    resultados[señal['par']] = {}
    print(f"\n   🎯 Procesando señal para {señal['par']}:")
    print(f"      Tipo: {señal['tipo']}")
    print(f"      Entrada: {señal['entrada']:.5f}")
    print(f"      SL: {señal['sl']:.5f}")
    print(f"      TP: {señal['tp']:.5f}")
    print(f"      Pips SL: {señal['pips_sl']}")
    print(f"      Ratio: {señal['ratio']}:1")
    
    # Ejecutar en cada cuenta
    for cuenta_config in CUENTAS:
        nombre_cuenta = cuenta_config.get('nombre', f"Cuenta {cuenta_config['credenciales']['numero_cuenta']}")
        servidor = cuenta_config['credenciales']['servidor']
        numero_cuenta = cuenta_config['credenciales']['numero_cuenta']
        contraseña = cuenta_config['credenciales']['contraseña']
        balance_cuenta = cuenta_config.get('balance', 0)
        
        print(f"\n      🔄 Procesando en {nombre_cuenta}...")
        
        # Determinar tipo de operación
        tipo_operacion = "COMPRA" if "LONG" in señal['tipo'] else "VENTA"
        
        if config.MODO_OPERACION == "REAL":
            # Ejecutar operación REAL usando el método de data_metatrader5
            resultado = abrir_operacion_mercado(
                type_filling=cuenta_config['type_filling'],
                servidor=servidor,
                numero_cuenta=numero_cuenta,
                contraseña=contraseña,
                simbolo=señal['par'],
                balance_cuenta=balance_cuenta,
                precio_sl=señal['sl'],
                tipo_operacion=tipo_operacion,
                porcentaje_riesgo=cuenta_config['riesgo'],
                rr_ratio=config.rr_ratio,
                ruta=cuenta_config['credenciales']['ruta']
            )
            if resultado:
                print(f"      ✅ {nombre_cuenta}: Operación exitosa - Ticket {resultado.order}")
                resultados[señal['par']][nombre_cuenta] = {
                    'exito': True,
                    'ticket': resultado.order,
                    'volumen': resultado.volume,
                    'precio_ejecutado': resultado.price
                }
                
            else:
                print(f"      ❌ {nombre_cuenta}: Error ejecutando operación")
                resultados[señal['par']][nombre_cuenta] = {'exito': False}
    return resultados

