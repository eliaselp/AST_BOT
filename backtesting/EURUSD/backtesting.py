#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BACKTESTING ESTRATEGIA "95K"
Sistema de Alta Probabilidad basado en OHLCV
Versión: Datos separados H4 y M15 con columna datetime
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class Config:
    DATASET_H4_PATH = 'EURUSD_H4.csv'
    DATASET_M15_PATH = 'EURUSD_M15.csv'
    COL_OPEN = 'open'
    COL_HIGH = 'high'
    COL_LOW = 'low'
    COL_CLOSE = 'close'
    COL_VOLUME = 'volume'
    DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
    SL_BUFFER = 8
    
    RISK_PERCENT = 0.4
    RR_RATIO = 0.5
    
    VOLUME_MULTIPLIER = 0
    HORAS_EVITAR = [1, 2, 3, 7, 10, 11, 15, 16, 19, 20, 21, 23]
    
    #MIN_BODY_RATIO = 0.60
    #MAX_WICK_RATIO = 0.40
    MIN_BODY_RATIO = 0
    MAX_WICK_RATIO = 1
    
    PLOT_RESULTS = True
    SAVE_REPORT = True
    REPORT_FILENAME = 'backtest_95k_results.html'
    EXPORT_TRADES_CSV = True
    SYMBOL = 'EURUSD'
    PIP_VALUE = 0.0001
    DECIMALS = 5
    CHECK_OVERLAP = True
    TIMEZONE = 'UTC'

