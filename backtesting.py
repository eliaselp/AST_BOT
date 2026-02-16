import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import warnings
import seaborn as sns
import os
from pathlib import Path
warnings.filterwarnings('ignore')

# Configurar estilo de los gráficos
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# Crear carpeta para guardar gráficos
GRAPH_FOLDER = "graficos_backtest_porcentual"
Path(GRAPH_FOLDER).mkdir(exist_ok=True)

class EstrategiaBacktest:
    def __init__(self, csv_file, max_operaciones_simultaneas=2, max_duracion_horas=5, 
                 rr_ratio=2.0, capital_inicial=10000, comision=0.0001, riesgo_por_operacion=0.01):
        """
        Inicializa el backtest con los parámetros configurables
        AHORA TRABAJA EN PORCENTAJES - Riesgo fijo del 1% del capital inicial
        
        Args:
            csv_file: Archivo CSV con datos OHLCV
            max_operaciones_simultaneas: Número máximo de operaciones abiertas (default: 2)
            max_duracion_horas: Duración máxima en horas de una operación (default: 5)
            rr_ratio: Ratio Risk/Reward (default: 2.0 para 1:2)
            capital_inicial: Capital inicial para el backtest (default: 10000)
            comision: Comisión por operación como porcentaje (default: 0.01%)
        """
        self.csv_file = csv_file
        self.max_ops_simultaneas = max_operaciones_simultaneas
        self.max_duracion_horas = max_duracion_horas
        self.rr_ratio = rr_ratio
        self.capital_inicial = capital_inicial
        self.comision = comision
        
        # Definir porcentajes fijos
        self.riesgo_por_operacion =  riesgo_por_operacion # 1% del capital inicial
        self.recompensa_por_operacion = rr_ratio * riesgo_por_operacion  # 2% del capital inicial
        
        # Cargar datos
        self.df = self.cargar_datos()
        
        # Inicializar variables para operaciones
        self.operaciones = []
        self.operaciones_abiertas = []
        
        # Seguimiento del capital en porcentaje
        self.capital_porcentual = 100.0  # Comenzamos en 100%
        self.equity_curve_porcentual = []  # Para guardar evolución
        
    def cargar_datos(self):
        """Carga y prepara los datos del CSV"""
        try:
            df = pd.read_csv(self.csv_file)
            
            # Asegurar que tenemos las columnas necesarias
            columnas_requeridas = ['datetime', 'open', 'high', 'low', 'close', 'volume']
            columnas_alternativas = ['date', 'time', 'fecha', 'hora', 'timestamp']
            
            # Normalizar nombres de columnas
            df.columns = df.columns.str.lower()
            
            # Verificar columnas requeridas
            for col in columnas_requeridas:
                if col not in df.columns:
                    # Buscar alternativa para datetime
                    if col == 'datetime':
                        encontrado = False
                        for col_alt in columnas_alternativas:
                            if col_alt in df.columns:
                                df['datetime'] = pd.to_datetime(df[col_alt])
                                encontrado = True
                                break
                        if not encontrado:
                            raise ValueError(f"No se encontró columna de tiempo en {df.columns.tolist()}")
                    else:
                        raise ValueError(f"Columna '{col}' no encontrada en el CSV")
            
            # Convertir datetime si es necesario
            if 'datetime' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['datetime']):
                df['datetime'] = pd.to_datetime(df['datetime'])
            
            # Ordenar por datetime
            df = df.sort_values('datetime').reset_index(drop=True)
            
            # Identificar tipo de vela
            df['candle_type'] = np.where(df['close'] > df['open'], 'LONG', 'SHORT')
            
            print(f"✅ Datos cargados: {len(df)} velas desde {df['datetime'].iloc[0]} hasta {df['datetime'].iloc[-1]}")
            
            return df
            
        except Exception as e:
            print(f"Error al cargar datos: {e}")
            raise
    
    def verificar_condicion_long(self, idx):
        """Verifica si se cumple condición para LONG en el índice dado"""
        if idx < 1:
            return False
        
        vela_anterior = self.df.iloc[idx-1]
        vela_actual = self.df.iloc[idx]
        
        # Condiciones LONG
        #cond1 = vela_anterior['candle_type'] == 'LONG'
        cond2 = vela_actual['close'] > vela_anterior['high']
        cond3 = vela_actual['low'] > vela_anterior['low']
        
        return  cond2 and cond3
    
    def verificar_condicion_short(self, idx):
        """Verifica si se cumple condición para SHORT en el índice dado"""
        if idx < 1:
            return False
        
        vela_anterior = self.df.iloc[idx-1]
        vela_actual = self.df.iloc[idx]
        
        # Condiciones SHORT
        #cond1 = vela_anterior['candle_type'] == 'SHORT'
        cond2 = vela_actual['close'] < vela_anterior['low']
        cond3 = vela_actual['high'] < vela_anterior['high']
        
        return cond2 and cond3
    
    def calcular_sl_tp_porcentual(self, tipo, idx):
        """
        Calcula SL y TP basado en porcentajes
        SL: 1% del capital inicial
        TP: 2% del capital inicial
        """
        vela_anterior = self.df.iloc[idx-1]
        entrada = self.df.iloc[idx]['open']
        
        # Calcular la distancia en pips para el 1% del capital inicial
        # Asumimos que 1 lote estándar (100,000 unidades) equivale a $10 por pip
        # Para arriesgar 1% del capital inicial, calculamos los pips necesarios
        capital_riesgo = self.capital_inicial * self.riesgo_por_operacion  # 1% en dólares
        pip_value = 10  # $10 por pip para 1 lote estándar
        
        # Calcular tamaño de posición basado en el riesgo fijo
        if tipo == 'LONG':
            distancia_sl_pips = (entrada - vela_anterior['low']) / 0.0001  # Convertir a pips para EURUSD
            # Tamaño de posición para que la pérdida sea exactamente el 1%
            size = capital_riesgo / (distancia_sl_pips * pip_value)
            
            sl = vela_anterior['low']
            tp = entrada + (entrada - sl) * self.rr_ratio
            
        else:  # SHORT
            distancia_sl_pips = (vela_anterior['high'] - entrada) / 0.0001  # Convertir a pips
            size = capital_riesgo / (distancia_sl_pips * pip_value)
            
            sl = vela_anterior['high']
            tp = entrada - (sl - entrada) * self.rr_ratio
        
        # Limitar tamaño máximo para evitar sizes extremos
        size = min(size, 10)  # Máximo 10 lotes
        size = max(size, 0.01)  # Mínimo 0.01 lotes
        
        return entrada, sl, tp, size
    
    def calcular_porcentaje_operacion(self, tipo, entrada, salida, size):
        """
        Calcula el porcentaje ganado/perdido en la operación
        """
        if tipo == 'LONG':
            pnl_dolares = (salida - entrada) * size * 100000
        else:
            pnl_dolares = (entrada - salida) * size * 100000
        
        # Porcentaje respecto al capital inicial
        porcentaje = (pnl_dolares / self.capital_inicial) * 100
        
        return porcentaje, pnl_dolares
    
    def ejecutar_backtest(self):
        """Ejecuta el backtest completo"""
        print("="*60)
        print("INICIANDO BACKTEST - MÉTRICAS PORCENTUALES")
        print("="*60)
        print(f"Capital inicial: ${self.capital_inicial:,.2f} (100%)")
        print(f"Riesgo por operación: {self.riesgo_por_operacion*100}% del capital inicial")
        print(f"Recompensa objetivo: {self.recompensa_por_operacion*100}% del capital inicial")
        print(f"Máximo operaciones simultáneas: {self.max_ops_simultaneas}")
        print(f"Duración máxima por operación: {self.max_duracion_horas} horas")
        print(f"Ratio R:R: 1:{self.rr_ratio}\n")
        
        self.operaciones = []
        ultimo_cierre_tiempo = None
        
        # Registrar evolución del capital
        self.equity_curve_porcentual = []
        
        for i in range(1, len(self.df) - 1):
            datetime_actual = self.df.iloc[i]['datetime']
            
            # Registrar equity actual (en porcentaje)
            pnl_acumulado = sum([op.get('porcentaje', 0) for op in self.operaciones])
            equity_actual = 100 + pnl_acumulado
            self.equity_curve_porcentual.append({
                'datetime': datetime_actual,
                'equity': equity_actual,
                'operaciones_abiertas': len(self.operaciones_abiertas)
            })
            
            # Cerrar operaciones por tiempo máximo
            operaciones_a_cerrar_tiempo = []
            for op in self.operaciones_abiertas:
                horas_transcurridas = (datetime_actual - op['fecha_entrada']).total_seconds() / 3600
                if horas_transcurridas > self.max_duracion_horas:
                    op['fecha_salida'] = datetime_actual
                    op['salida'] = self.df.iloc[i]['open']  # Cerrar al open de la vela actual
                    
                    # Calcular porcentaje ganado/perdido
                    porcentaje, pnl_dolares = self.calcular_porcentaje_operacion(
                        op['tipo'], op['entrada'], op['salida'], op['size']
                    )
                    
                    op['porcentaje'] = porcentaje
                    op['pnl_dolares'] = pnl_dolares
                    op['resultado'] = 'TIEMPO'
                    op['comision_porcentaje'] = self.comision * 100  # Comisión en porcentaje
                    op['porcentaje_neto'] = porcentaje - op['comision_porcentaje']
                    op['estado'] = 'cerrada'
                    operaciones_a_cerrar_tiempo.append(op)
                    ultimo_cierre_tiempo = datetime_actual
            
            # Remover operaciones cerradas por tiempo
            for op in operaciones_a_cerrar_tiempo:
                self.operaciones.append(op)
                self.operaciones_abiertas.remove(op)
            
            # Verificar si podemos abrir nueva operación
            if len(self.operaciones_abiertas) >= self.max_ops_simultaneas:
                continue
            
            # Verificar condiciones de entrada
            entrada_realizada = False
            
            # LONG
            if self.verificar_condicion_long(i):
                entrada, sl, tp, size = self.calcular_sl_tp_porcentual('LONG', i)
                
                # Verificar que el SL y TP son válidos
                if sl < entrada and tp > entrada:
                    operacion = {
                        'tipo': 'LONG',
                        'fecha_entrada': datetime_actual,
                        'entrada': entrada,
                        'sl': sl,
                        'tp': tp,
                        'size': size,
                        'estado': 'abierta'
                    }
                    self.operaciones_abiertas.append(operacion)
                    entrada_realizada = True
                    
                    print(f"  📈 LONG abierta - Entrada: {entrada:.5f}, SL: {sl:.5f}, TP: {tp:.5f}, Size: {size:.2f}")
            
            # SHORT
            if not entrada_realizada and self.verificar_condicion_short(i):
                entrada, sl, tp, size = self.calcular_sl_tp_porcentual('SHORT', i)
                
                # Verificar que el SL y TP son válidos
                if sl > entrada and tp < entrada:
                    operacion = {
                        'tipo': 'SHORT',
                        'fecha_entrada': datetime_actual,
                        'entrada': entrada,
                        'sl': sl,
                        'tp': tp,
                        'size': size,
                        'estado': 'abierta'
                    }
                    self.operaciones_abiertas.append(operacion)
                    
                    print(f"  📉 SHORT abierta - Entrada: {entrada:.5f}, SL: {sl:.5f}, TP: {tp:.5f}, Size: {size:.2f}")
            
            # Simular cierre de operaciones basado en precio
            self.simular_cierres(i)
        
        # Cerrar operaciones restantes al final
        self.cerrar_operaciones_restantes()
        
        # Registrar equity final
        pnl_acumulado = sum([op.get('porcentaje_neto', op.get('porcentaje', 0)) for op in self.operaciones])
        self.equity_curve_porcentual.append({
            'datetime': self.df.iloc[-1]['datetime'],
            'equity': 100 + pnl_acumulado,
            'operaciones_abiertas': 0
        })
        
        # Calcular métricas
        metricas = self.calcular_metricas()
        
        return metricas
    
    def simular_cierres(self, idx):
        """Simula el cierre de operaciones basado en los precios de la vela actual"""
        vela = self.df.iloc[idx]
        operaciones_a_cerrar = []
        
        for op in self.operaciones_abiertas:
            if op['estado'] != 'abierta':
                continue
                
            if op['tipo'] == 'LONG':
                # Verificar si se alcanzó SL o TP
                if vela['low'] <= op['sl']:
                    op['fecha_salida'] = vela['datetime']
                    op['salida'] = op['sl']
                    op['resultado'] = 'SL'
                    
                    # Calcular porcentaje (pérdida del 1% esperada)
                    porcentaje, pnl_dolares = self.calcular_porcentaje_operacion(
                        op['tipo'], op['entrada'], op['salida'], op['size']
                    )
                    
                    op['porcentaje'] = porcentaje
                    op['pnl_dolares'] = pnl_dolares
                    operaciones_a_cerrar.append(op)
                    
                    print(f"    ❌ SL alcanzado - Pérdida: {porcentaje:.2f}%")
                    
                elif vela['high'] >= op['tp']:
                    op['fecha_salida'] = vela['datetime']
                    op['salida'] = op['tp']
                    op['resultado'] = 'TP'
                    
                    # Calcular porcentaje (ganancia del 2% esperada)
                    porcentaje, pnl_dolares = self.calcular_porcentaje_operacion(
                        op['tipo'], op['entrada'], op['salida'], op['size']
                    )
                    
                    op['porcentaje'] = porcentaje
                    op['pnl_dolares'] = pnl_dolares
                    operaciones_a_cerrar.append(op)
                    
                    print(f"    ✅ TP alcanzado - Ganancia: {porcentaje:.2f}%")
                    
            else:  # SHORT
                if vela['high'] >= op['sl']:
                    op['fecha_salida'] = vela['datetime']
                    op['salida'] = op['sl']
                    op['resultado'] = 'SL'
                    
                    porcentaje, pnl_dolares = self.calcular_porcentaje_operacion(
                        op['tipo'], op['entrada'], op['salida'], op['size']
                    )
                    
                    op['porcentaje'] = porcentaje
                    op['pnl_dolares'] = pnl_dolares
                    operaciones_a_cerrar.append(op)
                    
                    print(f"    ❌ SL alcanzado - Pérdida: {porcentaje:.2f}%")
                    
                elif vela['low'] <= op['tp']:
                    op['fecha_salida'] = vela['datetime']
                    op['salida'] = op['tp']
                    op['resultado'] = 'TP'
                    
                    porcentaje, pnl_dolares = self.calcular_porcentaje_operacion(
                        op['tipo'], op['entrada'], op['salida'], op['size']
                    )
                    
                    op['porcentaje'] = porcentaje
                    op['pnl_dolares'] = pnl_dolares
                    operaciones_a_cerrar.append(op)
                    
                    print(f"    ✅ TP alcanzado - Ganancia: {porcentaje:.2f}%")
        
        # Mover operaciones cerradas a la lista principal
        for op in operaciones_a_cerrar:
            op['estado'] = 'cerrada'
            op['comision_porcentaje'] = self.comision * 100  # Comisión en porcentaje
            op['porcentaje_neto'] = op['porcentaje'] - op['comision_porcentaje']
            self.operaciones.append(op)
            self.operaciones_abiertas.remove(op)
    
    def cerrar_operaciones_restantes(self):
        """Cierra las operaciones que quedan abiertas al final del backtest"""
        ultimo_precio = self.df.iloc[-1]['close']
        ultimo_datetime = self.df.iloc[-1]['datetime']
        
        for op in self.operaciones_abiertas:
            op['salida'] = ultimo_precio
            op['fecha_salida'] = ultimo_datetime
            op['resultado'] = 'FIN_DATA'
            
            # Calcular porcentaje
            porcentaje, pnl_dolares = self.calcular_porcentaje_operacion(
                op['tipo'], op['entrada'], op['salida'], op['size']
            )
            
            op['porcentaje'] = porcentaje
            op['pnl_dolares'] = pnl_dolares
            op['comision_porcentaje'] = self.comision * 100
            op['porcentaje_neto'] = porcentaje - op['comision_porcentaje']
            op['estado'] = 'cerrada'
            self.operaciones.append(op)
            
            print(f"    ⏹️ Cierre fin datos - {op['tipo']} - Rent: {porcentaje:.2f}%")
        
        self.operaciones_abiertas = []
    
    def calcular_metricas(self):
        """Calcula todas las métricas del backtest en porcentajes"""
        if not self.operaciones:
            print("No se realizaron operaciones")
            return {}
        
        df_ops = pd.DataFrame(self.operaciones)
        
        # Estadísticas por resultado
        stats_resultados = df_ops['resultado'].value_counts()
        tp_count = stats_resultados.get('TP', 0)
        sl_count = stats_resultados.get('SL', 0)
        tiempo_count = stats_resultados.get('TIEMPO', 0)
        fin_data_count = stats_resultados.get('FIN_DATA', 0)
        
        # Estadísticas detalladas para operaciones cerradas por tiempo
        df_tiempo = df_ops[df_ops['resultado'] == 'TIEMPO']
        if not df_tiempo.empty:
            tiempo_ganadoras = len(df_tiempo[df_tiempo['porcentaje'] > 0])
            tiempo_perdedoras = len(df_tiempo[df_tiempo['porcentaje'] <= 0])
            tiempo_pnl_total = df_tiempo['porcentaje_neto'].sum()
            tiempo_pnl_promedio = df_tiempo['porcentaje_neto'].mean()
            tiempo_win_rate = (tiempo_ganadoras / len(df_tiempo)) * 100 if len(df_tiempo) > 0 else 0
        else:
            tiempo_ganadoras = tiempo_perdedoras = tiempo_pnl_total = tiempo_pnl_promedio = tiempo_win_rate = 0
        
        # Métricas generales
        total_ops = len(df_ops)
        ops_ganadoras = len(df_ops[df_ops['porcentaje'] > 0])
        ops_perdedoras = len(df_ops[df_ops['porcentaje'] <= 0])
        
        # Calcular rachas
        df_ops = df_ops.sort_values('fecha_entrada')
        df_ops['ganadora'] = df_ops['porcentaje'] > 0
        
        # Rachas ganadoras
        max_win_streak = 0
        current_win_streak = 0
        for ganadora in df_ops['ganadora']:
            if ganadora:
                current_win_streak += 1
                max_win_streak = max(max_win_streak, current_win_streak)
            else:
                current_win_streak = 0
        
        # Rachas perdedoras
        max_loss_streak = 0
        current_loss_streak = 0
        for ganadora in df_ops['ganadora']:
            if not ganadora:
                current_loss_streak += 1
                max_loss_streak = max(max_loss_streak, current_loss_streak)
            else:
                current_loss_streak = 0
        
        if total_ops > 0:
            win_rate = (ops_ganadoras / total_ops) * 100
        else:
            win_rate = 0
        
        # PnL en porcentaje
        pnl_total_porcentaje = df_ops['porcentaje_neto'].sum()
        pnl_promedio_porcentaje = df_ops['porcentaje_neto'].mean()
        
        # PnL por resultado
        pnl_por_resultado = df_ops.groupby('resultado').agg({
            'porcentaje_neto': ['sum', 'mean', 'count', 'std']
        }).round(2)
        
        # Métricas por tipo
        longs = df_ops[df_ops['tipo'] == 'LONG']
        shorts = df_ops[df_ops['tipo'] == 'SHORT']
        
        # Duración de operaciones
        df_ops['duracion_horas'] = (pd.to_datetime(df_ops['fecha_salida']) - pd.to_datetime(df_ops['fecha_entrada'])).dt.total_seconds() / 3600
        
        # Métricas mensuales
        df_ops['mes'] = pd.to_datetime(df_ops['fecha_entrada']).dt.to_period('M')
        metricas_mensuales = df_ops.groupby('mes').agg({
            'porcentaje_neto': ['sum', 'count', lambda x: (x > 0).sum() / len(x) * 100]
        }).round(2)
        
        metricas_mensuales.columns = ['Rentabilidad_Mensual_%', 'Operaciones', 'Win_Rate_%']
        
        # Factor de beneficio
        ganancias = df_ops[df_ops['porcentaje_neto'] > 0]['porcentaje_neto'].sum()
        perdidas = abs(df_ops[df_ops['porcentaje_neto'] < 0]['porcentaje_neto'].sum())
        profit_factor = ganancias / perdidas if perdidas != 0 else float('inf')
        
        # Sharpe ratio (basado en retornos porcentuales)
        returns = df_ops['porcentaje_neto'] / 100  # Convertir a decimal
        sharpe = returns.mean() / returns.std() * np.sqrt(252 * 24) if returns.std() != 0 else 0
        
        # Drawdown (basado en equity curve porcentual)
        df_equity = pd.DataFrame(self.equity_curve_porcentual)
        max_capital = df_equity['equity'].expanding().max()
        drawdown = (df_equity['equity'] - max_capital) / max_capital * 100
        max_drawdown = drawdown.min()
        
        # Distribución de rentabilidades
        pnl_stats = {
            'media_%': df_ops['porcentaje_neto'].mean(),
            'mediana_%': df_ops['porcentaje_neto'].median(),
            'std_%': df_ops['porcentaje_neto'].std(),
            'min_%': df_ops['porcentaje_neto'].min(),
            'max_%': df_ops['porcentaje_neto'].max(),
            'q1_%': df_ops['porcentaje_neto'].quantile(0.25),
            'q3_%': df_ops['porcentaje_neto'].quantile(0.75)
        }
        
        # Calcular expectancy
        expectancy = (win_rate/100 * pnl_promedio_porcentaje) - ((1-win_rate/100) * abs(df_ops[df_ops['porcentaje_neto'] < 0]['porcentaje_neto'].mean()))
        
        metricas = {
            'total_operaciones': total_ops,
            'operaciones_ganadoras': ops_ganadoras,
            'operaciones_perdedoras': ops_perdedoras,
            'win_rate': win_rate,
            'pnl_total_%': pnl_total_porcentaje,
            'pnl_promedio_%': pnl_promedio_porcentaje,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'max_drawdown_%': max_drawdown,
            'longs': len(longs),
            'shorts': len(shorts),
            'tp_count': tp_count,
            'sl_count': sl_count,
            'tiempo_count': tiempo_count,
            'fin_data_count': fin_data_count,
            'max_win_streak': max_win_streak,
            'max_loss_streak': max_loss_streak,
            'metricas_mensuales': metricas_mensuales,
            'capital_final_%': 100 + pnl_total_porcentaje,
            'retorno_total_%': pnl_total_porcentaje,
            'pnl_por_resultado': pnl_por_resultado,
            'duracion_promedio': df_ops['duracion_horas'].mean(),
            'duracion_mediana': df_ops['duracion_horas'].median(),
            'pnl_stats': pnl_stats,
            'df_ops': df_ops,
            'df_equity': df_equity,
            'expectancy_%': expectancy,
            # Métricas específicas para cierres por tiempo
            'tiempo_ganadoras': tiempo_ganadoras,
            'tiempo_perdedoras': tiempo_perdedoras,
            'tiempo_pnl_total_%': tiempo_pnl_total,
            'tiempo_pnl_promedio_%': tiempo_pnl_promedio,
            'tiempo_win_rate': tiempo_win_rate
        }
        
        return metricas
    
    def mostrar_resultados(self, metricas):
        """Muestra los resultados del backtest en porcentajes"""
        if not metricas:
            print("No hay métricas para mostrar")
            return
        
        print("\n" + "="*60)
        print("📊 RESULTADOS DEL BACKTEST (MÉTRICAS PORCENTUALES)")
        print("="*60)
        
        print(f"\n📈 ESTADÍSTICAS GENERALES:")
        print(f"  • Total operaciones: {metricas['total_operaciones']}")
        print(f"  • Operaciones ganadoras: {metricas['operaciones_ganadoras']}")
        print(f"  • Operaciones perdedoras: {metricas['operaciones_perdedoras']}")
        print(f"  • Win Rate: {metricas['win_rate']:.2f}%")
        print(f"  • Longs/Shorts: {metricas['longs']}/{metricas['shorts']}")
        print(f"  • Expectancy: {metricas['expectancy_%']:.3f}% por operación")
        
        print(f"\n🎯 RESULTADO POR TIPO DE CIERRE:")
        print(f"  • Take Profit (TP): {metricas['tp_count']} ({metricas['tp_count']/metricas['total_operaciones']*100:.1f}%)")
        print(f"  • Stop Loss (SL): {metricas['sl_count']} ({metricas['sl_count']/metricas['total_operaciones']*100:.1f}%)")
        print(f"  • Cierre por tiempo: {metricas['tiempo_count']} ({metricas['tiempo_count']/metricas['total_operaciones']*100:.1f}%)")
        print(f"  • Cierre fin datos: {metricas['fin_data_count']} ({metricas['fin_data_count']/metricas['total_operaciones']*100:.1f}%)")
        
        print(f"\n⏰ ESTADÍSTICAS DE CIERRES POR TIEMPO:")
        print(f"  • Operaciones cerradas por tiempo: {metricas['tiempo_count']}")
        print(f"  • Ganadoras por tiempo: {metricas['tiempo_ganadoras']} ({metricas['tiempo_win_rate']:.1f}%)")
        print(f"  • Perdedoras por tiempo: {metricas['tiempo_perdedoras']}")
        print(f"  • Rentabilidad total cierres tiempo: {metricas['tiempo_pnl_total_%']:.2f}%")
        print(f"  • Rentabilidad promedio cierre tiempo: {metricas['tiempo_pnl_promedio_%']:.2f}%")
        
        print(f"\n📊 RACHAS:")
        print(f"  • Máxima racha ganadora: {metricas['max_win_streak']} operaciones")
        print(f"  • Máxima racha perdedora: {metricas['max_loss_streak']} operaciones")
        
        print(f"\n💰 RENDIMIENTO PORCENTUAL:")
        print(f"  • Capital inicial: 100%")
        print(f"  • Capital final: {metricas['capital_final_%']:.2f}%")
        print(f"  • Rentabilidad Total: {metricas['retorno_total_%']:+.2f}%")
        print(f"  • Rentabilidad Promedio por operación: {metricas['pnl_promedio_%']:+.2f}%")
        
        print(f"\n📈 RATIOS DE RIESGO:")
        print(f"  • Profit Factor: {metricas['profit_factor']:.2f}")
        print(f"  • Sharpe Ratio: {metricas['sharpe_ratio']:.2f}")
        print(f"  • Max Drawdown: {metricas['max_drawdown_%']:.2f}%")
        
        print(f"\n⏱️  DURACIÓN OPERACIONES:")
        print(f"  • Duración promedio: {metricas['duracion_promedio']:.2f} horas")
        print(f"  • Duración mediana: {metricas['duracion_mediana']:.2f} horas")
        
        print(f"\n📊 ESTADÍSTICAS RENTABILIDAD %:")
        print(f"  • Media: {metricas['pnl_stats']['media_%']:+.2f}%")
        print(f"  • Mediana: {metricas['pnl_stats']['mediana_%']:+.2f}%")
        print(f"  • Desviación std: {metricas['pnl_stats']['std_%']:.2f}%")
        print(f"  • Mínimo: {metricas['pnl_stats']['min_%']:+.2f}%")
        print(f"  • Máximo: {metricas['pnl_stats']['max_%']:+.2f}%")
        print(f"  • Q1 (25%): {metricas['pnl_stats']['q1_%']:+.2f}%")
        print(f"  • Q3 (75%): {metricas['pnl_stats']['q3_%']:+.2f}%")
        
        print(f"\n💰 RENTABILIDAD % POR TIPO DE CIERRE:")
        print(metricas['pnl_por_resultado'])
        
        print(f"\n📅 MÉTRICAS MENSUALES (%):")
        print(metricas['metricas_mensuales'])
        
        # Generar y guardar todos los gráficos
        self.graficar_y_guardar_todo(metricas['df_ops'], metricas['df_equity'])
    
    def graficar_y_guardar_todo(self, df_ops, df_equity):
        """Genera y guarda todos los gráficos estadísticos en porcentajes"""
        if df_ops.empty:
            return
        
        print(f"\n💾 Guardando gráficos en la carpeta '{GRAPH_FOLDER}/'...")
        
        # 1. Gráfico de Equity Curve y Drawdown (en %)
        fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]})
        
        ax1.plot(df_equity['datetime'], df_equity['equity'], color='blue', linewidth=1.5, label='Equity %')
        ax1.axhline(y=100, color='gray', linestyle='--', alpha=0.7, label='Capital Inicial (100%)')
        ax1.fill_between(df_equity['datetime'], 100, df_equity['equity'], 
                         where=(df_equity['equity'] >= 100), color='green', alpha=0.3, label='Ganancias')
        ax1.fill_between(df_equity['datetime'], 100, df_equity['equity'], 
                         where=(df_equity['equity'] < 100), color='red', alpha=0.3, label='Pérdidas')
        ax1.set_title('Curva de Equity (%)', fontweight='bold', fontsize=14)
        ax1.set_ylabel('Capital (%)')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # Calcular drawdown
        max_capital = df_equity['equity'].expanding().max()
        drawdown = (df_equity['equity'] - max_capital) / max_capital * 100
        
        ax2.fill_between(df_equity['datetime'], 0, drawdown, color='red', alpha=0.5)
        ax2.set_title('Drawdown (%)', fontweight='bold', fontsize=14)
        ax2.set_ylabel('Drawdown (%)')
        ax2.set_xlabel('Fecha')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f'{GRAPH_FOLDER}/1_equity_drawdown_porcentual.png', dpi=150, bbox_inches='tight')
        plt.close(fig1)
        
        # 2. Distribución de resultados
        fig2, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        # 2.1 Pie chart de resultados
        resultados = df_ops['resultado'].value_counts()
        colors = {'TP': 'green', 'SL': 'red', 'TIEMPO': 'orange', 'FIN_DATA': 'gray'}
        color_list = [colors.get(r, 'blue') for r in resultados.index]
        axes[0, 0].pie(resultados.values, labels=resultados.index, autopct='%1.1f%%', 
                       colors=color_list, startangle=90)
        axes[0, 0].set_title('Distribución por Tipo de Cierre', fontweight='bold')
        
        # 2.2 Histograma de rentabilidades %
        axes[0, 1].hist(df_ops['porcentaje_neto'], bins=30, color='skyblue', edgecolor='black', alpha=0.7)
        axes[0, 1].axvline(x=0, color='red', linestyle='--', linewidth=2)
        axes[0, 1].axvline(x=df_ops['porcentaje_neto'].mean(), color='green', linestyle='--', 
                          linewidth=2, label=f'Media: {df_ops["porcentaje_neto"].mean():.2f}%')
        axes[0, 1].set_title('Distribución de Rentabilidades (%)', fontweight='bold')
        axes[0, 1].set_xlabel('Rentabilidad (%)')
        axes[0, 1].set_ylabel('Frecuencia')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # 2.3 Boxplot por resultado
        df_ops.boxplot(column='porcentaje_neto', by='resultado', ax=axes[0, 2])
        axes[0, 2].set_title('Rentabilidad % por Resultado', fontweight='bold')
        axes[0, 2].set_ylabel('Rentabilidad (%)')
        axes[0, 2].set_xlabel('Resultado')
        axes[0, 2].grid(True, alpha=0.3)
        
        # 2.4 Duración de operaciones
        axes[1, 0].hist(df_ops['duracion_horas'], bins=30, color='purple', edgecolor='black', alpha=0.7)
        axes[1, 0].axvline(x=self.max_duracion_horas, color='red', linestyle='--', 
                          linewidth=2, label=f'Límite: {self.max_duracion_horas}h')
        axes[1, 0].set_title('Duración de Operaciones', fontweight='bold')
        axes[1, 0].set_xlabel('Horas')
        axes[1, 0].set_ylabel('Frecuencia')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # 2.5 Rentabilidad mensual %
        df_ops['mes'] = pd.to_datetime(df_ops['fecha_entrada']).dt.to_period('M')
        pnl_mensual = df_ops.groupby('mes')['porcentaje_neto'].sum()
        meses = [str(m) for m in pnl_mensual.index]
        colors_bar = ['green' if x > 0 else 'red' for x in pnl_mensual.values]
        axes[1, 1].bar(range(len(pnl_mensual)), pnl_mensual.values, color=colors_bar)
        axes[1, 1].set_title('Rentabilidad Mensual (%)', fontweight='bold')
        axes[1, 1].set_xticks(range(len(pnl_mensual)))
        axes[1, 1].set_xticklabels(meses, rotation=45, ha='right')
        axes[1, 1].set_ylabel('Rentabilidad (%)')
        axes[1, 1].grid(True, alpha=0.3)
        
        # 2.6 Win Rate mensual
        win_rate_mensual = df_ops.groupby('mes').apply(lambda x: (x['porcentaje_neto'] > 0).sum() / len(x) * 100)
        axes[1, 2].plot(range(len(win_rate_mensual)), win_rate_mensual.values, marker='o', 
                       color='blue', linewidth=2, markersize=8)
        axes[1, 2].axhline(y=50, color='red', linestyle='--', alpha=0.7, label='50%')
        axes[1, 2].set_title('Win Rate Mensual', fontweight='bold')
        axes[1, 2].set_xticks(range(len(win_rate_mensual)))
        axes[1, 2].set_xticklabels(meses, rotation=45, ha='right')
        axes[1, 2].set_ylabel('Win Rate (%)')
        axes[1, 2].grid(True, alpha=0.3)
        axes[1, 2].legend()
        
        plt.suptitle('ANÁLISIS ESTADÍSTICO - PARTE 1 (MÉTRICAS %)', fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()
        plt.savefig(f'{GRAPH_FOLDER}/2_analisis_estadistico_parte1_porcentual.png', dpi=150, bbox_inches='tight')
        plt.close(fig2)
        
        # 3. Segundo conjunto de gráficos
        fig3, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        # 3.1 Frecuencia de rachas
        df_ops['ganadora'] = df_ops['porcentaje_neto'] > 0
        rachas = []
        current_streak = 0
        current_type = None
        
        for _, row in df_ops.iterrows():
            if row['ganadora']:
                if current_type == 'win':
                    current_streak += 1
                else:
                    if current_type is not None:
                        rachas.append((current_type, current_streak))
                    current_type = 'win'
                    current_streak = 1
            else:
                if current_type == 'loss':
                    current_streak += 1
                else:
                    if current_type is not None:
                        rachas.append((current_type, current_streak))
                    current_type = 'loss'
                    current_streak = 1
        
        if current_type is not None:
            rachas.append((current_type, current_streak))
        
        rachas_df = pd.DataFrame(rachas, columns=['tipo', 'longitud'])
        rachas_win = rachas_df[rachas_df['tipo'] == 'win']['longitud'].value_counts().sort_index()
        rachas_loss = rachas_df[rachas_df['tipo'] == 'loss']['longitud'].value_counts().sort_index()
        
        x = range(1, max(rachas_win.index.max() if not rachas_win.empty else 0, 
                        rachas_loss.index.max() if not rachas_loss.empty else 0) + 1)
        win_counts = [rachas_win.get(i, 0) for i in x]
        loss_counts = [rachas_loss.get(i, 0) for i in x]
        
        axes[0, 0].bar([i-0.2 for i in x], win_counts, width=0.4, label='Ganadoras', color='green', alpha=0.7)
        axes[0, 0].bar([i+0.2 for i in x], loss_counts, width=0.4, label='Perdedoras', color='red', alpha=0.7)
        axes[0, 0].set_title('Frecuencia de Rachas', fontweight='bold')
        axes[0, 0].set_xlabel('Longitud de la racha')
        axes[0, 0].set_ylabel('Frecuencia')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 3.2 Scatter plot: Duración vs Rentabilidad %
        colors = {'TP': 'green', 'SL': 'red', 'TIEMPO': 'orange', 'FIN_DATA': 'gray'}
        for resultado, color in colors.items():
            mask = df_ops['resultado'] == resultado
            if mask.any():
                axes[0, 1].scatter(df_ops.loc[mask, 'duracion_horas'], df_ops.loc[mask, 'porcentaje_neto'], 
                                  c=color, label=resultado, alpha=0.6, s=50)
        axes[0, 1].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        axes[0, 1].set_title('Duración vs Rentabilidad %', fontweight='bold')
        axes[0, 1].set_xlabel('Duración (horas)')
        axes[0, 1].set_ylabel('Rentabilidad (%)')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3.3 Win Rate acumulado
        df_ops['win_rate_acum'] = (df_ops['porcentaje_neto'] > 0).expanding().mean() * 100
        axes[0, 2].plot(df_ops['fecha_entrada'], df_ops['win_rate_acum'], color='purple', linewidth=2)
        axes[0, 2].axhline(y=50, color='red', linestyle='--', alpha=0.7)
        axes[0, 2].set_title('Win Rate Acumulado', fontweight='bold')
        axes[0, 2].set_ylabel('Win Rate (%)')
        axes[0, 2].set_xlabel('Fecha')
        axes[0, 2].grid(True, alpha=0.3)
        
        # 3.4 Boxplot de rentabilidad % por tipo de operación
        df_ops.boxplot(column='porcentaje_neto', by='tipo', ax=axes[1, 0])
        axes[1, 0].set_title('Rentabilidad % por Tipo', fontweight='bold')
        axes[1, 0].set_ylabel('Rentabilidad (%)')
        axes[1, 0].set_xlabel('Tipo')
        axes[1, 0].grid(True, alpha=0.3)
        
        # 3.5 Evolución del capital % por operación
        axes[1, 1].plot(range(len(df_equity)), df_equity['equity'], color='blue', linewidth=2, marker='o', markersize=2)
        axes[1, 1].set_title('Evolución del Capital % por Operación', fontweight='bold')
        axes[1, 1].set_xlabel('Número de Operación')
        axes[1, 1].set_ylabel('Capital (%)')
        axes[1, 1].grid(True, alpha=0.3)
        
        # 3.6 Distribución de rentabilidad % por resultado
        pnl_por_resultado = df_ops.groupby('resultado')['porcentaje_neto'].sum()
        colors_bar = [colors.get(r, 'blue') for r in pnl_por_resultado.index]
        axes[1, 2].bar(pnl_por_resultado.index, pnl_por_resultado.values, color=colors_bar)
        axes[1, 2].set_title('Rentabilidad Total % por Resultado', fontweight='bold')
        axes[1, 2].set_ylabel('Rentabilidad Total (%)')
        axes[1, 2].set_xlabel('Resultado')
        axes[1, 2].grid(True, alpha=0.3)
        
        plt.suptitle('ANÁLISIS ESTADÍSTICO - PARTE 2 (MÉTRICAS %)', fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()
        plt.savefig(f'{GRAPH_FOLDER}/3_analisis_estadistico_parte2_porcentual.png', dpi=150, bbox_inches='tight')
        plt.close(fig3)
        
        # 4. Gráfico específico para cierres por tiempo
        df_tiempo = df_ops[df_ops['resultado'] == 'TIEMPO']
        if not df_tiempo.empty:
            fig4, axes = plt.subplots(1, 3, figsize=(18, 6))
            
            # 4.1 Rentabilidad de cierres por tiempo
            axes[0].bar(range(len(df_tiempo)), df_tiempo['porcentaje_neto'].values, 
                       color=['green' if x > 0 else 'red' for x in df_tiempo['porcentaje_neto'].values])
            axes[0].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            axes[0].set_title('Rentabilidad % - Cierres por Tiempo', fontweight='bold')
            axes[0].set_xlabel('Operación')
            axes[0].set_ylabel('Rentabilidad (%)')
            axes[0].grid(True, alpha=0.3)
            
            # 4.2 Distribución de duración de cierres por tiempo
            axes[1].hist(df_tiempo['duracion_horas'], bins=15, color='orange', edgecolor='black', alpha=0.7)
            axes[1].axvline(x=self.max_duracion_horas, color='red', linestyle='--', 
                          linewidth=2, label=f'Límite: {self.max_duracion_horas}h')
            axes[1].set_title('Duración de Cierres por Tiempo', fontweight='bold')
            axes[1].set_xlabel('Horas')
            axes[1].set_ylabel('Frecuencia')
            axes[1].legend()
            axes[1].grid(True, alpha=0.3)
            
            # 4.3 Win rate de cierres por tiempo
            labels = ['Ganadoras', 'Perdedoras']
            values = [len(df_tiempo[df_tiempo['porcentaje'] > 0]), len(df_tiempo[df_tiempo['porcentaje'] <= 0])]
            colors_pie = ['green', 'red']
            axes[2].pie(values, labels=labels, autopct='%1.1f%%', colors=colors_pie, startangle=90)
            axes[2].set_title('Win Rate - Cierres por Tiempo', fontweight='bold')
            
            plt.suptitle('ANÁLISIS DE CIERRES POR TIEMPO (MÉTRICAS %)', fontsize=16, fontweight='bold', y=1.05)
            plt.tight_layout()
            plt.savefig(f'{GRAPH_FOLDER}/4_cierres_por_tiempo_porcentual.png', dpi=150, bbox_inches='tight')
            plt.close(fig4)
        
        print(f"✅ Gráficos guardados en '{GRAPH_FOLDER}/'")
        
        # Mostrar los gráficos en pantalla
        plt.show()

# Configuración principal
def main():
    # PARÁMETROS CONFIGURABLES
    config = {
        'csv_file': 'EURUSD_1H.csv',           # Archivo CSV con datos
        'max_operaciones_simultaneas': 2,       # Máximo operaciones abiertas
        'max_duracion_horas': 2,                 # Duración máxima por operación
        'rr_ratio': 2.0,                          # Ratio Risk/Reward (1:2)
        'capital_inicial': 10000,                  # Capital inicial
        'comision': 0.0001,                         # Comisión por operación (0.01%)
        'riesgo_por_operacion': 0.01                 # Riesgo por operacion. 
    }
    
    try:
        # Crear instancia del backtest
        backtest = EstrategiaBacktest(**config)
        
        # Ejecutar backtest
        metricas = backtest.ejecutar_backtest()
        
        # Mostrar resultados
        backtest.mostrar_resultados(metricas)
        
        # Exportar operaciones a CSV
        if backtest.operaciones:
            df_ops = pd.DataFrame(backtest.operaciones)
            df_ops.to_csv('operaciones_realizadas_porcentual.csv', index=False)
            print(f"\n✅ Operaciones exportadas a 'operaciones_realizadas_porcentual.csv'")
        
    except Exception as e:
        print(f"❌ Error durante la ejecución: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()    

'''
============================================================
📊 RESULTADOS DEL BACKTEST (MÉTRICAS PORCENTUALES)
============================================================

📈 ESTADÍSTICAS GENERALES:
  • Total operaciones: 26047
  • Operaciones ganadoras: 21018
  • Operaciones perdedoras: 5029
  • Win Rate: 80.69%
  • Longs/Shorts: 13074/12973
  • Expectancy: 0.739% por operación

🎯 RESULTADO POR TIPO DE CIERRE:
  • Take Profit (TP): 13101 (50.3%)
  • Stop Loss (SL): 2614 (10.0%)
  • Cierre por tiempo: 10331 (39.7%)
  • Cierre fin datos: 1 (0.0%)

⏰ ESTADÍSTICAS DE CIERRES POR TIEMPO:
  • Operaciones cerradas por tiempo: 10331
  • Ganadoras por tiempo: 7916 (76.6%)
  • Perdedoras por tiempo: 2415
  • Rentabilidad total cierres tiempo: 5234.88%
  • Rentabilidad promedio cierre tiempo: 0.51%

📊 RACHAS:
  • Máxima racha ganadora: 42 operaciones
  • Máxima racha perdedora: 5 operaciones

💰 RENDIMIENTO PORCENTUAL:
  • Capital inicial: 100%
  • Capital final: 28436.21%
  • Rentabilidad Total: +28336.21%
  • Rentabilidad Promedio por operación: +1.09%

📈 RATIOS DE RIESGO:
  • Profit Factor: 8.78
  • Sharpe Ratio: 75.43
  • Max Drawdown: -1.22%

⏱️  DURACIÓN OPERACIONES:
  • Duración promedio: 2.27 horas
  • Duración mediana: 2.00 horas

📊 ESTADÍSTICAS RENTABILIDAD %:
  • Media: +1.09%
  • Mediana: +1.86%
  • Desviación std: 1.12%
  • Mínimo: -17.60%
  • Máximo: +21.04%
  • Q1 (25%): +0.25%
  • Q3 (75%): +1.99%

💰 RENTABILIDAD % POR TIPO DE CIERRE:
          porcentaje_neto                   
                      sum  mean  count   std
resultado                                   
FIN_DATA             0.88  0.88      1   NaN
SL               -2640.14 -1.01   2614  0.00
TIEMPO            5234.88  0.51  10331  0.84
TP               25740.59  1.96  13101  0.16

📅 MÉTRICAS MENSUALES (%):
         Rentabilidad_Mensual_%  Operaciones  Win_Rate_%
mes                                                     
2015-01                  222.83          209       78.95
2015-02                  195.15          167       80.84
2015-03                  248.45          218       82.57
2015-04                  241.54          206       80.58
2015-05                  216.67          169       85.21
...                         ...          ...         ...
2025-10                  206.45          208       75.96
2025-11                  180.88          190       74.21
2025-12                  197.79          206       76.70
2026-01                  225.70          200       79.50
2026-02                   89.89           93       72.04

[134 rows x 3 columns]

💾 Guardando gráficos en la carpeta 'graficos_backtest_porcentual/'...
✅ Gráficos guardados en 'graficos_backtest_porcentual/'

✅ Operaciones exportadas a 'operaciones_realizadas_porcentual.csv'
(env) khr@khr:~/Desktop/backtesting$ 

'''