import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class KnapsackTimeOptimizer:
    """
    Optimizador de Horas usando Programación Dinámica (Algoritmo de la Mochila)
    Determina qué horas operar para maximizar el profit total con restricciones de riesgo
    """
    
    def __init__(self, df):
        self.df = df
        self.hourly_data = None
        self.dp_table = None
        self.selected_hours = None
        
    def prepare_hourly_data(self):
        """Prepara los datos por hora para el análisis"""
        print("📊 Preparando datos por hora...")
        
        hourly_stats = []
        
        for hour in range(24):
            hour_data = self.df[self.df['hour'] == hour]
            
            if len(hour_data) == 0:
                continue
                
            total_profit = hour_data['profit_percent'].sum()
            total_trades = len(hour_data)
            wins = len(hour_data[hour_data['result'] == 'WIN'])
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            
            # Calcular riesgo (desviación estándar de los retornos)
            risk = hour_data['profit_percent'].std() if total_trades > 1 else 1
            
            # Calcular Sharpe ratio (rendimiento ajustado por riesgo)
            sharpe = (hour_data['profit_percent'].mean() / risk) * np.sqrt(252) if risk > 0 else 0
            
            # Calcular drawdown máximo para esta hora
            cumulative = hour_data['profit_percent'].cumsum()
            running_max = cumulative.expanding().max()
            drawdown = cumulative - running_max
            max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0
            
            hourly_stats.append({
                'hour': hour,
                'profit': total_profit,
                'trades': total_trades,
                'wins': wins,
                'losses': total_trades - wins,
                'win_rate': win_rate,
                'risk': risk,
                'sharpe': sharpe,
                'max_drawdown': max_drawdown,
                'avg_profit': hour_data['profit_percent'].mean(),
                'profit_per_trade': total_profit / total_trades if total_trades > 0 else 0
            })
        
        self.hourly_data = pd.DataFrame(hourly_stats)
        self.hourly_data = self.hourly_data.sort_values('profit', ascending=False).reset_index(drop=True)
        
        print(f"   ✅ {len(self.hourly_data)} horas con datos")
        return self.hourly_data
    
    def knapsack_optimization(self, risk_capacity=10, min_trades=50):
        """
        Algoritmo de la mochila para selección óptima de horas
        
        Parámetros:
        - risk_capacity: Capacidad máxima de riesgo aceptable (% de drawdown)
        - min_trades: Mínimo de operaciones requeridas
        """
        print("\n🎯 Ejecutando optimización tipo mochila...")
        
        n_hours = len(self.hourly_data)
        
        # Ordenar datos por hora (para consistencia)
        self.hourly_data = self.hourly_data.sort_values('hour').reset_index(drop=True)
        hours = self.hourly_data['hour'].values
        profits = self.hourly_data['profit'].values
        risks = self.hourly_data['max_drawdown'].values
        trades = self.hourly_data['trades'].values
        
        # Escalar valores para la programación dinámica
        max_possible_profit = int(profits.sum() * 100)  # Escalar a enteros
        scaled_profits = (profits * 100).astype(int)
        scaled_risks = (risks * 10).astype(int)  # Escalar riesgos
        
        # Capacidad de riesgo escalada
        capacity = int(risk_capacity * 10)
        
        # Inicializar tabla DP: [hora][riesgo_acumulado] = max_profit
        dp = np.zeros((n_hours + 1, capacity + 1), dtype=int)
        keep = np.zeros((n_hours + 1, capacity + 1), dtype=bool)
        
        # Llenar tabla DP
        for i in range(1, n_hours + 1):
            for w in range(capacity + 1):
                # No tomar la hora i-1
                dp[i][w] = dp[i-1][w]
                
                # Tomar la hora i-1 si cabe en la capacidad
                if scaled_risks[i-1] <= w:
                    value_with_hour = dp[i-1][w - scaled_risks[i-1]] + scaled_profits[i-1]
                    if value_with_hour > dp[i][w]:
                        dp[i][w] = value_with_hour
                        keep[i][w] = True
        
        # Reconstruir solución
        selected = []
        w = capacity
        for i in range(n_hours, 0, -1):
            if keep[i][w]:
                selected.append(i-1)
                w -= scaled_risks[i-1]
        
        selected_hours = hours[selected].tolist()
        
        # Calcular estadísticas de la selección
        selected_data = self.hourly_data[self.hourly_data['hour'].isin(selected_hours)]
        total_profit = selected_data['profit'].sum()
        total_risk = selected_data['max_drawdown'].max()
        total_trades = selected_data['trades'].sum()
        avg_win_rate = selected_data['win_rate'].mean()
        
        # Calcular estadísticas de horas excluidas
        excluded_data = self.hourly_data[~self.hourly_data['hour'].isin(selected_hours)]
        excluded_profit = excluded_data['profit'].sum()
        excluded_trades = excluded_data['trades'].sum()
        
        self.selected_hours = selected_hours
        
        results = {
            'selected_hours': selected_hours,
            'selected_hours_sorted': sorted(selected_hours),
            'total_profit': total_profit,
            'total_risk': total_risk,
            'total_trades': total_trades,
            'avg_win_rate': avg_win_rate,
            'excluded_hours': excluded_data['hour'].tolist(),
            'excluded_profit': excluded_profit,
            'excluded_trades': excluded_trades,
            'improvement': total_profit / (total_profit + abs(excluded_profit)) * 100 if excluded_profit < 0 else 100,
            'dp_table': dp,
            'n_hours_selected': len(selected_hours)
        }
        
        print(f"   ✅ Optimización completada: {len(selected_hours)} horas seleccionadas")
        print(f"   📈 Profit total: {total_profit:.2f}% | Riesgo máx: {total_risk:.2f}%")
        
        return results
    
    def greedy_selection(self, min_win_rate=70):
        """
        Algoritmo greedy: selecciona horas en orden descendente de rentabilidad
        hasta que el win_rate promedio caiga por debajo del umbral
        """
        print("\n🎯 Ejecutando optimización greedy...")
        
        # Ordenar por profit descendente
        sorted_data = self.hourly_data.sort_values('profit', ascending=False).reset_index(drop=True)
        
        selected = []
        cumulative_profit = 0
        cumulative_trades = 0
        weighted_win_rate = 0
        
        for idx, row in sorted_data.iterrows():
            # Calcular nuevo win_rate ponderado si añadimos esta hora
            new_trades = cumulative_trades + row['trades']
            if new_trades > 0:
                new_weighted_win_rate = (weighted_win_rate * cumulative_trades + row['win_rate'] * row['trades']) / new_trades
            else:
                new_weighted_win_rate = 0
            
            if new_weighted_win_rate >= min_win_rate:
                selected.append(row['hour'])
                cumulative_profit += row['profit']
                cumulative_trades = new_trades
                weighted_win_rate = new_weighted_win_rate
            else:
                break
        
        selected_hours = selected
        selected_data = self.hourly_data[self.hourly_data['hour'].isin(selected_hours)]
        
        results = {
            'selected_hours': selected_hours,
            'selected_hours_sorted': sorted(selected_hours),
            'total_profit': selected_data['profit'].sum() if len(selected_data) > 0 else 0,
            'total_risk': selected_data['max_drawdown'].max() if len(selected_data) > 0 else 0,
            'total_trades': selected_data['trades'].sum() if len(selected_data) > 0 else 0,
            'avg_win_rate': weighted_win_rate,
            'n_hours_selected': len(selected_hours)
        }
        
        print(f"   ✅ Greedy completado: {len(selected_hours)} horas seleccionadas")
        return results
    
    def markov_chain_analysis(self):
        """
        Análisis de cadena de Markov para transiciones entre horas
        Determina la probabilidad de que una hora buena siga a otra buena
        """
        print("\n🎯 Ejecutando análisis de cadena de Markov...")
        
        # Crear matriz de transición entre horas consecutivas
        transition_matrix = np.zeros((24, 24))
        count_matrix = np.zeros((24, 24))
        
        # Ordenar trades por tiempo
        df_sorted = self.df.sort_values('entry_time')
        
        for i in range(len(df_sorted) - 1):
            current_hour = df_sorted.iloc[i]['hour']
            next_hour = df_sorted.iloc[i+1]['hour']
            
            # Determinar si la operación actual fue rentable
            current_profitable = df_sorted.iloc[i]['profit_percent'] > 0
            
            # Solo considerar transiciones de horas rentables
            if current_profitable:
                count_matrix[current_hour, next_hour] += 1
        
        # Normalizar por fila
        row_sums = count_matrix.sum(axis=1, keepdims=True)
        # Evitar división por cero
        row_sums[row_sums == 0] = 1
        transition_matrix = count_matrix / row_sums
        
        # Calcular distribución estacionaria usando el método del eigenvector
        # pero con manejo de casos especiales
        try:
            eigenvalues, eigenvectors = np.linalg.eig(transition_matrix.T)
            # Encontrar eigenvector para eigenvalue = 1
            idx = np.argmin(np.abs(eigenvalues - 1))
            stationary = np.real(eigenvectors[:, idx])
            stationary = np.abs(stationary) / np.sum(np.abs(stationary))
        except:
            # Si falla, usar distribución uniforme sobre horas con datos
            stationary = np.ones(24) / 24
        
        # Identificar clusters de horas buenas
        good_hours = self.hourly_data[self.hourly_data['profit'] > 0]['hour'].tolist()
        
        return {
            'transition_matrix': transition_matrix,
            'stationary_distribution': stationary,
            'good_hours_clusters': good_hours
        }
    
    def generate_html_report(self, knapsack_results, greedy_results, markov_results):
        """Genera un informe profesional en HTML"""
        
        # Preparar datos para visualización
        all_hours_data = self.hourly_data.sort_values('hour')
        
        # Calcular mejora vs 24/7
        mejora_knapsack = ((knapsack_results['total_profit'] / self.df['profit_percent'].sum()) - 1) * 100
        
        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Optimizador de Horas - Análisis Matemático Profesional</title>
    <style>
        :root {{
            --primary: #2c3e50;
            --secondary: #3498db;
            --success: #27ae60;
            --warning: #f39c12;
            --danger: #e74c3c;
            --dark: #1a2634;
            --light: #f5f7fa;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: var(--primary);
            line-height: 1.6;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header h1 span {{
            font-weight: 300;
            display: block;
            font-size: 0.5em;
            margin-top: 10px;
            opacity: 0.9;
        }}
        
        .header .date {{
            margin-top: 20px;
            opacity: 0.8;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 40px;
            background: var(--light);
        }}
        
        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            text-align: center;
            transition: transform 0.3s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }}
        
        .stat-card .label {{
            color: #7f8c8d;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        
        .stat-card .value {{
            font-size: 2em;
            font-weight: 700;
            color: var(--primary);
        }}
        
        .stat-card .sub-value {{
            font-size: 0.9em;
            color: #7f8c8d;
            margin-top: 5px;
        }}
        
        .section {{
            padding: 40px;
            border-bottom: 1px solid #ecf0f1;
        }}
        
        .section-title {{
            font-size: 1.8em;
            color: var(--primary);
            margin-bottom: 30px;
            font-weight: 300;
            border-left: 5px solid var(--secondary);
            padding-left: 20px;
        }}
        
        .comparison-box {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }}
        
        .algorithm-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
        }}
        
        .algorithm-box h3 {{
            margin-bottom: 20px;
            font-size: 1.4em;
        }}
        
        .hour-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 8px 15px;
            border-radius: 30px;
            margin: 5px;
            font-weight: 600;
        }}
        
        .hour-badge.selected {{
            background: var(--success);
        }}
        
        .hour-badge.excluded {{
            background: var(--danger);
        }}
        
        .metric-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #ecf0f1;
        }}
        
        .metric-label {{
            color: #7f8c8d;
        }}
        
        .metric-value {{
            font-weight: 600;
            color: var(--primary);
        }}
        
        .metric-value.positive {{
            color: var(--success);
        }}
        
        .metric-value.negative {{
            color: var(--danger);
        }}
        
        .hour-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        
        .hour-table th {{
            background: var(--primary);
            color: white;
            padding: 12px;
            text-align: left;
        }}
        
        .hour-table td {{
            padding: 10px;
            border-bottom: 1px solid #ecf0f1;
        }}
        
        .hour-table tr:hover {{
            background: var(--light);
        }}
        
        .profit-positive {{
            color: var(--success);
            font-weight: 600;
        }}
        
        .profit-negative {{
            color: var(--danger);
            font-weight: 600;
        }}
        
        .footer {{
            background: var(--primary);
            color: white;
            text-align: center;
            padding: 30px;
            font-size: 0.9em;
        }}
        
        .recommendation {{
            background: #e8f5e9;
            padding: 25px;
            border-radius: 15px;
            margin-top: 30px;
        }}
        
        @media (max-width: 768px) {{
            .comparison-box {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>
                OPTIMIZADOR MATEMÁTICO DE HORAS
                <span>Algoritmo de la Mochila + Programación Dinámica + Cadenas de Markov</span>
            </h1>
            <div class="date">Generado el {datetime.now().strftime('%d de %B de %Y a las %H:%M')}</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total Operaciones</div>
                <div class="value">{len(self.df):,}</div>
                <div class="sub-value">Dataset completo</div>
            </div>
            <div class="stat-card">
                <div class="label">Profit Total</div>
                <div class="value">{self.df['profit_percent'].sum():.2f}%</div>
                <div class="sub-value">Operando 24/7</div>
            </div>
            <div class="stat-card">
                <div class="label">Horas Analizadas</div>
                <div class="value">{len(self.hourly_data)}</div>
                <div class="sub-value">de 24 posibles</div>
            </div>
            <div class="stat-card">
                <div class="label">Win Rate Global</div>
                <div class="value">{(len(self.df[self.df['result']=='WIN'])/len(self.df)*100):.1f}%</div>
                <div class="sub-value">{len(self.df[self.df['result']=='WIN'])}W / {len(self.df[self.df['result']=='LOSS'])}L</div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">📊 ANÁLISIS COMPARATIVO DE ALGORITMOS</h2>
            
            <div class="comparison-box">
                <div class="algorithm-box">
                    <h3>🎯 ALGORITMO DE LA MOCHILA (KNAPSACK)</h3>
                    <p style="margin-bottom: 20px;">Optimización con restricción de riesgo máximo {knapsack_results['total_risk']:.1f}%</p>
                    
                    <div style="margin-bottom: 20px;">
                        <strong>Horas SELECCIONADAS ({knapsack_results['n_hours_selected']}):</strong><br>
                        {''.join([f'<span class="hour-badge selected">{int(h):02d}:00</span>' for h in sorted(knapsack_results['selected_hours'])])}
                    </div>
                    
                    <div style="margin-bottom: 20px;">
                        <strong>Horas EXCLUIDAS ({24 - knapsack_results['n_hours_selected']}):</strong><br>
                        {''.join([f'<span class="hour-badge excluded">{h:02d}:00</span>' for h in range(24) if h not in knapsack_results['selected_hours']])}
                    </div>
                    
                    <div class="metric-row">
                        <span class="metric-label">Profit Total:</span>
                        <span class="metric-value positive">{knapsack_results['total_profit']:.2f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Riesgo Máximo:</span>
                        <span class="metric-value">{knapsack_results['total_risk']:.2f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Operaciones:</span>
                        <span class="metric-value">{knapsack_results['total_trades']}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Win Rate Promedio:</span>
                        <span class="metric-value">{knapsack_results['avg_win_rate']:.1f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Mejora vs 24/7:</span>
                        <span class="metric-value positive">+{mejora_knapsack:+.1f}%</span>
                    </div>
                </div>
                
                <div class="algorithm-box" style="background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);">
                    <h3>🔄 ALGORITMO GREEDY</h3>
                    <p style="margin-bottom: 20px;">Selección greedy con mínimo win rate {greedy_results['avg_win_rate']:.1f}%</p>
                    
                    <div style="margin-bottom: 20px;">
                        <strong>Horas SELECCIONADAS ({greedy_results['n_hours_selected']}):</strong><br>
                        {''.join([f'<span class="hour-badge selected">{int(h):02d}:00</span>' for h in sorted(greedy_results['selected_hours'])])}
                    </div>
                    
                    <div style="margin-bottom: 20px;">
                        <strong>Horas EXCLUIDAS ({24 - greedy_results['n_hours_selected']}):</strong><br>
                        {''.join([f'<span class="hour-badge excluded">{h:02d}:00</span>' for h in range(24) if h not in greedy_results['selected_hours']])}
                    </div>
                    
                    <div class="metric-row">
                        <span class="metric-label">Profit Total:</span>
                        <span class="metric-value positive">{greedy_results['total_profit']:.2f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Riesgo Máximo:</span>
                        <span class="metric-value">{greedy_results['total_risk']:.2f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Operaciones:</span>
                        <span class="metric-value">{greedy_results['total_trades']}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Win Rate Promedio:</span>
                        <span class="metric-value">{greedy_results['avg_win_rate']:.1f}%</span>
                    </div>
                </div>
            </div>
            
            <div class="recommendation">
                <h3 style="color: #2e7d32; margin-bottom: 15px;">📌 RECOMENDACIÓN FINAL (ENSEMBLE)</h3>
                <p style="margin-bottom: 15px;">Combinando ambos algoritmos, las horas que aparecen en AMBAS selecciones son las más robustas:</p>
                
                <div style="margin-bottom: 15px;">
                    <strong>✅ HORAS ROBUSTAS (en ambos algoritmos):</strong><br>
                    {''.join([f'<span class="hour-badge selected">{int(h):02d}:00</span>' for h in sorted(set(knapsack_results['selected_hours']) & set(greedy_results['selected_hours']))])}
                </div>
                
                <div style="margin-bottom: 15px;">
                    <strong>⚠️ HORAS CONFLICTIVAS (solo en un algoritmo):</strong><br>
                    {''.join([f'<span class="hour-badge" style="background: #f39c12;">{int(h):02d}:00</span>' for h in sorted(set(knapsack_results['selected_hours']) ^ set(greedy_results['selected_hours']))])}
                </div>
                
                <div>
                    <strong>❌ HORAS A EVITAR (en ninguno):</strong><br>
                    {''.join([f'<span class="hour-badge excluded">{h:02d}:00</span>' for h in range(24) if h not in set(knapsack_results['selected_hours']) | set(greedy_results['selected_hours'])])}
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">📈 ANÁLISIS DE CADENA DE MARKOV</h2>
            
            <p style="margin-bottom: 20px;">Probabilidades de transición entre horas rentables:</p>
            
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
                <tr>
                    <th style="background: var(--primary); color: white; padding: 10px;">Hora Actual</th>
                    <th style="background: var(--primary); color: white; padding: 10px;">Próxima Hora Más Probable</th>
                    <th style="background: var(--primary); color: white; padding: 10px;">Probabilidad</th>
                </tr>
                {''.join([f'''
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ecf0f1;">{h:02d}:00</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ecf0f1;">{np.argmax(markov_results['transition_matrix'][h]):02d}:00</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ecf0f1;">{markov_results['transition_matrix'][h].max()*100:.1f}%</td>
                </tr>
                ''' for h in range(0, 24, 3) if np.sum(markov_results['transition_matrix'][h]) > 0])}
            </table>
            
            <p><strong>Distribución estacionaria:</strong> Las horas con mayor probabilidad a largo plazo son:</p>
            <div style="margin-top: 10px;">
                {''.join([f'<span class="hour-badge selected">{int(h):02d}:00</span>' for h in np.argsort(markov_results['stationary_distribution'])[-5:]])}
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">📋 TABLA COMPLETA DE HORAS (ORDENADA POR RENTABILIDAD)</h2>
            
            <table class="hour-table">
                <thead>
                    <tr>
                        <th>Hora</th>
                        <th>Profit Total</th>
                        <th>Profit/Op</th>
                        <th>W/L</th>
                        <th>Win Rate</th>
                        <th>Riesgo</th>
                        <th>Sharpe</th>
                        <th>Knapsack</th>
                        <th>Greedy</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'''
                    <tr>
                        <td><strong>{int(row['hour']):02d}:00</strong></td>
                        <td class="{'profit-positive' if row['profit']>0 else 'profit-negative'}">{row['profit']:+.2f}%</td>
                        <td>{row['avg_profit']:+.3f}%</td>
                        <td>{int(row['wins'])}/{int(row['losses'])}</td>
                        <td>{row['win_rate']:.1f}%</td>
                        <td>{row['max_drawdown']:.2f}%</td>
                        <td>{row['sharpe']:.2f}</td>
                        <td style="text-align: center;">{'✅' if int(row['hour']) in knapsack_results['selected_hours'] else '❌'}</td>
                        <td style="text-align: center;">{'✅' if int(row['hour']) in greedy_results['selected_hours'] else '❌'}</td>
                    </tr>
                    ''' for _, row in self.hourly_data.sort_values('profit', ascending=False).iterrows()])}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>© 2025 Optimizador Matemático de Horas Trading</p>
            <p style="margin-top: 10px; opacity: 0.7;">Basado en programación dinámica, algoritmo de la mochila y cadenas de Markov</p>
        </div>
    </div>
</body>
</html>"""
        
        with open('optimizacion_matematica_horas.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print("   ✅ Reporte HTML generado: 'optimizacion_matematica_horas.html'")

# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    print("🔥"*80)
    print("OPTIMIZADOR MATEMÁTICO DE HORAS TRADING".center(80))
    print("Algoritmo de la Mochila + Programación Dinámica + Cadenas de Markov".center(80))
    print("🔥"*80)
    
    # Cargar datos
    try:
        df = pd.read_csv('trades_detalle.csv')
        df['entry_time'] = pd.to_datetime(df['entry_time'])
        df['hour'] = df['entry_time'].dt.hour
        df['profit_percent'] = pd.to_numeric(df['profit_percent'], errors='coerce')
        
        print(f"\n📂 Datos cargados: {len(df)} operaciones")
        print(f"   Período: {df['entry_time'].min().date()} a {df['entry_time'].max().date()}")
        
    except FileNotFoundError:
        print("❌ Error: No se encontró 'trades_detalle.csv'")
        exit()
    
    # Crear optimizador
    optimizer = KnapsackTimeOptimizer(df)
    
    # Preparar datos
    hourly_data = optimizer.prepare_hourly_data()
    
    # Ejecutar optimizaciones
    knapsack_results = optimizer.knapsack_optimization(risk_capacity=10, min_trades=50)
    greedy_results = optimizer.greedy_selection(min_win_rate=70)
    markov_results = optimizer.markov_chain_analysis()
    
    # Generar reporte
    optimizer.generate_html_report(knapsack_results, greedy_results, markov_results)
    
    print("\n" + "="*80)
    print("✅ ANÁLISIS COMPLETADO".center(80))
    print("="*80)
    print("\n📊 Reporte generado: optimizacion_matematica_horas.html")
    print("   Ábrelo en cualquier navegador para ver el análisis completo")