class Backtest95K:
    def __init__(self, config):
        self.config = config
        self.data_h4 = None
        self.data_m15 = None
        self.trades = []
        self.metrics = {}
        self.monthly_metrics = None
        self.max_simultaneous_trades = 0
        self.current_simultaneous_trades = 0
        
    def load_csv_file(self, filepath):
        try:
            print(f"Cargando {filepath}...")
            df = pd.read_csv(filepath)
            
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'], format=self.config.DATETIME_FORMAT)
            else:
                print(f"❌ Error: No se encontró columna 'datetime' en {filepath}")
                return None
            
            df.set_index('datetime', inplace=True)
            df.sort_index(inplace=True)
            
            if df.index.duplicated().any():
                print(f"⚠️  Advertencia: {df.index.duplicated().sum()} registros duplicados en {filepath}")
                df = df[~df.index.duplicated(keep='first')]
            
            column_mapping = {
                self.config.COL_OPEN: 'open',
                self.config.COL_HIGH: 'high',
                self.config.COL_LOW: 'low',
                self.config.COL_CLOSE: 'close',
                self.config.COL_VOLUME: 'volume'
            }
            
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df.rename(columns={old_col: new_col}, inplace=True)
            
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                print(f"❌ Error: Columnas faltantes en {filepath}: {missing_cols}")
                print(f"   Columnas disponibles: {list(df.columns)}")
                return None
            
            print(f"   ✅ {len(df)} registros desde {df.index[0]} hasta {df.index[-1]}")
            return df
            
        except Exception as e:
            print(f"❌ Error cargando {filepath}: {e}")
            return None
    
    def load_data(self):
        print("\n📂 CARGANDO DATASETS")
        print("="*50)
        
        self.data_h4 = self.load_csv_file(self.config.DATASET_H4_PATH)
        if self.data_h4 is None:
            return False
        
        self.data_m15 = self.load_csv_file(self.config.DATASET_M15_PATH)
        if self.data_m15 is None:
            return False
        
        if self.config.CHECK_OVERLAP:
            h4_start, h4_end = self.data_h4.index[0], self.data_h4.index[-1]
            m15_start, m15_end = self.data_m15.index[0], self.data_m15.index[-1]
            
            print("\n📅 VERIFICACIÓN DE FECHAS:")
            print(f"   H4:  {h4_start} → {h4_end}")
            print(f"   M15: {m15_start} → {m15_end}")
            
            common_start = max(h4_start, m15_start)
            common_end = min(h4_end, m15_end)
            
            if common_start >= common_end:
                print("❌ Error: Los datasets no tienen período común")
                return False
            
            print(f"   ✅ Período común: {common_start} → {common_end}")
            
            self.data_h4 = self.data_h4[common_start:common_end]
            self.data_m15 = self.data_m15[common_start:common_end]
            
            print(f"   H4 después del recorte: {len(self.data_h4)} registros")
            print(f"   M15 después del recorte: {len(self.data_m15)} registros")
        
        return True
    
    def align_trend_to_m15(self):
        print("\n🔄 ALINEANDO TENDENCIAS H4 → M15")
        
        self.data_m15['h4_trend_alcista'] = False
        self.data_m15['h4_trend_bajista'] = False
        self.data_m15['h4_open'] = np.nan
        self.data_m15['h4_close'] = np.nan
        
        matched = 0
        unmatched = 0
        
        for idx in self.data_m15.index:
            h4_mask = self.data_h4.index <= idx
            if h4_mask.any():
                last_h4_idx = self.data_h4.index[h4_mask][-1]
                h4_row = self.data_h4.loc[last_h4_idx]
                
                h4_alcista = h4_row['close'] > h4_row['open']
                h4_bajista = h4_row['close'] < h4_row['open']
                
                self.data_m15.loc[idx, 'h4_trend_alcista'] = h4_alcista
                self.data_m15.loc[idx, 'h4_trend_bajista'] = h4_bajista
                self.data_m15.loc[idx, 'h4_open'] = h4_row['open']
                self.data_m15.loc[idx, 'h4_close'] = h4_row['close']
                matched += 1
            else:
                unmatched += 1
        
        print(f"   ✅ Velas M15 con tendencia asignada: {matched}")
        if unmatched > 0:
            print(f"   ⚠️  Velas sin tendencia (antes del primer H4): {unmatched}")
    
    def check_signal(self, pos, row):
        try:
            if pos == 0:
                return None
            
            prev_row = self.data_m15.iloc[pos - 1]
            
            en_horario = False
            if self.config.HORAS_EVITAR:
                hora_actual = row.name.hour
                if hora_actual not in self.config.HORAS_EVITAR:
                    en_horario = True
            else:
                en_horario =True
             
            if en_horario:    
                rango = row['high'] - row['low']
                if rango <= 0 or pd.isna(rango):
                    return None
                
                cuerpo = abs(row['close'] - row['open'])
                body_ratio = cuerpo / rango
                
                if (row['close'] > prev_row['high'] and
                    body_ratio >= self.config.MIN_BODY_RATIO and
                    (row['high'] - row['close']) / rango <= self.config.MAX_WICK_RATIO and
                    row['volume'] > prev_row['volume'] * self.config.VOLUME_MULTIPLIER and
                    row['h4_trend_alcista']):
                    return 'LONG'
                
                elif (row['close'] < prev_row['low'] and
                    body_ratio >= self.config.MIN_BODY_RATIO and
                    (row['close'] - row['low']) / rango <= self.config.MAX_WICK_RATIO and
                    row['volume'] > prev_row['volume'] * self.config.VOLUME_MULTIPLIER and
                    row['h4_trend_bajista']):
                    return 'SHORT'
            return None
            
        except Exception:
            return None
    
    def calculate_entry_price(self, row, signal_type):
        tick = self.config.PIP_VALUE / 10
        if signal_type == 'LONG':
            return row['close'] + tick
        else:
            return row['close'] - tick
    
    def calculate_sl(self, row, signal_type):
        buffer = self.config.SL_BUFFER * self.config.PIP_VALUE
        if signal_type == 'LONG':
            return row['low'] - buffer
        else:
            return row['high'] + buffer
    
    def calculate_tp(self, entry_price, sl, signal_type):
        tp_pips = abs(entry_price - sl) * self.config.RR_RATIO
        if signal_type == 'LONG':
            return entry_price + tp_pips
        else:
            return entry_price - tp_pips
        
    def scan_result(self, start_pos, entry, sl, tp, signal_type):
        max_bars = 100
        
        for j in range(start_pos + 1, min(start_pos + max_bars, len(self.data_m15))):
            bar = self.data_m15.iloc[j]
            
            if signal_type == 'LONG':
                if bar['low'] <= sl:
                    pips = (sl - entry) / self.config.PIP_VALUE
                    return {
                        'result': 'LOSS',
                        'exit_time': bar.name,
                        'exit_price': sl,
                        'pips': pips,
                        'profit_percent': -self.config.RISK_PERCENT
                    }
                elif bar['high'] >= tp:
                    pips = (tp - entry) / self.config.PIP_VALUE
                    return {
                        'result': 'WIN',
                        'exit_time': bar.name,
                        'exit_price': tp,
                        'pips': pips,
                        'profit_percent': self.config.RISK_PERCENT * self.config.RR_RATIO
                    }
            else:
                if bar['high'] >= sl:
                    pips = (entry - sl) / self.config.PIP_VALUE
                    return {
                        'result': 'LOSS',
                        'exit_time': bar.name,
                        'exit_price': sl,
                        'pips': pips,
                        'profit_percent': -self.config.RISK_PERCENT
                    }
                elif bar['low'] <= tp:
                    pips = (entry - tp) / self.config.PIP_VALUE
                    return {
                        'result': 'WIN',
                        'exit_time': bar.name,
                        'exit_price': tp,
                        'pips': pips,
                        'profit_percent': self.config.RISK_PERCENT * self.config.RR_RATIO
                    }
        
        return {
            'result': 'OPEN',
            'exit_time': None,
            'exit_price': None,
            'pips': 0,
            'profit_percent': 0
        }
    
    def run_backtest(self):
        print("\n🎯 EJECUTANDO BACKTEST")
        print("="*50)
        
        self.trades = []
        self.current_simultaneous_trades = 0
        self.max_simultaneous_trades = 0
        
        for i in range(1, len(self.data_m15) - 1):
            row = self.data_m15.iloc[i]
            signal = self.check_signal(i, row)
            
            if signal:
                entry = self.calculate_entry_price(row, signal)
                sl = self.calculate_sl(self.data_m15.iloc[i-1], signal)
                tp = self.calculate_tp(entry, sl, signal)
                
                if signal == 'LONG' and (sl >= entry or tp <= entry):
                    continue
                if signal == 'SHORT' and (sl <= entry or tp >= entry):
                    continue
                
                self.current_simultaneous_trades += 1
                self.max_simultaneous_trades = max(self.max_simultaneous_trades, self.current_simultaneous_trades)
                
                result = self.scan_result(i, entry, sl, tp, signal)
                
                if result['result'] != 'OPEN':
                    self.current_simultaneous_trades -= 1
                    
                    trade = {
                        'entry_time': row.name,
                        'type': signal,
                        'entry_price': entry,
                        'sl': sl,
                        'tp': tp,
                        'result': result['result'],
                        'exit_time': result['exit_time'],
                        'exit_price': result['exit_price'],
                        'pips': result['pips'],
                        'profit_percent': result['profit_percent'],
                        'h4_trend_alcista': row['h4_trend_alcista'],
                        'h4_trend_bajista': row['h4_trend_bajista'],
                        'volume_ratio': row['volume'] / self.data_m15.iloc[i-1]['volume']
                    }
                    self.trades.append(trade)
        
        print(f"   📊 Señales encontradas: {len(self.trades)}")
        print(f"   🔄 Máximo de operaciones simultáneas: {self.max_simultaneous_trades}")
        
        if self.trades:
            wins = sum(1 for t in self.trades if t['result'] == 'WIN')
            losses = sum(1 for t in self.trades if t['result'] == 'LOSS')
            winrate = (wins / len(self.trades) * 100)
            print(f"   ✅ Winrate preliminar: {winrate:.1f}% ({wins}W / {losses}L)")
        
        self.calculate_metrics()
    
    def calculate_metrics(self):
        if not self.trades:
            print("⚠️  No hay trades para calcular métricas")
            return
        
        df_trades = pd.DataFrame(self.trades)
        
        wins = df_trades[df_trades['result'] == 'WIN']
        losses = df_trades[df_trades['result'] == 'LOSS']
        
        total_trades = len(df_trades)
        win_count = len(wins)
        loss_count = len(losses)
        winrate = (win_count / total_trades * 100) if total_trades > 0 else 0
        total_pips = df_trades['pips'].sum()
        avg_pips_win = wins['pips'].mean() if win_count > 0 else 0
        avg_pips_loss = losses['pips'].mean() if loss_count > 0 else 0
        total_profit_percent = df_trades['profit_percent'].sum()
        profit_factor = abs(wins['pips'].sum() / losses['pips'].sum()) if loss_count > 0 and losses['pips'].sum() != 0 else float('inf')
        
        returns = df_trades['profit_percent'].values
        sharpe = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0
        
        max_consecutive_wins = self.calculate_max_consecutive(df_trades['result'] == 'WIN')
        max_consecutive_losses = self.calculate_max_consecutive(df_trades['result'] == 'LOSS')
        
        cumulative = df_trades['profit_percent'].cumsum()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max).min()
        
        if len(df_trades) > 1:
            days_range = (df_trades['entry_time'].max() - df_trades['entry_time'].min()).days + 1
            trades_per_day = len(df_trades) / days_range if days_range > 0 else 0
        else:
            trades_per_day = 0
        
        self.metrics = {
            'total_trades': total_trades,
            'win_count': win_count,
            'loss_count': loss_count,
            'winrate': winrate,
            'total_pips': total_pips,
            'avg_pips_win': avg_pips_win,
            'avg_pips_loss': avg_pips_loss,
            'total_profit_percent': total_profit_percent,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'max_drawdown': drawdown,
            'avg_trade': df_trades['profit_percent'].mean(),
            'trades_per_day': trades_per_day,
            'long_trades': len(df_trades[df_trades['type'] == 'LONG']),
            'short_trades': len(df_trades[df_trades['type'] == 'SHORT']),
            'max_simultaneous_trades': self.max_simultaneous_trades
        }
        
        self.calculate_monthly_metrics(df_trades)
        
        if self.config.EXPORT_TRADES_CSV:
            df_trades.to_csv('trades_detalle.csv', index=False)
            print("   💾 Trades exportados a 'trades_detalle.csv'")
    
    def calculate_max_consecutive(self, condition):
        max_streak = 0
        current_streak = 0
        for value in condition:
            if value:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        return max_streak
    
    def calculate_monthly_metrics(self, df_trades):
        df_trades['month'] = df_trades['entry_time'].dt.to_period('M')
        monthly = df_trades.groupby('month').agg({
            'result': lambda x: (x == 'WIN').sum(),
            'pips': 'sum',
            'profit_percent': 'sum',
            'type': 'count'
        }).rename(columns={
            'result': 'wins',
            'pips': 'total_pips',
            'profit_percent': 'profit_percent',
            'type': 'total_trades'
        })
        monthly['winrate'] = (monthly['wins'] / monthly['total_trades'] * 100)
        monthly['losses'] = monthly['total_trades'] - monthly['wins']
        self.monthly_metrics = monthly
    
    def print_metrics(self):
        print("\n" + "="*60)
        print("📊 RESULTADOS DEL BACKTEST - ESTRATEGIA 95K")
        print("="*60)
        
        if not self.metrics:
            print("No hay métricas para mostrar")
            return
        
        print(f"\n📈 MÉTRICAS GLOBALES:")
        print(f"   {'Total operaciones:':<25} {self.metrics['total_trades']}")
        print(f"   {'Ganadoras / Perdedoras:':<25} {self.metrics['win_count']} / {self.metrics['loss_count']}")
        print(f"   {'Winrate:':<25} {self.metrics['winrate']:.2f}%")
        print(f"   {'Profit Factor:':<25} {self.metrics['profit_factor']:.2f}")
        print(f"   {'Sharpe Ratio:':<25} {self.metrics['sharpe_ratio']:.2f}")
        print(f"   {'Max Operaciones Simultáneas:':<25} {self.metrics['max_simultaneous_trades']}")
        
        print(f"\n💰 RENDIMIENTO:")
        print(f"   {'Pips totales:':<25} {self.metrics['total_pips']:.1f}")
        print(f"   {'Profit % total:':<25} {self.metrics['total_profit_percent']:.2f}%")
        print(f"   {'Operaciones/día:':<25} {self.metrics['trades_per_day']:.2f}")
        
        print(f"\n📉 ESTADÍSTICAS POR OPERACIÓN:")
        print(f"   {'Promedio pips ganador:':<25} {self.metrics['avg_pips_win']:.1f}")
        print(f"   {'Promedio pips perdedor:':<25} {self.metrics['avg_pips_loss']:.1f}")
        
        print(f"\n🔴 RACHAS Y DRAWDOWN:")
        print(f"   {'Máxima racha ganadora:':<25} {self.metrics['max_consecutive_wins']}")
        print(f"   {'Máxima racha perdedora:':<25} {self.metrics['max_consecutive_losses']}")
        print(f"   {'Máximo Drawdown:':<25} {self.metrics['max_drawdown']:.2f}%")
        
        print(f"\n🔄 DISTRIBUCIÓN:")
        print(f"   {'Operaciones LONG:':<25} {self.metrics['long_trades']}")
        print(f"   {'Operaciones SHORT:':<25} {self.metrics['short_trades']}")
    
    def print_monthly_metrics(self):
        if self.monthly_metrics is None or len(self.monthly_metrics) == 0:
            return
        
        print("\n" + "="*60)
        print("📅 RENDIMIENTO MENSUAL")
        print("="*60)
        
        for month, row in self.monthly_metrics.iterrows():
            print(f"\n{month}:")
            print(f"   Operaciones: {int(row['total_trades'])} (W:{int(row['wins'])} L:{int(row['losses'])})")
            print(f"   Winrate: {row['winrate']:.1f}%")
            print(f"   Pips: {row['total_pips']:.1f}")
            print(f"   Profit: {row['profit_percent']:.2f}%")
    
    def plot_results(self):
        if not self.config.PLOT_RESULTS or not self.trades:
            return
        
        df_trades = pd.DataFrame(self.trades)
        plt.style.use('seaborn-v0_8-darkgrid')
        fig = plt.figure(figsize=(18, 14))
        
        ax1 = plt.subplot(3, 3, 1)
        cumulative_pips = df_trades['pips'].cumsum()
        ax1.plot(df_trades['entry_time'], cumulative_pips, color='blue', linewidth=2, label='Curva de Equity')
        ax1.fill_between(df_trades['entry_time'], 0, cumulative_pips, alpha=0.3, color='blue')
        ax1.axhline(y=0, color='black', linewidth=0.5, linestyle='--')
        ax1.set_title('Curva de Equity (Pips Acumulados)', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Fecha')
        ax1.set_ylabel('Pips')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        ax2 = plt.subplot(3, 3, 2)
        cumulative_profit = df_trades['profit_percent'].cumsum()
        ax2.plot(df_trades['entry_time'], cumulative_profit, color='green', linewidth=2, label='Rendimiento %')
        ax2.fill_between(df_trades['entry_time'], 0, cumulative_profit, alpha=0.3, color='green')
        ax2.axhline(y=0, color='black', linewidth=0.5, linestyle='--')
        ax2.set_title('Rendimiento Acumulado (%)', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Fecha')
        ax2.set_ylabel('Rendimiento %')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        ax3 = plt.subplot(3, 3, 3)
        colors = ['green' if r == 'WIN' else 'red' for r in df_trades['result']]
        ax3.bar(range(len(df_trades)), df_trades['pips'], color=colors, alpha=0.7)
        ax3.axhline(y=0, color='black', linewidth=0.5)
        ax3.set_title('Resultados por Operación', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Operación #')
        ax3.set_ylabel('Pips')
        ax3.grid(True, alpha=0.3)
        
        ax4 = plt.subplot(3, 3, 4)
        if self.monthly_metrics is not None:
            months_str = [str(m) for m in self.monthly_metrics.index]
            bars = ax4.bar(months_str, self.monthly_metrics['winrate'], color='green', alpha=0.7)
            ax4.axhline(y=95, color='red', linestyle='--', linewidth=2, label='Objetivo 95%')
            for bar, wr in zip(bars, self.monthly_metrics['winrate']):
                if wr >= 95:
                    bar.set_color('darkgreen')
                else:
                    bar.set_color('orange')
            ax4.set_title('Winrate Mensual', fontsize=12, fontweight='bold')
            ax4.set_xlabel('Mes')
            ax4.set_ylabel('Winrate %')
            ax4.set_ylim(0, 105)
            ax4.legend()
            ax4.grid(True, alpha=0.3)
            plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)
        
        ax5 = plt.subplot(3, 3, 5)
        if self.monthly_metrics is not None:
            months_str = [str(m) for m in self.monthly_metrics.index]
            bars = ax5.bar(months_str, self.monthly_metrics['total_pips'], color='blue', alpha=0.7)
            for bar, pips in zip(bars, self.monthly_metrics['total_pips']):
                if pips >= 0:
                    bar.set_color('blue')
                else:
                    bar.set_color('red')
            ax5.set_title('Pips Mensuales', fontsize=12, fontweight='bold')
            ax5.set_xlabel('Mes')
            ax5.set_ylabel('Pips')
            ax5.grid(True, alpha=0.3)
            plt.setp(ax5.xaxis.get_majorticklabels(), rotation=45)
        
        ax6 = plt.subplot(3, 3, 6)
        cumulative = df_trades['profit_percent'].cumsum()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) * 100
        ax6.fill_between(df_trades['entry_time'], 0, drawdown, color='red', alpha=0.5, label='Drawdown')
        ax6.set_title('Drawdown (%)', fontsize=12, fontweight='bold')
        ax6.set_xlabel('Fecha')
        ax6.set_ylabel('Drawdown %')
        ax6.grid(True, alpha=0.3)
        ax6.legend()
        
        ax7 = plt.subplot(3, 3, 7)
        ax7.scatter(range(len(df_trades)), df_trades['volume_ratio'], 
                   c=['green' if r == 'WIN' else 'red' for r in df_trades['result']], alpha=0.6, s=50)
        ax7.axhline(y=1.5, color='blue', linestyle='--', linewidth=1, label='Mínimo requerido (1.5x)')
        ax7.set_title('Ratio de Volumen por Operación', fontsize=12, fontweight='bold')
        ax7.set_xlabel('Operación #')
        ax7.set_ylabel('Volumen / Volumen[-1]')
        ax7.set_yscale('log')
        ax7.grid(True, alpha=0.3)
        ax7.legend()
        
        ax8 = plt.subplot(3, 3, 8)
        long_count = len(df_trades[df_trades['type'] == 'LONG'])
        short_count = len(df_trades[df_trades['type'] == 'SHORT'])
        long_wins = len(df_trades[(df_trades['type'] == 'LONG') & (df_trades['result'] == 'WIN')])
        short_wins = len(df_trades[(df_trades['type'] == 'SHORT') & (df_trades['result'] == 'WIN')])
        x = np.arange(2)
        width = 0.35
        bars1 = ax8.bar(x - width/2, [long_count, short_count], width, label='Total', color='gray', alpha=0.5)
        bars2 = ax8.bar(x + width/2, [long_wins, short_wins], width, label='Ganadoras', color='green', alpha=0.7)
        ax8.set_title('Distribución LONG/SHORT', fontsize=12, fontweight='bold')
        ax8.set_xticks(x)
        ax8.set_xticklabels(['LONG', 'SHORT'])
        ax8.set_ylabel('Cantidad')
        ax8.legend()
        ax8.grid(True, alpha=0.3)
        
        ax9 = plt.subplot(3, 3, 9)
        ax9.axis('off')
        metrics_text = f"""
        📊 RESUMEN EJECUTIVO
        {self.config.SYMBOL} | {len(self.trades)} operaciones
        🎯 WINRATE: {self.metrics['winrate']:.1f}%
        {'✓ CUMPLE OBJETIVO 95%' if self.metrics['winrate'] >= 95 else '✗ POR DEBAJO DEL OBJETIVO'}
        📈 RENDIMIENTO:
        Pips: {self.metrics['total_pips']:.1f}
        Profit: {self.metrics['total_profit_percent']:.1f}%
        📊 ESTADÍSTICAS:
        Profit Factor: {self.metrics['profit_factor']:.2f}
        Sharpe Ratio: {self.metrics['sharpe_ratio']:.2f}
        Max DD: {self.metrics['max_drawdown']:.1f}%
        Max Simultáneas: {self.metrics['max_simultaneous_trades']}
        ⏱️  FRECUENCIA:
        {self.metrics['trades_per_day']:.2f} ops/día
        """
        ax9.text(0.1, 0.9, metrics_text, fontsize=10, verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.suptitle(f'Backtest Estrategia 95K - {self.config.SYMBOL}\nPeríodo: {df_trades["entry_time"].min().strftime("%Y-%m-%d")} a {df_trades["entry_time"].max().strftime("%Y-%m-%d")}', 
                    fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        if self.config.SAVE_REPORT:
            plt.savefig('backtest_95k_chart.png', dpi=300, bbox_inches='tight')
            print("   💾 Gráfico guardado como 'backtest_95k_chart.png'")
        
        plt.show()
    
    def generate_report(self):
        if not self.config.SAVE_REPORT or not self.trades:
            return
        
        df_trades = pd.DataFrame(self.trades)
        
        html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Backtest Estrategia 95K - {self.config.SYMBOL}</title>
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{ font-family: 'Segoe UI', sans-serif; background-color: #f5f5f5; color: #333; line-height: 1.6; padding: 20px; }}
                .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1); }}
                h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-bottom: 30px; }}
                h2 {{ color: #34495e; margin: 25px 0 15px 0; }}
                .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                .card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .card h3 {{ color: rgba(255,255,255,0.9); margin-bottom: 15px; font-size: 16px; text-transform: uppercase; }}
                .card .metric-value {{ font-size: 36px; font-weight: bold; margin-bottom: 5px; }}
                .card .metric-label {{ font-size: 14px; opacity: 0.9; }}
                .stats-container {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 30px; }}
                .stats-box {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; }}
                .stats-box h3 {{ color: #495057; margin-bottom: 15px; border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
                .stat-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e9ecef; }}
                .stat-label {{ color: #6c757d; }}
                .stat-value {{ font-weight: bold; color: #2c3e50; }}
                .stat-value.positive {{ color: #27ae60; }}
                .stat-value.negative {{ color: #c0392b; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: white; }}
                th {{ background: #3498db; color: white; font-weight: 600; padding: 12px; text-align: left; }}
                td {{ padding: 10px 12px; border-bottom: 1px solid #e9ecef; }}
                tr:hover {{ background-color: #f8f9fa; }}
                .win {{ color: #27ae60; font-weight: bold; }}
                .loss {{ color: #c0392b; font-weight: bold; }}
                .badge {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold; text-transform: uppercase; }}
                .badge-win {{ background: #27ae60; color: white; }}
                .badge-loss {{ background: #c0392b; color: white; }}
                .footer {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #dee2e6; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📊 Backtest Estrategia 95K - {self.config.SYMBOL}</h1>
                <div style="background: #f1f9ff; padding: 15px; border-radius: 8px; margin-bottom: 30px;">
                    <p><strong>Período analizado:</strong> {df_trades['entry_time'].min().strftime('%Y-%m-%d %H:%M')} a {df_trades['entry_time'].max().strftime('%Y-%m-%d %H:%M')}</p>
                    <p><strong>Total días:</strong> {(df_trades['entry_time'].max() - df_trades['entry_time'].min()).days + 1}</p>
                </div>
                
                <h2>📈 Métricas Globales</h2>
                <div class="metrics-grid">
                    <div class="card">
                        <h3>Winrate</h3>
                        <div class="metric-value">{self.metrics['winrate']:.1f}%</div>
                        <div class="metric-label">{self.metrics['win_count']}W / {self.metrics['loss_count']}L</div>
                    </div>
                    <div class="card" style="background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);">
                        <h3>Pips Totales</h3>
                        <div class="metric-value">{self.metrics['total_pips']:.1f}</div>
                        <div class="metric-label">Promedio: {self.metrics['avg_pips_win']:.1f}W / {self.metrics['avg_pips_loss']:.1f}L</div>
                    </div>
                    <div class="card" style="background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);">
                        <h3>Profit %</h3>
                        <div class="metric-value">{self.metrics['total_profit_percent']:.2f}%</div>
                        <div class="metric-label">Riesgo: {self.config.RISK_PERCENT}%</div>
                    </div>
                </div>
                
                <div class="stats-container">
                    <div class="stats-box">
                        <h3>📊 Estadísticas</h3>
                        <div class="stat-row"><span class="stat-label">Profit Factor:</span><span class="stat-value">{self.metrics['profit_factor']:.2f}</span></div>
                        <div class="stat-row"><span class="stat-label">Sharpe Ratio:</span><span class="stat-value">{self.metrics['sharpe_ratio']:.2f}</span></div>
                        <div class="stat-row"><span class="stat-label">Max Drawdown:</span><span class="stat-value negative">{self.metrics['max_drawdown']:.2f}%</span></div>
                        <div class="stat-row"><span class="stat-label">Max Simultáneas:</span><span class="stat-value">{self.metrics['max_simultaneous_trades']}</span></div>
                        <div class="stat-row"><span class="stat-label">Ops/Día:</span><span class="stat-value">{self.metrics['trades_per_day']:.2f}</span></div>
                    </div>
                    <div class="stats-box">
                        <h3>🎯 Rachas</h3>
                        <div class="stat-row"><span class="stat-label">Max Wins:</span><span class="stat-value positive">{self.metrics['max_consecutive_wins']}</span></div>
                        <div class="stat-row"><span class="stat-label">Max Losses:</span><span class="stat-value negative">{self.metrics['max_consecutive_losses']}</span></div>
                        <div class="stat-row"><span class="stat-label">LONG:</span><span class="stat-value">{self.metrics['long_trades']}</span></div>
                        <div class="stat-row"><span class="stat-label">SHORT:</span><span class="stat-value">{self.metrics['short_trades']}</span></div>
                    </div>
                </div>
                
                <h2>📅 Rendimiento Mensual</h2>
                <table>
                    <thead><tr><th>Mes</th><th>Total</th><th>Wins</th><th>Losses</th><th>Winrate %</th><th>Pips</th><th>Profit %</th></tr></thead>
                    <tbody>
        """
        
        for month, row in self.monthly_metrics.iterrows():
            winrate_color = "win" if row['winrate'] >= 95 else "loss" if row['winrate'] < 90 else ""
            pips_color = "positive" if row['total_pips'] >= 0 else "negative"
            html += f"""
                        <tr>
                            <td><strong>{month}</strong></td>
                            <td>{int(row['total_trades'])}</td>
                            <td class="win">{int(row['wins'])}</td>
                            <td class="loss">{int(row['losses'])}</td>
                            <td class="{winrate_color}">{row['winrate']:.1f}%</td>
                            <td class="{pips_color}">{row['total_pips']:.1f}</td>
                            <td class="{pips_color}">{row['profit_percent']:.2f}%</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
                
                <h2>📋 Detalle de Operaciones</h2>
                <table>
                    <thead>
                        <tr><th>Fecha Entrada</th><th>Tipo</th><th>Entrada</th><th>SL</th><th>TP</th><th>Resultado</th><th>Pips</th><th>Profit %</th></tr>
                    </thead>
                    <tbody>
        """
        
        for _, trade in df_trades.iterrows():
            result_class = 'win' if trade['result'] == 'WIN' else 'loss'
            badge_class = 'badge-win' if trade['result'] == 'WIN' else 'badge-loss'
            html += f"""
                        <tr>
                            <td>{trade['entry_time'].strftime('%Y-%m-%d %H:%M')}</td>
                            <td>{trade['type']}</td>
                            <td>{trade['entry_price']:.5f}</td>
                            <td>{trade['sl']:.5f}</td>
                            <td>{trade['tp']:.5f}</td>
                            <td><span class="badge {badge_class}">{trade['result']}</span></td>
                            <td class="{result_class}">{trade['pips']:.1f}</td>
                            <td class="{result_class}">{trade['profit_percent']:.2f}%</td>
                        </tr>
            """
        
        html += f"""
                    </tbody>
                </table>
                <div class="footer">
                    <p>Backtest generado el {datetime.now().strftime('%Y-%m-%d %H:%M')} | RR={self.config.RR_RATIO} | SL Buffer={self.config.SL_BUFFER}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        with open(self.config.REPORT_FILENAME, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"\n📁 Reporte HTML guardado como: {self.config.REPORT_FILENAME}")

def main():
    print("="*70)
    print("🚀 BACKTESTING ESTRATEGIA '95K' - VERSIÓN DATOS SEPARADOS")
    print("="*70)
    
    bt = Backtest95K(Config)
    
    if not bt.load_data():
        print("\n❌ Error: No se pudieron cargar los datos.")
        return
    
    bt.align_trend_to_m15()
    bt.run_backtest()
    
    if bt.trades:
        bt.print_metrics()
        bt.print_monthly_metrics()
        bt.plot_results()
        bt.generate_report()
        
        print("\n" + "="*70)
        print("✅ BACKTEST COMPLETADO EXITOSAMENTE")
        print("="*70)
        print("\nArchivos generados:")
        print("   • trades_detalle.csv - Detalle de operaciones")
        print(f"   • {Config.REPORT_FILENAME} - Reporte HTML")
        print("   • backtest_95k_chart.png - Gráficos")
    else:
        print("\n⚠️  No se encontraron señales de trading.")

if __name__ == "__main__":
    main()