#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPTIMIZADOR DE HORAS A EVITAR - VERSIÓN BITMASK ULTRA RÁPIDA
Itera de 0 a 2^24 usando máscaras de bits para representar combinaciones
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import pickle
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import warnings
import psutil
import gc
import time
import signal
import sys

warnings.filterwarnings('ignore')

class OptimizadorHorasBitmask:
    def __init__(self, trades_csv_path, drawdown_min_esperado=3, checkpoint_file='optimizador_bitmask_checkpoint.pkl'):
        """
        Inicializa el optimizador con enfoque de máscara de bits
        """
        print("📊 Cargando datos...")
        self.trades_df = pd.read_csv(trades_csv_path)
        self.trades_df['entry_time'] = pd.to_datetime(self.trades_df['entry_time'])
        self.trades_df['hour'] = self.trades_df['entry_time'].dt.hour
        
        # Pre-calcular todo para acceso instantáneo
        self._precalcular_todo()
        
        self.drawdown_min_esperado = drawdown_min_esperado
        self.mejor_config = None
        self.mejor_valor_ajustado = 0  # Valor ajustado por riesgo (no solo winrate)
        self.mejor_winrate = 0
        self.max_profit_registrado = 0
        self.resultados = []
        self.checkpoint_file = checkpoint_file
        
        # Estado de la ejecución
        self.current_index = 0  # Índice actual en la iteración
        self.total_combinaciones = 2**24  # 16,777,216
        self.processed_count = 0
        self.best_configs = []  # Guardar top configs por valor ajustado
        
        # Detectar recursos
        self.num_cpus = mp.cpu_count()
        self.memoria_disponible = psutil.virtual_memory().available / (1024**3)
        
        # Calcular tamaño de lote óptimo para procesamiento paralelo
        self.tamano_lote = self._calcular_tamano_lote()
        
        print(f"   ✅ {len(self.trades_df)} operaciones cargadas")
        print(f"   💻 CPUs detectados: {self.num_cpus}")
        print(f"   💾 Memoria disponible: {self.memoria_disponible:.2f} GB")
        print(f"   📦 Tamaño de lote: {self.tamano_lote:,} combinaciones")
        print(f"   🎯 Total a procesar: {self.total_combinaciones:,} combinaciones")
        
        # Cargar checkpoint
        self._cargar_checkpoint()
        
        # Configurar manejador de señal
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _precalcular_todo(self):
        """Pre-calcula TODOS los datos necesarios para acceso O(1)"""
        print("⚡ Pre-calculando estructuras de datos óptimas...")
        
        # 1. Estadísticas por hora (array numpy para acceso rápido)
        self.stats_por_hora = np.zeros(24, dtype=[
            ('count', 'i4'),
            ('wins', 'i4'),
            ('profit', 'f8'),
            ('pips_wins', 'f8'),
            ('pips_losses', 'f8'),
            ('cumulative_idx_start', 'i4'),
            ('cumulative_idx_end', 'i4')
        ])
        
        # 2. Array único con todos los profits para drawdown rápido
        all_profits_list = []
        current_idx = 0
        
        # Mostrar distribución inicial por hora para referencia
        print("\n📊 Distribución inicial por hora:")
        
        for hour in range(24):
            mask = self.trades_df['hour'] == hour
            df_hour = self.trades_df[mask]
            
            if len(df_hour) > 0:
                wins = (df_hour['result'] == 'WIN').sum()
                profits = df_hour['profit_percent'].values
                winrate_hora = (wins / len(df_hour) * 100)
                
                print(f"   Hora {hour:02d}: {len(df_hour):4d} ops, WR: {winrate_hora:5.1f}%, Profit: {profits.sum():7.2f}%")
                
                self.stats_por_hora[hour]['count'] = len(df_hour)
                self.stats_por_hora[hour]['wins'] = wins
                self.stats_por_hora[hour]['profit'] = profits.sum()
                self.stats_por_hora[hour]['pips_wins'] = df_hour[df_hour['result'] == 'WIN']['pips'].sum() if wins > 0 else 0
                self.stats_por_hora[hour]['pips_losses'] = df_hour[df_hour['result'] == 'LOSS']['pips'].sum() if (len(df_hour) - wins) > 0 else 0
                self.stats_por_hora[hour]['cumulative_idx_start'] = current_idx
                
                all_profits_list.extend(profits)
                current_idx += len(profits)
                self.stats_por_hora[hour]['cumulative_idx_end'] = current_idx
            else:
                print(f"   Hora {hour:02d}: 0 ops")
                self.stats_por_hora[hour]['count'] = 0
                self.stats_por_hora[hour]['cumulative_idx_start'] = current_idx
                self.stats_por_hora[hour]['cumulative_idx_end'] = current_idx
        
        # 3. Array único de profits para cálculos vectorizados
        self.all_profits = np.array(all_profits_list, dtype=np.float32)
        
        # 4. Pre-calcular suma acumulada para drawdown rápido
        self.cumsum_profits = np.cumsum(self.all_profits)
        
        print(f"\n   ✅ Arrays optimizados creados: {len(self.all_profits)} trades totales")
    
    def _calcular_tamano_lote(self):
        """Calcula tamaño de lote óptimo basado en memoria y CPUs"""
        # Estimación conservadora: cada combinación procesada requiere ~1KB
        memoria_por_combinacion = 1024
        memoria_segura = self.memoria_disponible * 0.6 * (1024**3)
        tamano_por_memoria = int(memoria_segura / memoria_por_combinacion)
        
        # Ajustar por número de CPUs (cada CPU procesará sublotes)
        tamano_por_cpu = max(10000, tamano_por_memoria // self.num_cpus)
        
        return min(tamano_por_cpu * self.num_cpus, 500000)  # Máximo 500k
    
    def _cargar_checkpoint(self):
        """Carga el estado guardado"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'rb') as f:
                    checkpoint = pickle.load(f)
                    
                self.current_index = checkpoint.get('current_index', 0)
                self.processed_count = checkpoint.get('processed_count', 0)
                self.mejor_config = checkpoint.get('mejor_config')
                self.mejor_valor_ajustado = checkpoint.get('mejor_valor_ajustado', 0)
                self.mejor_winrate = checkpoint.get('mejor_winrate', 0)
                self.max_profit_registrado = checkpoint.get('max_profit_registrado', 0)
                self.resultados = checkpoint.get('resultados', [])
                self.best_configs = checkpoint.get('best_configs', [])
                
                print(f"🔄 Checkpoint cargado: {self.processed_count:,} combinaciones procesadas")
                print(f"   Progreso: {self.current_index:,} / {self.total_combinaciones:,} ({self.current_index/self.total_combinaciones*100:.2f}%)")
                print(f"   Mejor valor ajustado: {self.mejor_valor_ajustado:.4f}")
                print(f"   Mejor winrate: {self.mejor_winrate:.2f}%")
            except Exception as e:
                print(f"⚠️ Error cargando checkpoint: {e}")
                self.current_index = 0
                self.processed_count = 0
    
    def _guardar_checkpoint(self):
        """Guarda el estado actual"""
        try:
            checkpoint = {
                'current_index': self.current_index,
                'processed_count': self.processed_count,
                'mejor_config': self.mejor_config,
                'mejor_valor_ajustado': self.mejor_valor_ajustado,
                'mejor_winrate': self.mejor_winrate,
                'max_profit_registrado': self.max_profit_registrado,
                'resultados': self.resultados[-1000:],  # Solo últimos 1000
                'best_configs': self.best_configs[:100],  # Top 100 configs
                'timestamp': datetime.now().isoformat()
            }
            
            # Guardar temporal y renombrar para evitar corrupción
            temp_file = f"{self.checkpoint_file}.tmp"
            with open(temp_file, 'wb') as f:
                pickle.dump(checkpoint, f)
            
            os.replace(temp_file, self.checkpoint_file)
            
            print(f"💾 Checkpoint guardado: {self.processed_count:,}/{self.total_combinaciones:,} "
                  f"({self.processed_count/self.total_combinaciones*100:.2f}%)")
                
        except Exception as e:
            print(f"⚠️ Error guardando checkpoint: {e}")
    
    def _signal_handler(self, signum, frame):
        """Manejador de señal para guardar antes de salir"""
        print("\n\n⚠️ Interrupción detectada. Guardando checkpoint...")
        self._guardar_checkpoint()
        print("✅ Checkpoint guardado. Puedes reanudar después.")
        sys.exit(0)
    
    def _calcular_valor_ajustado_por_riesgo(self, profit, max_drawdown):
        """
        Calcula el valor ajustado por riesgo según la fórmula:
        (1 / max_drawdown) * drawdown_min_esperado * profit
        """
        if max_drawdown <= 0:
            return 0
        return (1.0 / max_drawdown) * self.drawdown_min_esperado * profit
    
    @staticmethod
    def procesar_lote_bitmask(args):
        """
        Procesa un rango de números usando máscaras de bits
        Esta función es estática para poder serializarse
        """
        inicio, fin, stats_por_hora, all_profits, cumsum_profits, drawdown_min_esperado, max_profit_actual = args
        
        resultados_lote = []
        mejoras_lote = []
        
        for mask in range(inicio, fin):
            # Encontrar horas activas (bits en 1 = horas a evitar)
            horas_evitar = []
            mascara_temp = mask
            pos = 0
            
            while mascara_temp:
                if mascara_temp & 1:
                    horas_evitar.append(pos)
                mascara_temp >>= 1
                pos += 1
            
            # Calcular métricas usando los arrays pre-calculados
            total_trades = 0
            total_wins = 0
            profit_sum = 0.0
            pips_wins_sum = 0.0
            pips_losses_sum = 0.0
            
            # Arrays para reconstruir secuencia de profits
            profit_indices = []
            
            # Iterar sobre todas las horas
            for hour in range(24):
                # Verificar si la hora está en horas_evitar (bit activo)
                if mask & (1 << hour):  # Hora a evitar
                    continue
                
                # Hora activa - sumar estadísticas
                stats = stats_por_hora[hour]
                if stats['count'] > 0:
                    total_trades += stats['count']
                    total_wins += stats['wins']
                    profit_sum += stats['profit']
                    pips_wins_sum += stats['pips_wins']
                    pips_losses_sum += stats['pips_losses']
                    
                    # Guardar rango de índices para este hour
                    if stats['cumulative_idx_end'] > stats['cumulative_idx_start']:
                        profit_indices.append((stats['cumulative_idx_start'], stats['cumulative_idx_end']))
            
            if total_trades == 0:
                continue
            
            winrate = (total_wins / total_trades * 100.0)
            
            # Calcular drawdown máximo usando índices
            max_drawdown = 0.0
            if profit_indices:
                # Reconstruir secuencia de profits para este subconjunto
                all_segments = []
                for start, end in profit_indices:
                    all_segments.append(all_profits[start:end])
                
                if all_segments:
                    profits_seq = np.concatenate(all_segments) if len(all_segments) > 1 else all_segments[0]
                    
                    # Calcular drawdown de manera vectorizada
                    if len(profits_seq) > 0:
                        cumulative = np.cumsum(profits_seq)
                        running_max = np.maximum.accumulate(cumulative)
                        drawdowns = cumulative - running_max
                        max_drawdown = abs(np.min(drawdowns))
            
            # Calcular valor ajustado por riesgo
            if max_drawdown > 0:
                valor_ajustado = (1.0 / max_drawdown) * drawdown_min_esperado * profit_sum
            else:
                valor_ajustado = 0
            
            # Profit factor
            profit_factor = abs(pips_wins_sum / pips_losses_sum) if pips_losses_sum != 0 else float('inf')
            
            metricas = {
                'mask': mask,
                'horas_evitar': horas_evitar,
                'total_trades': int(total_trades),
                'wins': int(total_wins),
                'losses': int(total_trades - total_wins),
                'winrate': float(winrate),
                'profit_general': float(profit_sum),
                'max_drawdown': float(max_drawdown),
                'valor_ajustado': float(valor_ajustado),
                'profit_factor': float(profit_factor),
                'avg_win_pips': float(pips_wins_sum / total_wins) if total_wins > 0 else 0,
                'avg_loss_pips': float(pips_losses_sum / (total_trades - total_wins)) if (total_trades - total_wins) > 0 else 0,
                'trades_eliminados': int(sum(stats_por_hora[h]['count'] for h in horas_evitar if h < 24))
            }
            
            resultados_lote.append(metricas)
            
            # Verificar si es mejor que la actual (por valor ajustado)
            if valor_ajustado > 0 and valor_ajustado > max_profit_actual:
                mejoras_lote.append(metricas)
        
        return resultados_lote, mejoras_lote
    
    def optimizar(self):
        """
        Optimiza iterando de 0 a 2^24 usando máscaras de bits
        """
        print("\n" + "="*70)
        print("🔍 INICIANDO OPTIMIZACIÓN BITMASK")
        print("="*70)
        print(f"🎯 Objetivo: Maximizar (1/DD) * {self.drawdown_min_esperado} * Profit")
        
        # Calcular métricas iniciales (mask=0 = ninguna hora evitada)
        if self.current_index == 0:
            print("\n📊 Calculando configuración base (sin filtrar horas)...")
            resultados_inicial, _ = self.procesar_lote_bitmask(
                (0, 1, self.stats_por_hora, self.all_profits, self.cumsum_profits, 
                 self.drawdown_min_esperado, self.max_profit_registrado)
            )
            if resultados_inicial:
                inicial = resultados_inicial[0]
                self.max_profit_registrado = inicial['profit_general']
                self.mejor_valor_ajustado = inicial['valor_ajustado']
                self.mejor_config = inicial
                self.mejor_winrate = inicial['winrate']
                
                print(f"\n📈 Configuración BASE (sin filtrar):")
                print(f"   Profit: {inicial['profit_general']:.2f}%")
                print(f"   Winrate: {inicial['winrate']:.2f}%")
                print(f"   Max DD: {inicial['max_drawdown']:.2f}%")
                print(f"   Valor ajustado: {inicial['valor_ajustado']:.4f}")
        
        print(f"\n📊 Progreso actual: {self.current_index:,} / {self.total_combinaciones:,}")
        print(f"   {(self.current_index/self.total_combinaciones*100):.2f}% completado")
        
        if self.current_index >= self.total_combinaciones:
            print("✅ Optimización ya completada")
            return self.mejor_config
        
        # Calcular lotes para procesamiento paralelo
        rango_restante = self.total_combinaciones - self.current_index
        num_lotes = max(self.num_cpus * 2, rango_restante // self.tamano_lote + 1)
        tamano_lote_actual = max(1000, rango_restante // num_lotes)
        
        lotes = []
        for i in range(self.current_index, self.total_combinaciones, tamano_lote_actual):
            fin = min(i + tamano_lote_actual, self.total_combinaciones)
            lotes.append((i, fin))
        
        print(f"\n🚀 Procesando {len(lotes)} lotes con {self.num_cpus} CPUs")
        print(f"   Tamaño de lote: ~{tamano_lote_actual:,} combinaciones")
        
        mejoras_encontradas = 0
        tiempo_inicio = time.time()
        lotes_procesados = 0
        
        # Procesar lotes con ProgressBar
        with tqdm(total=len(lotes), desc="Lotes completados") as pbar:
            for lote_idx, (inicio_lote, fin_lote) in enumerate(lotes):
                # Dividir el lote en sublotes para paralelismo
                num_sublotes = min(self.num_cpus, (fin_lote - inicio_lote) // 1000 + 1)
                sublotes = []
                paso = (fin_lote - inicio_lote) // num_sublotes
                
                for i in range(num_sublotes):
                    sub_inicio = inicio_lote + i * paso
                    sub_fin = inicio_lote + (i + 1) * paso if i < num_sublotes - 1 else fin_lote
                    if sub_inicio < sub_fin:
                        sublotes.append((
                            sub_inicio, sub_fin, self.stats_por_hora, self.all_profits,
                            self.cumsum_profits, self.drawdown_min_esperado, self.mejor_valor_ajustado
                        ))
                
                # Procesar sublotes en paralelo
                with ProcessPoolExecutor(max_workers=self.num_cpus) as executor:
                    futures = [executor.submit(self.procesar_lote_bitmask, args) for args in sublotes]
                    
                    for future in as_completed(futures):
                        try:
                            resultados_sublote, mejoras_sublote = future.result(timeout=300)
                            
                            # Actualizar resultados
                            self.resultados.extend(resultados_sublote)
                            
                            # Procesar mejoras (basadas en valor ajustado)
                            for mejora in mejoras_sublote:
                                if mejora['valor_ajustado'] > self.mejor_valor_ajustado:
                                    self.mejor_valor_ajustado = mejora['valor_ajustado']
                                    self.mejor_config = mejora
                                    self.mejor_winrate = mejora['winrate']
                                    self.max_profit_registrado = mejora['profit_general']
                                    mejoras_encontradas += 1
                                    
                                    print(f"\n✨ ¡MEJORA #{mejoras_encontradas}!")
                                    print(f"   Mask: {mejora['mask']:06X}")
                                    print(f"   Horas a evitar: {mejora['horas_evitar']}")
                                    print(f"   Winrate: {mejora['winrate']:.2f}%")
                                    print(f"   Profit: {mejora['profit_general']:.2f}%")
                                    print(f"   Max DD: {mejora['max_drawdown']:.2f}%")
                                    print(f"   Valor ajustado: {mejora['valor_ajustado']:.4f} (vs anterior {self.mejor_valor_ajustado:.4f})")
                                    
                                    # Guardar en top configs (ordenado por valor ajustado)
                                    self.best_configs.append(mejora)
                                    self.best_configs.sort(key=lambda x: x['valor_ajustado'], reverse=True)
                                    self.best_configs = self.best_configs[:100]
                            
                        except Exception as e:
                            print(f"\n⚠️ Error en sublote: {e}")
                            continue
                
                # Actualizar progreso
                self.current_index = fin_lote
                self.processed_count = fin_lote
                lotes_procesados += 1
                pbar.update(1)
                pbar.set_postfix({
                    'mejor_valor': f"{self.mejor_valor_ajustado:.4f}",
                    'mejoras': mejoras_encontradas
                })
                
                # Guardar checkpoint periódicamente
                if lotes_procesados % 5 == 0:  # Cada 5 lotes
                    self._guardar_checkpoint()
                    # Limpiar memoria
                    self.resultados = self.resultados[-1000:]
                    gc.collect()
        
        tiempo_total = time.time() - tiempo_inicio
        print(f"\n⏱️ Tiempo total: {tiempo_total:.2f} segundos")
        print(f"📈 Velocidad: {self.total_combinaciones / tiempo_total:.0f} combinaciones/segundo")
        
        # Guardar checkpoint final
        self._guardar_checkpoint()
        
        # Ordenar resultados finales por valor ajustado
        self.resultados.sort(key=lambda x: x['valor_ajustado'], reverse=True)
        
        return self.mejor_config
    
    def generar_reporte_html(self, filename='optimizacion_bitmask.html'):
        """
        Genera reporte HTML con resultados
        """
        if not self.mejor_config:
            print("❌ No hay resultados para generar reporte - La optimización no se ha ejecutado")
            return
        
        print("\n📊 Generando reporte HTML...")
        
        # Calcular métricas iniciales (mask=0)
        resultados_inicial, _ = self.procesar_lote_bitmask(
            (0, 1, self.stats_por_hora, self.all_profits, self.cumsum_profits, 
             self.drawdown_min_esperado, self.mejor_valor_ajustado)
        )
        metricas_iniciales = resultados_inicial[0] if resultados_inicial else None
        
        # Estadísticas adicionales
        total_mejoras = len([r for r in self.resultados if r['valor_ajustado'] > (metricas_iniciales['valor_ajustado'] if metricas_iniciales else 0)])
        mejora_relativa = ((self.mejor_valor_ajustado / metricas_iniciales['valor_ajustado'] - 1) * 100) if metricas_iniciales and metricas_iniciales['valor_ajustado'] > 0 else 0
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Optimización Bitmask - Resultados</title>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 20px;
                    background: #f5f5f5;
                }}
                .container {{ 
                    max-width: 1400px; 
                    margin: 0 auto;
                    background: white;
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                }}
                h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #34495e; margin-top: 30px; }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin: 20px 0;
                }}
                .stat-box {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 8px;
                    border-left: 4px solid #3498db;
                }}
                .stat-box .label {{
                    color: #7f8c8d;
                    font-size: 14px;
                    text-transform: uppercase;
                }}
                .stat-box .value {{
                    color: #2c3e50;
                    font-size: 24px;
                    font-weight: bold;
                }}
                .stat-box .sub {{
                    color: #95a5a6;
                    font-size: 12px;
                }}
                .mejor-config {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white; 
                    padding: 25px; 
                    border-radius: 10px;
                    margin: 20px 0;
                }}
                .comparison-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin: 20px 0;
                }}
                .config-card {{
                    background: white;
                    border-radius: 10px;
                    padding: 20px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .config-card.original {{ border-left: 5px solid #3498db; }}
                .config-card.optimized {{ border-left: 5px solid #27ae60; }}
                .badge-optimized {{ background: #27ae60; color: white; padding: 3px 8px; border-radius: 3px; }}
                table {{ 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin: 20px 0;
                    background: white;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                th, td {{ 
                    padding: 12px; 
                    text-align: left; 
                    border-bottom: 1px solid #ddd; 
                }}
                th {{ 
                    background: #34495e; 
                    color: white; 
                }}
                tr:hover {{ background: #f5f6fa; }}
                .badge {{
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 3px;
                    font-size: 12px;
                    font-weight: bold;
                    margin: 2px;
                }}
                .badge-win {{ background: #27ae60; color: white; }}
                .badge-loss {{ background: #c0392b; color: white; }}
                .mejora {{ color: #27ae60; font-weight: bold; }}
                .footer {{ text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ecf0f1; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎯 Optimización de Horas a Evitar - Análisis por Máscara de Bits</h1>
                
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="label">Fecha análisis</div>
                        <div class="value">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Combinaciones evaluadas</div>
                        <div class="value">{self.processed_count:,}</div>
                        <div class="sub">de {self.total_combinaciones:,} totales ({self.processed_count/self.total_combinaciones*100:.2f}%)</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Mejoras encontradas</div>
                        <div class="value">{total_mejoras}</div>
                        <div class="sub">vs configuración base</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Drawdown objetivo</div>
                        <div class="value">{self.drawdown_min_esperado}%</div>
                    </div>
                </div>
                
                <h2>📊 Comparativa: Base vs Optimizado</h2>
                
                <div class="comparison-grid">
                    <!-- Configuración Base -->
                    <div class="config-card original">
                        <h3 style="color: #3498db; margin-top: 0;">⚙️ Configuración Base (Sin filtrar)</h3>
                        <p><strong>Horas evitadas:</strong> Ninguna</p>
                        <div class="stats-grid" style="grid-template-columns: 1fr 1fr;">
                            <div>
                                <div class="label">Winrate</div>
                                <div class="value" style="font-size: 20px;">{metricas_iniciales['winrate']:.2f}%</div>
                                <div>{metricas_iniciales['wins']}W / {metricas_iniciales['losses']}L</div>
                            </div>
                            <div>
                                <div class="label">Profit</div>
                                <div class="value" style="font-size: 20px;">{metricas_iniciales['profit_general']:.2f}%</div>
                            </div>
                            <div>
                                <div class="label">Max Drawdown</div>
                                <div class="value" style="font-size: 20px;">{metricas_iniciales['max_drawdown']:.2f}%</div>
                            </div>
                            <div>
                                <div class="label">Valor Ajustado</div>
                                <div class="value" style="font-size: 20px;">{metricas_iniciales['valor_ajustado']:.4f}</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Configuración Optimizada -->
                    <div class="config-card optimized">
                        <h3 style="color: #27ae60; margin-top: 0;">🏆 Configuración Optimizada</h3>
                        <p><strong>Máscara binaria:</strong> <code>{self.mejor_config['mask']:024b}</code></p>
                        <p><strong>Horas a evitar:</strong> 
                            {''.join([f'<span class="badge badge-win">{h:02d}:00</span>' for h in self.mejor_config['horas_evitar']])}
                        </p>
                        <div class="stats-grid" style="grid-template-columns: 1fr 1fr;">
                            <div>
                                <div class="label">Winrate</div>
                                <div class="value" style="font-size: 20px;">{self.mejor_config['winrate']:.2f}%</div>
                                <div class="mejora">(+{self.mejor_config['winrate'] - metricas_iniciales['winrate']:.2f}%)</div>
                            </div>
                            <div>
                                <div class="label">Profit</div>
                                <div class="value" style="font-size: 20px;">{self.mejor_config['profit_general']:.2f}%</div>
                                <div class="mejora">(+{self.mejor_config['profit_general'] - metricas_iniciales['profit_general']:.2f}%)</div>
                            </div>
                            <div>
                                <div class="label">Max Drawdown</div>
                                <div class="value" style="font-size: 20px;">{self.mejor_config['max_drawdown']:.2f}%</div>
                                <div class="{'mejora' if self.mejor_config['max_drawdown'] < metricas_iniciales['max_drawdown'] else ''}">
                                    ({'↓' if self.mejor_config['max_drawdown'] < metricas_iniciales['max_drawdown'] else '↑'} 
                                    {abs(self.mejor_config['max_drawdown'] - metricas_iniciales['max_drawdown']):.2f}%)
                                </div>
                            </div>
                            <div>
                                <div class="label">Valor Ajustado</div>
                                <div class="value" style="font-size: 20px;">{self.mejor_config['valor_ajustado']:.4f}</div>
                                <div class="mejora">(+{mejora_relativa:.1f}%)</div>
                            </div>
                        </div>
                        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.2);">
                            <strong>Trades:</strong> {self.mejor_config['total_trades']} ({self.mejor_config['trades_eliminados']} eliminados)
                        </div>
                    </div>
                </div>
                
                <h2>📈 Top 10 Configuraciones por Valor Ajustado</h2>
                
                <table>
                    <tr>
                        <th>#</th>
                        <th>Máscara</th>
                        <th>Horas Evitadas</th>
                        <th>WR%</th>
                        <th>Profit%</th>
                        <th>Max DD%</th>
                        <th>Valor Ajustado</th>
                        <th>Trades</th>
                    </tr>
        """
        
        for i, config in enumerate(self.best_configs[:10], 1):
            horas_str = ', '.join([f"{h:02d}:00" for h in config['horas_evitar']])
            es_mejor = config['mask'] == self.mejor_config['mask']
            row_style = ' style="background: #f0fff4;"' if es_mejor else ''
            
            html += f"""
                    <tr{row_style}>
                        <td><strong>#{i}{' 🏆' if es_mejor else ''}</strong></td>
                        <td><code>{config['mask']:024b}</code></td>
                        <td>{horas_str}</td>
                        <td>{config['winrate']:.2f}%</td>
                        <td>{config['profit_general']:.2f}%</td>
                        <td>{config['max_drawdown']:.2f}%</td>
                        <td><strong>{config['valor_ajustado']:.4f}</strong></td>
                        <td>{config['total_trades']}</td>
                    </tr>
            """
        
        html += f"""
                </table>
                
                <h2>📊 Análisis de Mejora</h2>
                
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="label">Mejor winrate encontrado</div>
                        <div class="value">{max([c['winrate'] for c in self.best_configs] + [0]):.2f}%</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Mejor profit encontrado</div>
                        <div class="value">{max([c['profit_general'] for c in self.best_configs] + [0]):.2f}%</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Mejor drawdown</div>
                        <div class="value">{min([c['max_drawdown'] for c in self.best_configs] + [float('inf')]):.2f}%</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Total configs guardadas</div>
                        <div class="value">{len(self.best_configs)}</div>
                    </div>
                </div>
                
                <div class="footer">
                    <p>Optimización completada: {self.processed_count:,} combinaciones analizadas</p>
                    <p>Mejor valor ajustado: {self.mejor_valor_ajustado:.4f} (objetivo: maximizar (1/DD) * {self.drawdown_min_esperado} * Profit)</p>
                    <p>⚡ Procesamiento con máscara de bits - {self.num_cpus} CPUs utilizados</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ Reporte generado: {filename}")

def main():
    print("="*70)
    print("🚀 OPTIMIZADOR BITMASK ULTRA RÁPIDO")
    print("="*70)
    
    # Configuración
    TRADES_CSV = 'trades_detalle.csv'
    DRAWDOWN_MIN_ESPERADO = 3
    CHECKPOINT_FILE = 'optimizador_bitmask_checkpoint.pkl'
    
    print("\n⚙️ Configuración:")
    print(f"   📁 Archivo trades: {TRADES_CSV}")
    print(f"   📊 Drawdown min esperado: {DRAWDOWN_MIN_ESPERADO}%")
    print(f"   💾 Checkpoint: {CHECKPOINT_FILE}")
    print(f"   🎯 Objetivo: Maximizar (1/DD) * {DRAWDOWN_MIN_ESPERADO} * Profit")
    
    # Crear optimizador
    optimizador = OptimizadorHorasBitmask(
        TRADES_CSV, 
        DRAWDOWN_MIN_ESPERADO,
        CHECKPOINT_FILE
    )
    
    # Ejecutar optimización
    mejor_config = optimizador.optimizar()
    
    # Mostrar resultado
    if mejor_config:
        print("\n" + "="*70)
        print("🏆 RESULTADO FINAL")
        print("="*70)
        print(f"\n✅ Mejor configuración encontrada:")
        print(f"   Máscara: {mejor_config['mask']:024b}")
        print(f"   Horas a evitar: {mejor_config['horas_evitar']}")
        print(f"   Winrate: {mejor_config['winrate']:.2f}%")
        print(f"   Profit: {mejor_config['profit_general']:.2f}%")
        print(f"   Max DD: {mejor_config['max_drawdown']:.2f}%")
        print(f"   Valor ajustado: {mejor_config['valor_ajustado']:.4f}")
        print(f"   Trades: {mejor_config['total_trades']}")
    
    # Generar reporte (AHORA SÍ, después de la optimización)
    print("\n" + "="*70)
    optimizador.generar_reporte_html('optimizacion_bitmask.html')
    
    print("\n" + "="*70)
    print("✅ PROCESO COMPLETADO")
    print("="*70)

if __name__ == "__main__":
    mp.freeze_support()
    main()