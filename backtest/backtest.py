#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
from datetime import datetime, time
import warnings
warnings.filterwarnings('ignore')

class BacktestEURUSD:
    def __init__(self, csv_path, capital_inicial=10000, comision=0.0001, slippage=0.0001):
        self.csv_path = csv_path
        self.capital_inicial = capital_inicial
        self.comision = comision
        self.slippage = slippage
        self.datos = None
        self.trades = None
        self.resultados = None
        self.metricas = {}

    def cargar_datos(self):
        print("📊 Cargando datos...")
        try:
            self.datos = pd.read_csv(self.csv_path)
            col_tiempo = [col for col in self.datos.columns if 'time' in col.lower() or 'date' in col.lower()][0]
            self.datos['datetime'] = pd.to_datetime(self.datos[col_tiempo])
            self.datos.set_index('datetime', inplace=True)

            if self.datos.index.tz is None:
                self.datos.index = self.datos.index.tz_localize('UTC')
            else:
                self.datos.index = self.datos.index.tz_convert('UTC')

            self.datos.index = self.datos.index.tz_convert('America/New_York')

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

            required_cols = ['open', 'high', 'low', 'close']
            for col in required_cols:
                if col not in self.datos.columns:
                    raise ValueError(f"Columna '{col}' no encontrada en el CSV")

            print(f"✅ Datos cargados: {len(self.datos)} velas de 4H")
            print(f"Período: {self.datos.index[0]} - {self.datos.index[-1]}")
            print("\nPrimeras 35 filas del dataset:\n")
            print(self.datos.head(35))
            print("\nContinuando con el backtest...\n")

            return True
        except Exception as e:
            print(f"❌ Error cargando datos: {e}")
            return False

    def identificar_velas_5am(self):
        self.datos['hora_ny'] = self.datos.index.hour
        self.datos['es_5am'] = self.datos['hora_ny'] == 5
        return self.datos['es_5am'].sum()

    def ejecutar_backtest(self):
        print("🔄 Ejecutando backtest...")
        if self.datos is None:
            if not self.cargar_datos():
                return False

        num_velas_5am = self.identificar_velas_5am()
        print(f"Velas de 5AM encontradas: {num_velas_5am}")

        trades = []
        capital = self.capital_inicial

        for i in range(1, len(self.datos)):
            if not self.datos.iloc[i]['es_5am']:
                continue

            vela_actual = self.datos.iloc[i]
            vela_anterior = self.datos.iloc[i-1]

            es_bajista_anterior = vela_anterior['close'] < vela_anterior['open']

            if es_bajista_anterior:
                direccion = 'BUY'
                precio_entrada = vela_actual['open'] + self.slippage
                take_profit = vela_anterior['high']
            else:
                direccion = 'SELL'
                precio_entrada = vela_actual['open'] - self.slippage
                take_profit = vela_anterior['low']

            distancia_tp = abs(precio_entrada - take_profit)
            stop_loss = precio_entrada - distancia_tp if direccion == 'BUY' else precio_entrada + distancia_tp

            riesgo_pips = abs(precio_entrada - stop_loss)
            riesgo_dinero = capital * 0.01
            tamaño_posicion = riesgo_dinero / riesgo_pips if riesgo_pips > 0 else 0

            resultado = self.simular_operacion(i, direccion, precio_entrada, stop_loss, take_profit, tamaño_posicion, vela_actual)

            if resultado:
                capital += resultado['pnl']
                trades.append(resultado)

        self.trades = pd.DataFrame(trades)
        self.calcular_metricas()
        return True

    def simular_operacion(self, idx, direccion, entrada, sl, tp, tamaño, vela_entrada):
        for j in range(idx, len(self.datos)):
            vela = self.datos.iloc[j]

            if direccion == 'BUY':
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
            else:
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
        capital_curve = self.capital_inicial + self.trades['pnl'].cumsum()
        running_max = capital_curve.cummax()
        drawdown = (capital_curve - running_max) / running_max * 100
        return drawdown.min()

    def mostrar_metricas(self):
        print("\n" + "="*80)
        print("RESULTADOS DEL BACKTEST - EURUSD 4H (5AM NY)")
        print("="*80)
        for k, v in self.metricas.items():
            print(f"{k}: {v}")
        print("="*80)

    def exportar_resultados(self, filename='resultados_backtest.csv'):
        if self.trades is not None and len(self.trades) > 0:
            self.trades.to_csv(filename, index=False)
            print(f"Trades exportados a: {filename}")

def main():
    CONFIG = {
        'csv_path': 'dataset.csv',
        'capital_inicial': 10000,
        'comision': 0.0001,
        'slippage': 0.0001,
        'exportar_resultados': True
    }

    print("Iniciando Backtesting Profesional - EURUSD 4H")
    print("="*80)

    backtest = BacktestEURUSD(
        csv_path=CONFIG['csv_path'],
        capital_inicial=CONFIG['capital_inicial'],
        comision=CONFIG['comision'],
        slippage=CONFIG['slippage']
    )

    if backtest.ejecutar_backtest():
        backtest.mostrar_metricas()
        if CONFIG['exportar_resultados']:
            backtest.exportar_resultados()
        print("Backtest completado exitosamente")
    else:
        print("Error en la ejecución del backtest")

if __name__ == "__main__":
    main()
