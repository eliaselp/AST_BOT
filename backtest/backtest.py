#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtesting profesional para estrategia de trading en EURUSD - Temporalidad 4H
Estrategia: Entrada a las 5AM, dirección contraria a vela anterior, TP en extremos, SL 1:1
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
import warnings
warnings.filterwarnings('ignore')

class BacktestEURUSD:
    def __init__(self, csv_path, capital_inicial=10000, comision=0.0001, slippage=0.0001):
        """
        Inicializa el backtesting
        
        Args:
            csv_path: Ruta del archivo CSV con datos OHLCV
            capital_inicial: Capital inicial de la cuenta
            comision: Comisión por operación (0.01% = 0.0001)
            slippage: Deslizamiento estimado por operación
        """
        self.csv_path = csv_path
        self.capital_inicial = capital_inicial
        self.comision = comision
        self.slippage = slippage
        
        # DataFrames
        self.datos = None
        self.trades = None
        self.resultados = None
        
        # Métricas
        self.metricas = {}
        
    def cargar_datos(self):
        """Carga y prepara los datos del CSV"""
        print("📊 Cargando datos...")
        
        try:
            self.datos = pd.read_csv(self.csv_path)
            
            # Convertir columna de tiempo a datetime
            col_tiempo = [col for col in self.datos.columns if 'time' in col.lower() or 'date' in col.lower()][0]
            self.datos['datetime'] = pd.to_datetime(self.datos[col_tiempo])
            self.datos.set_index('datetime', inplace=True)
            
            # Renombrar columnas OHLCV si es necesario
            column_mapping = {}
            for col in self.datos.columns:
                col_lower = col.lower()
                if 'open' in col_lower:
                    column_mapping[col] = 'open'
                elif 'high' in col_lower:
                    column_mapping[col] = 'high'
                elif 'low' in col_lower:
                    column_mapping[col] = 'low'
                elif 'close' in col_lower:
                    column_mapping[col] = 'close'
                elif 'volume' in col_lower:
                    column_mapping[col] = 'volume'
            
            self.datos.rename(columns=column_mapping, inplace=True)
            
            # Asegurar columnas necesarias
            required_cols = ['open', 'high', 'low', 'close']
            for col in required_cols:
                if col not in self.datos.columns:
                    raise ValueError(f"Columna '{col}' no encontrada en el CSV")
            
            print(f"✅ Datos cargados: {len(self.datos)} velas de 4H")
            print(f"   Período: {self.datos.index[0]} - {self.datos.index[-1]}\n")
            
            return True
            
        except Exception as e:
            print(f"❌ Error cargando datos: {e}")
            return False
    
    def identificar_velas_5am(self):
        """Identifica las velas que comienzan a las 5:00 AM"""
        self.datos['es_5am'] = self.datos.index.hour == 5
        self.datos['hora'] = self.datos.index.hour
        return self.datos['es_5am'].sum()
    
    def ejecutar_backtest(self):
        """Ejecuta el backtesting completo"""
        print("🔄 Ejecutando backtest...")
        
        if self.datos is None:
            if not self.cargar_datos():
                return False
        
        # Identificar velas de 5am
        num_velas_5am = self.identificar_velas_5am()
        print(f"   Velas de 5AM encontradas: {num_velas_5am}")
        
        trades = []
        capital = self.capital_inicial
        
        for i in range(1, len(self.datos)):
            if not self.datos.iloc[i]['es_5am']:
                continue
                
            # Vela actual (5am) y vela anterior
            vela_actual = self.datos.iloc[i]
            vela_anterior = self.datos.iloc[i-1]
            
            # 2. Determinar dirección contraria a vela anterior
            es_bajista_anterior = vela_anterior['close'] < vela_anterior['open']
            
            # 3. Configurar entrada y TP
            if es_bajista_anterior:
                direccion = 'BUY'  # Contrario a bajista = compra
                precio_entrada = vela_actual['open'] + self.slippage
                take_profit = vela_anterior['high']
            else:
                direccion = 'SELL'  # Contrario a alcista = venta
                precio_entrada = vela_actual['open'] - self.slippage
                take_profit = vela_anterior['low']
            
            # 4. Calcular SL (1:1)
            distancia_tp = abs(precio_entrada - take_profit)
            stop_loss = precio_entrada - distancia_tp if direccion == 'BUY' else precio_entrada + distancia_tp
            
            # Calcular tamaño de posición (1% riesgo por operación)
            riesgo_pips = abs(precio_entrada - stop_loss)
            riesgo_dinero = capital * 0.01  # 1% de riesgo
            tamaño_posicion = riesgo_dinero / riesgo_pips if riesgo_pips > 0 else 0
            
            # Simular resultado de la operación
            resultado = self.simular_operacion(i, direccion, precio_entrada, stop_loss, take_profit, 
                                              tamaño_posicion, vela_actual)
            
            if resultado:
                capital += resultado['pnl']
                trades.append(resultado)
        
        self.trades = pd.DataFrame(trades)
        self.calcular_metricas()
        return True
    
    def simular_operacion(self, idx, direccion, entrada, sl, tp, tamaño, vela_entrada):
        """Simula una operación individual"""
        # Buscar desde la vela actual hasta el final
        for j in range(idx, len(self.datos)):
            vela = self.datos.iloc[j]
            
            if direccion == 'BUY':
                # Verificar si se alcanza TP o SL
                if vela['low'] <= sl:
                    precio_salida = sl + self.slippage
                    pnl = (precio_salida - entrada) * tamaño
                    pnl -= (entrada + precio_salida) * tamaño * self.comision
                    hora_salida = vela.name
                    razon_salida = 'SL'
                    break
                elif vela['high'] >= tp:
                    precio_salida = tp - self.slippage
                    pnl = (precio_salida - entrada) * tamaño
                    pnl -= (entrada + precio_salida) * tamaño * self.comision
                    hora_salida = vela.name
                    razon_salida = 'TP'
                    break
                
            else:  # SELL
                if vela['high'] >= sl:
                    precio_salida = sl - self.slippage
                    pnl = (entrada - precio_salida) * tamaño
                    pnl -= (entrada + precio_salida) * tamaño * self.comision
                    hora_salida = vela.name
                    razon_salida = 'SL'
                    break
                elif vela['low'] <= tp:
                    precio_salida = tp + self.slippage
                    pnl = (entrada - precio_salida) * tamaño
                    pnl -= (entrada + precio_salida) * tamaño * self.comision
                    hora_salida = vela.name
                    razon_salida = 'TP'
                    break

        else:
            # Operación no cerrada
            return None
        
        return {
            'fecha_entrada': vela_entrada.name,
            'fecha_salida': hora_salida,
            'direccion': direccion,
            'precio_entrada': entrada,
            'precio_salida': precio_salida,
            'stop_loss': sl,
            'take_profit': tp,
            'tamaño': tamaño,
            'pnl': pnl,
            'pnl_pips': (precio_salida - entrada) * 10000 if direccion == 'BUY' else (entrada - precio_salida) * 10000,
            'razon_salida': razon_salida,
            'velas_hold': j - idx
        }
    
    def calcular_metricas(self):
        """Calcula todas las métricas del backtest"""
        if self.trades is None or len(self.trades) == 0:
            print("❌ No hay trades para calcular métricas")
            return
        
        trades_ganadores = self.trades[self.trades['pnl'] > 0]
        trades_perdedores = self.trades[self.trades['pnl'] < 0]
        
        self.metricas = {
            'Total Trades': len(self.trades),
            'Trades Ganadores': len(trades_ganadores),
            'Trades Perdedores': len(trades_perdedores),
            '% Win Rate': len(trades_ganadores) / len(self.trades) * 100,
            
            'Capital Inicial': self.capital_inicial,
            'Capital Final': self.capital_inicial + self.trades['pnl'].sum(),
            'Net Profit': self.trades['pnl'].sum(),
            'Net Profit %': (self.trades['pnl'].sum() / self.capital_inicial) * 100,
            
            'Total Pips': self.trades['pnl_pips'].sum(),
            'Avg Pips por Trade': self.trades['pnl_pips'].mean(),
            'Avg Pips Ganador': trades_ganadores['pnl_pips'].mean() if len(trades_ganadores) > 0 else 0,
            'Avg Pips Perdedor': trades_perdedores['pnl_pips'].mean() if len(trades_perdedores) > 0 else 0,
            
            'Avg Ganancia': trades_ganadores['pnl'].mean() if len(trades_ganadores) > 0 else 0,
            'Avg Pérdida': trades_perdedores['pnl'].mean() if len(trades_perdedores) > 0 else 0,
            'Ratio Ganancia/Pérdida': abs(trades_ganadores['pnl'].mean() / trades_perdedores['pnl'].mean()) if len(trades_perdedores) > 0 and trades_perdedores['pnl'].mean() != 0 else 0,
            
            'Mayor Ganancia': self.trades['pnl'].max(),
            'Mayor Pérdida': self.trades['pnl'].min(),
            'Desviación Estándar': self.trades['pnl'].std(),
            
            'Sharpe Ratio': self.trades['pnl'].mean() / self.trades['pnl'].std() if self.trades['pnl'].std() != 0 else 0,
            
            'Total Comisiones': (self.trades['precio_entrada'] + self.trades['precio_salida']).sum() * self.trades['tamaño'].sum() * self.comision,
            
            'Trades TP': len(self.trades[self.trades['razon_salida'] == 'TP']),
            'Trades SL': len(self.trades[self.trades['razon_salida'] == 'SL']),
            '% TP': len(self.trades[self.trades['razon_salida'] == 'TP']) / len(self.trades) * 100,
            'Avg Velas por Trade': self.trades['velas_hold'].mean(),
            
            'Buy Trades': len(self.trades[self.trades['direccion'] == 'BUY']),
            'Sell Trades': len(self.trades[self.trades['direccion'] == 'SELL']),
            'Buy Win Rate': len(self.trades[(self.trades['direccion'] == 'BUY') & (self.trades['pnl'] > 0)]) / len(self.trades[self.trades['direccion'] == 'BUY']) * 100 if len(self.trades[self.trades['direccion'] == 'BUY']) > 0 else 0,
            'Sell Win Rate': len(self.trades[(self.trades['direccion'] == 'SELL') & (self.trades['pnl'] > 0)]) / len(self.trades[self.trades['direccion'] == 'SELL']) * 100 if len(self.trades[self.trades['direccion'] == 'SELL']) > 0 else 0,
            
            'Drawdown Máximo': self.calcular_max_drawdown(),
            'Factor de Beneficio': abs(self.trades[self.trades['pnl'] > 0]['pnl'].sum() / self.trades[self.trades['pnl'] < 0]['pnl'].sum()) if len(self.trades[self.trades['pnl'] < 0]) > 0 else 0,
        }
    
    def calcular_max_drawdown(self):
        """Calcula el máximo drawdown"""
        capital_curve = self.capital_inicial + self.trades['pnl'].cumsum()
        running_max = capital_curve.cummax()
        drawdown = (capital_curve - running_max) / running_max * 100
        return drawdown.min()
    
    def mostrar_metricas(self):
        """Muestra todas las métricas en consola"""
        print("\n" + "="*80)
        print("📈 RESULTADOS DEL BACKTEST - ESTRATEGIA EURUSD 4H (5AM)")
        print("="*80)
        
        print("\n📊 ESTADÍSTICAS GENERALES:")
        print(f"   Total Trades: {self.metricas['Total Trades']:.0f}")
        print(f"   Trades Ganadores: {self.metricas['Trades Ganadores']:.0f}")
        print(f"   Trades Perdedores: {self.metricas['Trades Perdedores']:.0f}")
        print(f"   Win Rate: {self.metricas['% Win Rate']:.2f}%")
        
        print("\n💰 RENDIMIENTO FINANCIERO:")
        print(f"   Capital Inicial: ${self.metricas['Capital Inicial']:,.2f}")
        print(f"   Capital Final: ${self.metricas['Capital Final']:,.2f}")
        print(f"   Beneficio Neto: ${self.metricas['Net Profit']:,.2f}")
        print(f"   Rentabilidad: {self.metricas['Net Profit %']:.2f}%")
        
        print("\n🎯 ESTADÍSTICAS EN PIPS:")
        print(f"   Total Pips: {self.metricas['Total Pips']:.1f}")
        print(f"   Promedio Pips/Trade: {self.metricas['Avg Pips por Trade']:.1f}")
        print(f"   Promedio Pips Ganador: {self.metricas['Avg Pips Ganador']:.1f}")
        print(f"   Promedio Pips Perdedor: {self.metricas['Avg Pips Perdedor']:.1f}")
        
        print("\n📉 GESTIÓN DE RIESGO:")
        print(f"   Drawdown Máximo: {self.metricas['Drawdown Máximo']:.2f}%")
        print(f"   Factor de Beneficio: {self.metricas['Factor de Beneficio']:.2f}")
        print(f"   Ratio Sharpe: {self.metricas['Sharpe Ratio']:.2f}")
        print(f"   Ratio Ganancia/Pérdida: {self.metricas['Ratio Ganancia/Pérdida']:.2f}")
        
        print("\n💹 DETALLES DE OPERACIONES:")
        print(f"   Mayor Ganancia: ${self.metricas['Mayor Ganancia']:,.2f}")
        print(f"   Mayor Pérdida: ${self.metricas['Mayor Pérdida']:,.2f}")
        print(f"   Desviación Estándar: ${self.metricas['Desviación Estándar']:,.2f}")
        
        print("\n⏱️  TIEMPO Y EJECUCIÓN:")
        print(f"   Trades TP: {self.metricas['Trades TP']:.0f} ({self.metricas['% TP']:.1f}%)")
        print(f"   Trades SL: {self.metricas['Trades SL']:.0f}")
        print(f"   Velas Promedio por Trade: {self.metricas['Avg Velas por Trade']:.1f}")
        
        print("\n🔄 DIRECCIÓN DE TRADES:")
        print(f"   Trades Buy: {self.metricas['Buy Trades']:.0f} (Win Rate: {self.metricas['Buy Win Rate']:.1f}%)")
        print(f"   Trades Sell: {self.metricas['Sell Trades']:.0f} (Win Rate: {self.metricas['Sell Win Rate']:.1f}%)")
        
        print("\n" + "="*80)
    
    def exportar_resultados(self, filename='resultados_backtest.csv'):
        """Exporta los trades a CSV"""
        if self.trades is not None and len(self.trades) > 0:
            self.trades.to_csv(filename, index=False)
            print(f"\n💾 Trades exportados a: {filename}")

def main():
    # CONFIGURACIÓN - Totalmente configurable
    CONFIG = {
        'csv_path': 'dataset.csv',  # Cambiar por la ruta correcta
        'capital_inicial': 10000,
        'comision': 0.0001,  # 0.01%
        'slippage': 0.0001,  # 1 pip
        'exportar_resultados': True
    }
    
    print("🚀 Iniciando Backtesting Profesional - EURUSD 4H")
    print("="*80)
    
    # Crear instancia del backtest
    backtest = BacktestEURUSD(
        csv_path=CONFIG['csv_path'],
        capital_inicial=CONFIG['capital_inicial'],
        comision=CONFIG['comision'],
        slippage=CONFIG['slippage']
    )
    
    # Ejecutar backtest
    if backtest.ejecutar_backtest():
        # Mostrar métricas
        backtest.mostrar_metricas()
        
        # Exportar resultados si está configurado
        if CONFIG['exportar_resultados']:
            backtest.exportar_resultados()
        
        print("\n✨ Backtest completado exitosamente!")
    else:
        print("\n❌ Error en la ejecución del backtest")

if __name__ == "__main__":
    main()