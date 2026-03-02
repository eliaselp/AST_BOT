import pandas as pd
import numpy as np
import itertools
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

class TradingTimeOptimizer:
    """
    Optimizador Avanzado de Rangos Horarios
    Prueba TODAS las combinaciones posibles de rangos de cualquier tamaño
    """
    
    def __init__(self, config=None):
        """
        Configuración del optimizador
        """
        self.config = {
            'min_trades_per_range': 3,        # Mínimo de operaciones para considerar un rango
            'max_drawdown_limit': 20,          # Drawdown máximo aceptable (%)
            'min_win_rate': 35,                 # Win rate mínimo aceptable (%)
            'max_ranges_in_combo': 5,           # Máximo número de rangos en una combinación
            'profit_weight': 0.35,               # Peso del profit total
            'monthly_profit_weight': 0.35,       # Peso del profit mensual
            'drawdown_weight': 0.30,             # Peso del drawdown (negativo)
            'consistency_weight': 0.15,           # Peso adicional para consistencia
        }
        
        if config:
            self.config.update(config)
            
        self.load_data()
        self.all_possible_ranges = []
        self.all_combinations_results = []
        
    def load_data(self):
        """Carga y prepara los datos"""
        print("📂 Cargando datos...")
        try:
            self.df = pd.read_csv('trades_detalle.csv')
            print(f"   ✅ {len(self.df)} operaciones cargadas")
        except FileNotFoundError:
            print("❌ Error: No se encontró 'trades_detalle.csv'")
            # Datos de ejemplo para pruebas
            self.create_sample_data()
            
        # Procesar datos
        self.df['entry_time'] = pd.to_datetime(self.df['entry_time'])
        self.df['hour'] = self.df['entry_time'].dt.hour
        self.df['profit_percent'] = pd.to_numeric(self.df['profit_percent'], errors='coerce')
        self.df['month'] = pd.to_datetime(self.df['month']).dt.strftime('%Y-%m')
        
        # Estadísticas generales
        self.total_profit_historico = self.df['profit_percent'].sum()
        self.total_trades = len(self.df)
        self.unique_months = self.df['month'].nunique()
        self.months_list = sorted(self.df['month'].unique())
        
        print(f"   📊 Período: {self.df['entry_time'].min().date()} a {self.df['entry_time'].max().date()}")
        print(f"   📊 Profit histórico: {self.total_profit_historico:.2f}%")
        
    def create_sample_data(self):
        """Crea datos de ejemplo para pruebas"""
        print("   ⚠️  Usando datos de ejemplo para demostración")
        np.random.seed(42)
        
        dates = pd.date_range('2025-01-01', '2025-03-31', freq='H')
        data = []
        
        for date in dates[:2000]:  # Limitar a 2000 operaciones
            hour = date.hour
            
            # Simular diferentes rendimientos por hora
            if 2 <= hour <= 5 or 14 <= hour <= 17:
                profit = np.random.normal(0.35, 0.4)
                result = 'WIN' if profit > 0 else 'LOSS'
            elif 8 <= hour <= 11 or 20 <= hour <= 23:
                profit = np.random.normal(0.15, 0.5)
                result = 'WIN' if profit > 0 else 'LOSS'
            else:
                profit = np.random.normal(-0.1, 0.6)
                result = 'WIN' if profit > 0 else 'LOSS'
            
            data.append({
                'entry_time': date,
                'type': np.random.choice(['LONG', 'SHORT']),
                'entry_price': 1.0371 + np.random.normal(0, 0.001),
                'sl': 1.0362,
                'tp': 1.03755,
                'result': result,
                'exit_time': date + pd.Timedelta(hours=1),
                'exit_price': 1.03755,
                'pips': np.random.normal(4.5, 2),
                'profit_percent': profit,
                'h4_trend_alcista': np.random.choice([True, False]),
                'h4_trend_bajista': np.random.choice([True, False]),
                'volume_ratio': np.random.uniform(0.8, 1.5),
                'month': date.strftime('%Y-%m')
            })
        
        self.df = pd.DataFrame(data)
        print(f"   ✅ {len(self.df)} operaciones de ejemplo creadas")
    
    def generate_all_possible_ranges(self):
        """Genera TODOS los rangos horarios posibles de cualquier tamaño"""
        print("\n🔍 Generando todos los rangos horarios posibles...")
        
        # Todos los posibles puntos de inicio y duración
        for start in range(24):
            for duration in range(1, 13):  # Rangos de 1 a 12 horas
                end = (start + duration) % 24
                
                # Calcular horas en el rango
                if start <= end:
                    hours_in_range = list(range(start, end))
                else:
                    hours_in_range = list(range(start, 24)) + list(range(0, end))
                
                # Verificar si hay suficientes datos
                if start <= end:
                    mask = (self.df['hour'] >= start) & (self.df['hour'] < end)
                else:
                    mask = (self.df['hour'] >= start) | (self.df['hour'] < end)
                
                range_data = self.df[mask]
                
                if len(range_data) >= self.config['min_trades_per_range']:
                    self.all_possible_ranges.append({
                        'start': start,
                        'end': end,
                        'duration': duration,
                        'hours': hours_in_range,
                        'range_name': f"{start:02d}:00-{end:02d}:00",
                        'trades_count': len(range_data),
                        'data': range_data
                    })
        
        print(f"   ✅ {len(self.all_possible_ranges)} rangos válidos generados")
        return self.all_possible_ranges
    
    def calculate_range_metrics(self, range_data):
        """Calcula todas las métricas para un conjunto de datos"""
        if len(range_data) == 0:
            return None
            
        total_profit = range_data['profit_percent'].sum()
        
        # Profit mensual promedio
        months_in_range = range_data['month'].nunique()
        monthly_profit = total_profit / months_in_range if months_in_range > 0 else 0
        
        # Win rate
        wins = range_data[range_data['result'] == 'WIN']
        win_rate = (len(wins) / len(range_data)) * 100
        
        # Profit factor
        loss_sum = abs(range_data[range_data['result'] == 'LOSS']['profit_percent'].sum())
        win_sum = wins['profit_percent'].sum() if len(wins) > 0 else 0
        profit_factor = win_sum / loss_sum if loss_sum != 0 else float('inf')
        
        # Drawdown máximo
        cumulative = range_data['profit_percent'].cumsum()
        running_max = cumulative.expanding().max()
        drawdown = cumulative - running_max
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0
        
        # Sharpe ratio
        returns_std = range_data['profit_percent'].std() if len(range_data) > 1 else 1
        sharpe = (range_data['profit_percent'].mean() / returns_std) * np.sqrt(252) if returns_std != 0 else 0
        
        # Consistencia mensual (coeficiente de variación inverso)
        monthly_profits = []
        for month in range_data['month'].unique():
            month_data = range_data[range_data['month'] == month]
            monthly_profits.append(month_data['profit_percent'].sum())
        
        monthly_std = np.std(monthly_profits) if len(monthly_profits) > 1 else 1
        monthly_mean = np.mean(monthly_profits) if monthly_profits else 1
        consistency = monthly_mean / (monthly_std + 0.001) if monthly_std > 0 else 10
        
        return {
            'total_profit': total_profit,
            'monthly_profit': monthly_profit,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'consistency': consistency,
            'trades_count': len(range_data),
            'months_count': months_in_range
        }
    
    def evaluate_combination(self, ranges):
        """Evalúa una combinación de rangos"""
        # Combinar datos de todos los rangos
        combined_data = pd.concat([r['data'] for r in ranges])
        combined_data = combined_data.drop_duplicates(subset=['entry_time'])
        
        if len(combined_data) == 0:
            return None
            
        # Calcular métricas de la combinación
        metrics = self.calculate_range_metrics(combined_data)
        
        if metrics is None:
            return None
            
        # Calcular score compuesto
        profit_score = metrics['total_profit'] / 100
        monthly_score = metrics['monthly_profit'] / 10
        drawdown_penalty = metrics['max_drawdown'] / self.config['max_drawdown_limit']
        consistency_score = metrics['consistency'] / 10
        
        composite_score = (
            self.config['profit_weight'] * profit_score +
            self.config['monthly_profit_weight'] * monthly_score -
            self.config['drawdown_weight'] * drawdown_penalty +
            self.config['consistency_weight'] * consistency_score
        )
        
        # Verificar criterios mínimos
        meets_criteria = (
            metrics['win_rate'] >= self.config['min_win_rate'] and
            metrics['max_drawdown'] <= self.config['max_drawdown_limit']
        )
        
        return {
            'ranges': [r['range_name'] for r in ranges],
            'range_objects': ranges,
            'metrics': metrics,
            'composite_score': composite_score,
            'meets_criteria': meets_criteria,
            'total_trades': len(combined_data),
            'total_ranges': len(ranges)
        }
    
    def find_optimal_combinations(self):
        """Encuentra las mejores combinaciones de rangos"""
        print("\n🎯 Buscando combinaciones óptimas de rangos...")
        
        # Generar todos los rangos posibles
        ranges = self.generate_all_possible_ranges()
        
        # Evaluar combinaciones de 1 a N rangos
        best_combinations = []
        
        for n_ranges in range(1, self.config['max_ranges_in_combo'] + 1):
            print(f"   Evaluando combinaciones de {n_ranges} rango(s)...")
            
            # Para eficiencia, primero evaluamos rangos individuales prometedores
            if n_ranges == 1:
                for r in ranges:
                    result = self.evaluate_combination([r])
                    if result:
                        best_combinations.append(result)
            else:
                # Seleccionar los mejores rangos individuales para combinaciones
                top_ranges = sorted(best_combinations, 
                                  key=lambda x: x['composite_score'], 
                                  reverse=True)[:20]
                
                top_range_objects = [item['range_objects'][0] for item in top_ranges]
                
                # Probar combinaciones de los mejores rangos
                for combo in itertools.combinations(top_range_objects, n_ranges):
                    result = self.evaluate_combination(list(combo))
                    if result and result['meets_criteria']:
                        best_combinations.append(result)
        
        # Ordenar por score compuesto
        best_combinations.sort(key=lambda x: x['composite_score'], reverse=True)
        
        print(f"   ✅ {len(best_combinations)} combinaciones válidas encontradas")
        return best_combinations[:50]  # Top 50 combinaciones
    
    def generate_html_report(self, best_combinations):
        """Genera un reporte HTML profesional"""
        print("\n📝 Generando reporte HTML...")
        
        top_combinations = best_combinations[:10]  # Top 10 para el reporte
        
        # Preparar datos para visualizaciones
        range_names = [combo['ranges'] for combo in top_combinations]
        profits = [combo['metrics']['total_profit'] for combo in top_combinations]
        monthly_profits = [combo['metrics']['monthly_profit'] for combo in top_combinations]
        drawdowns = [combo['metrics']['max_drawdown'] for combo in top_combinations]
        win_rates = [combo['metrics']['win_rate'] for combo in top_combinations]
        scores = [combo['composite_score'] for combo in top_combinations]
        
        # Identificar la mejor combinación
        best_combo = best_combinations[0]
        best_ranges = best_combo['ranges']
        best_metrics = best_combo['metrics']
        
        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Optimizador de Rangos Horarios - Reporte Profesional</title>
    <style>
        :root {{
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --success-color: #27ae60;
            --warning-color: #f39c12;
            --danger-color: #e74c3c;
            --dark-bg: #1a2634;
            --light-bg: #f5f7fa;
            --card-bg: #ffffff;
            --text-primary: #2c3e50;
            --text-secondary: #7f8c8d;
            --border-color: #ecf0f1;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
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
            font-weight: 300;
        }}
        
        .header h1 span {{
            font-weight: 700;
            display: block;
            font-size: 1.2em;
            margin-top: 10px;
        }}
        
        .header .date {{
            opacity: 0.9;
            font-size: 0.9em;
            margin-top: 20px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 40px;
            background: var(--light-bg);
        }}
        
        .stat-card {{
            background: var(--card-bg);
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
            color: var(--text-secondary);
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        
        .stat-card .value {{
            font-size: 2em;
            font-weight: 700;
            color: var(--primary-color);
        }}
        
        .stat-card .sub-value {{
            font-size: 0.9em;
            color: var(--text-secondary);
            margin-top: 5px;
        }}
        
        .badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .badge-success {{
            background: var(--success-color);
            color: white;
        }}
        
        .badge-warning {{
            background: var(--warning-color);
            color: white;
        }}
        
        .badge-danger {{
            background: var(--danger-color);
            color: white;
        }}
        
        .section {{
            padding: 40px;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .section-title {{
            font-size: 1.8em;
            color: var(--primary-color);
            margin-bottom: 30px;
            font-weight: 300;
            border-left: 5px solid var(--secondary-color);
            padding-left: 20px;
        }}
        
        .recommendation-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
        }}
        
        .time-ranges-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }}
        
        .time-range-card {{
            background: var(--card-bg);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            border: 2px solid transparent;
            transition: all 0.3s;
        }}
        
        .time-range-card.optimal {{
            border-color: var(--success-color);
            background: linear-gradient(to bottom right, #ffffff, #f0fff4);
        }}
        
        .time-range-card .range-title {{
            font-size: 1.4em;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 15px;
        }}
        
        .time-range-card .metric-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px dashed var(--border-color);
        }}
        
        .time-range-card .metric-label {{
            color: var(--text-secondary);
        }}
        
        .time-range-card .metric-value {{
            font-weight: 600;
            color: var(--primary-color);
        }}
        
        .time-range-card .positive {{
            color: var(--success-color);
        }}
        
        .time-range-card .negative {{
            color: var(--danger-color);
        }}
        
        .comparison-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 30px;
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
        }}
        
        .comparison-table th {{
            background: var(--primary-color);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        
        .comparison-table td {{
            padding: 15px;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .comparison-table tr:hover {{
            background: var(--light-bg);
        }}
        
        .comparison-table .rank-1 {{
            background: rgba(39, 174, 96, 0.1);
            font-weight: 600;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 10px;
            background: var(--border-color);
            border-radius: 5px;
            overflow: hidden;
            margin-top: 5px;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--secondary-color), var(--success-color));
            border-radius: 5px;
        }}
        
        .hour-grid {{
            display: grid;
            grid-template-columns: repeat(24, 1fr);
            gap: 2px;
            margin: 20px 0;
        }}
        
        .hour-cell {{
            aspect-ratio: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7em;
            font-weight: 600;
            color: white;
            border-radius: 3px;
        }}
        
        .footer {{
            background: var(--primary-color);
            color: white;
            text-align: center;
            padding: 30px;
            font-size: 0.9em;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8em;
            }}
            
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .section {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>
                OPTIMIZADOR DE RANGOS HORARIOS
                <span>Análisis Avanzado para Maximizar Profit y Minimizar Drawdown</span>
            </h1>
            <div class="date">Generado el {datetime.now().strftime('%d de %B de %Y a las %H:%M')}</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total Operaciones</div>
                <div class="value">{self.total_trades:,}</div>
                <div class="sub-value">Período analizado</div>
            </div>
            <div class="stat-card">
                <div class="label">Meses Analizados</div>
                <div class="value">{self.unique_months}</div>
                <div class="sub-value">{', '.join(self.months_list[:3])}{'...' if len(self.months_list)>3 else ''}</div>
            </div>
            <div class="stat-card">
                <div class="label">Profit Histórico</div>
                <div class="value">{self.total_profit_historico:.2f}%</div>
                <div class="sub-value">Operando 24/7</div>
            </div>
            <div class="stat-card">
                <div class="label">Rangos Evaluados</div>
                <div class="value">{len(self.all_possible_ranges):,}</div>
                <div class="sub-value">Combinaciones: {len(best_combinations):,}</div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">🎯 RECOMENDACIÓN ÓPTIMA</h2>
            
            <div class="recommendation-box">
                <h3 style="margin-bottom: 20px;">Configuración de Máximo Rendimiento</h3>
                <p style="font-size: 1.2em; margin-bottom: 30px;">
                    Basado en el análisis de {len(best_combinations):,} combinaciones posibles, 
                    esta configuración maximiza el profit general y mensual mientras minimiza el drawdown:
                </p>
                
                <div style="background: rgba(255,255,255,0.2); border-radius: 15px; padding: 25px;">
                    <h4 style="margin-bottom: 15px;">📋 RANGOS PERMITIDOS:</h4>
                    <div style="display: flex; flex-wrap: wrap; gap: 15px;">
                        {''.join([f'<span style="background: rgba(255,255,255,0.3); padding: 10px 20px; border-radius: 30px; font-weight: 600;">{r}</span>' for r in best_ranges])}
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-top: 30px;">
                        <div>
                            <div style="opacity: 0.9; margin-bottom: 5px;">Profit Total Proyectado</div>
                            <div style="font-size: 2.5em; font-weight: 700;">{best_metrics['total_profit']:.2f}%</div>
                            <div class="progress-bar" style="background: rgba(255,255,255,0.3);">
                                <div class="progress-fill" style="width: {min(100, best_metrics['total_profit'])}%; background: white;"></div>
                            </div>
                        </div>
                        <div>
                            <div style="opacity: 0.9; margin-bottom: 5px;">Profit Mensual Promedio</div>
                            <div style="font-size: 2.5em; font-weight: 700;">{best_metrics['monthly_profit']:.2f}%</div>
                        </div>
                        <div>
                            <div style="opacity: 0.9; margin-bottom: 5px;">Max Drawdown</div>
                            <div style="font-size: 2.5em; font-weight: 700;">{best_metrics['max_drawdown']:.2f}%</div>
                        </div>
                        <div>
                            <div style="opacity: 0.9; margin-bottom: 5px;">Win Rate</div>
                            <div style="font-size: 2.5em; font-weight: 700;">{best_metrics['win_rate']:.1f}%</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-top: 30px;">
                <div style="background: #e8f5e9; padding: 25px; border-radius: 15px;">
                    <h4 style="color: #2e7d32; margin-bottom: 15px;">✅ MEJORA VS OPERAR SIEMPRE</h4>
                    <div style="font-size: 1.3em; margin-bottom: 10px;">
                        Profit: <strong>{((best_metrics['total_profit']/self.total_profit_historico - 1)*100):+.1f}%</strong>
                    </div>
                    <div style="font-size: 1.3em;">
                        Drawdown: <strong>{((best_metrics['max_drawdown']/self.max_drawdown_historico - 1)*100):+.1f}%</strong>
                    </div>
                </div>
                
                <div style="background: #fff3e0; padding: 25px; border-radius: 15px;">
                    <h4 style="color: #ef6c00; margin-bottom: 15px;">⏰ DISTRIBUCIÓN HORARIA</h4>
                    <div class="hour-grid">
                        {self.generate_hour_grid_html(best_combo['range_objects'])}
                    </div>
                    <p style="margin-top: 15px; font-size: 0.9em; color: #666;">
                        Horas en verde: permitidas | Horas en gris: evitar
                    </p>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">📊 TOP 10 CONFIGURACIONES ÓPTIMAS</h2>
            
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>Ranking</th>
                        <th>Rangos Horarios</th>
                        <th>Profit Total</th>
                        <th>Profit Mensual</th>
                        <th>Max Drawdown</th>
                        <th>Win Rate</th>
                        <th>Score</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'''
                    <tr class="rank-{i+1}">
                        <td><strong>#{i+1}</strong></td>
                        <td>{', '.join(combo['ranges'])}</td>
                        <td style="color: #27ae60; font-weight: 600;">{combo['metrics']['total_profit']:.2f}%</td>
                        <td style="color: #27ae60; font-weight: 600;">{combo['metrics']['monthly_profit']:.2f}%</td>
                        <td style="color: #e74c3c; font-weight: 600;">{combo['metrics']['max_drawdown']:.2f}%</td>
                        <td>{combo['metrics']['win_rate']:.1f}%</td>
                        <td style="font-weight: 600;">{combo['composite_score']:.3f}</td>
                    </tr>
                    ''' for i, combo in enumerate(top_combinations)])}
                </tbody>
            </table>
        </div>
        
        <div class="section">
            <h2 class="section-title">📈 ANÁLISIS DETALLADO POR RANGO</h2>
            
            <div class="time-ranges-grid">
                {self.generate_range_cards_html(best_combo['range_objects'])}
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">📅 PROYECCIÓN MENSUAL</h2>
            
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>Mes</th>
                        <th>Profit Proyectado</th>
                        <th>Operaciones</th>
                        <th>vs Mes Anterior</th>
                    </tr>
                </thead>
                <tbody>
                    {self.generate_monthly_projection_html(best_combo)}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>© 2025 Trading Time Optimizer - Análisis Profesional para Maximizar Rendimiento</p>
            <p style="margin-top: 10px; opacity: 0.7;">Este reporte es generado algorítmicamente basado en datos históricos. El rendimiento pasado no garantiza resultados futuros.</p>
        </div>
    </div>
</body>
</html>"""
        
        # Guardar el archivo
        with open('reporte_optimizacion_horaria.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print("   ✅ Reporte HTML generado: 'reporte_optimizacion_horaria.html'")
    
    def generate_hour_grid_html(self, range_objects):
        """Genera visualización de la cuadrícula horaria"""
        allowed_hours = set()
        for r in range_objects:
            allowed_hours.update(r['hours'])
        
        cells = []
        for hour in range(24):
            if hour in allowed_hours:
                color = '#27ae60'
            else:
                color = '#95a5a6'
            
            cells.append(f'<div class="hour-cell" style="background: {color};">{hour:02d}</div>')
        
        return ''.join(cells)
    
    def generate_range_cards_html(self, range_objects):
        """Genera tarjetas para cada rango"""
        cards = []
        for i, r in enumerate(range_objects):
            metrics = self.calculate_range_metrics(r['data'])
            if metrics:
                cards.append(f'''
                <div class="time-range-card {'optimal' if i == 0 else ''}">
                    <div class="range-title">📊 {r['range_name']}</div>
                    <div class="metric-row">
                        <span class="metric-label">Duración:</span>
                        <span class="metric-value">{r['duration']} horas</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Horas:</span>
                        <span class="metric-value">{', '.join([f'{h:02d}' for h in r['hours']])}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Profit Total:</span>
                        <span class="metric-value positive">{metrics['total_profit']:.2f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Profit Mensual:</span>
                        <span class="metric-value positive">{metrics['monthly_profit']:.2f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Max Drawdown:</span>
                        <span class="metric-value negative">{metrics['max_drawdown']:.2f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Win Rate:</span>
                        <span class="metric-value">{metrics['win_rate']:.1f}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Operaciones:</span>
                        <span class="metric-value">{metrics['trades_count']}</span>
                    </div>
                </div>
                ''')
        return ''.join(cards)
    
    def generate_monthly_projection_html(self, best_combo):
        """Genera proyección mensual"""
        rows = []
        cumulative = 0
        
        for i, month in enumerate(self.months_list):
            month_data = self.df[self.df['month'] == month]
            
            # Filtrar por rangos óptimos
            filtered_data = pd.concat([r['data'][r['data']['month'] == month] for r in best_combo['range_objects']])
            filtered_data = filtered_data.drop_duplicates(subset=['entry_time'])
            
            month_profit = filtered_data['profit_percent'].sum() if len(filtered_data) > 0 else 0
            cumulative += month_profit
            
            prev_profit = 0
            if i > 0:
                prev_data = pd.concat([r['data'][r['data']['month'] == self.months_list[i-1]] for r in best_combo['range_objects']])
                prev_data = prev_data.drop_duplicates(subset=['entry_time'])
                prev_profit = prev_data['profit_percent'].sum() if len(prev_data) > 0 else 0
            
            change = ((month_profit / prev_profit) - 1) * 100 if prev_profit != 0 else 0
            change_class = 'positive' if change > 0 else 'negative'
            change_symbol = '▲' if change > 0 else '▼'
            
            rows.append(f'''
            <tr>
                <td><strong>{month}</strong></td>
                <td style="color: #27ae60; font-weight: 600;">{month_profit:.2f}%</td>
                <td>{len(filtered_data)}</td>
                <td style="color: {change_class};">
                    {change_symbol} {abs(change):.1f}%
                </td>
            </tr>
            ''')
        
        return ''.join(rows)
    
    def run(self):
        """Ejecuta el análisis completo"""
        print("\n" + "="*80)
        print(" TRADING TIME OPTIMIZER - ANÁLISIS AVANZADO ".center(80, "🔥"))
        print("="*80)
        
        # Encontrar mejores combinaciones
        best_combinations = self.find_optimal_combinations()
        
        if not best_combinations:
            print("❌ No se encontraron combinaciones válidas")
            return
        
        # Mostrar top resultados en consola
        print("\n" + "-"*80)
        print("🏆 TOP 5 CONFIGURACIONES ÓPTIMAS")
        print("-"*80)
        
        for i, combo in enumerate(best_combinations[:5]):
            print(f"\n  #{i+1} - Score: {combo['composite_score']:.3f}")
            print(f"     Rangos: {', '.join(combo['ranges'])}")
            print(f"     Profit Total: {combo['metrics']['total_profit']:.2f}% | "
                  f"Mensual: {combo['metrics']['monthly_profit']:.2f}% | "
                  f"DD: {combo['metrics']['max_drawdown']:.2f}%")
        
        # Generar reporte HTML
        self.generate_html_report(best_combinations)
        
        print("\n" + "="*80)
        print(" ANÁLISIS COMPLETADO ".center(80, "✅"))
        print("="*80)
        print("\n📊 Reporte HTML generado: reporte_optimizacion_horaria.html")
        print("   Ábrelo en cualquier navegador para ver el análisis completo")
        
        # Guardar también en CSV
        results_df = pd.DataFrame([{
            'ranking': i+1,
            'ranges': ', '.join(combo['ranges']),
            'total_profit': combo['metrics']['total_profit'],
            'monthly_profit': combo['metrics']['monthly_profit'],
            'max_drawdown': combo['metrics']['max_drawdown'],
            'win_rate': combo['metrics']['win_rate'],
            'profit_factor': combo['metrics']['profit_factor'],
            'sharpe_ratio': combo['metrics']['sharpe_ratio'],
            'trades': combo['metrics']['trades_count'],
            'score': combo['composite_score']
        } for i, combo in enumerate(best_combinations[:20])])
        
        results_df.to_csv('resultados_optimizacion.csv', index=False)
        print("📊 Resultados guardados en: resultados_optimizacion.csv")
        
        return best_combinations

# ============================================================================
# EJECUCIÓN PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    print("🔥"*80)
    print("OPTIMIZADOR AVANZADO DE RANGOS HORARIOS".center(80))
    print("Buscando la combinación perfecta para maximizar profit y minimizar drawdown".center(80))
    print("🔥"*80)
    
    # Configuración personalizable
    config = {
        'min_trades_per_range': 1,      # Mínimo de operaciones por rango
        'max_drawdown_limit': 3,        # Drawdown máximo aceptable (%)
        'min_win_rate': 80,               # Win rate mínimo (%)
        'max_ranges_in_combo': 10,         # Máximo número de rangos a combinar
        
        'profit_weight': 0.35,             # Peso del profit total
        'monthly_profit_weight': 0.35,     # Peso del profit mensual
        'drawdown_weight': 0.30,           # Peso del drawdown (minimizar)
    }
    
    # Crear optimizador y ejecutar
    optimizer = TradingTimeOptimizer(config)
    best_combinations = optimizer.run()
    
    print("\n" + "💡"*80)
    print("INSTRUCCIONES".center(80))
    print("💡"*80)
    print("\n1. Abre el archivo 'reporte_optimizacion_horaria.html' en tu navegador")
    print("2. Revisa la sección 'RECOMENDACIÓN ÓPTIMA' para ver los horarios sugeridos")
    print("3. La tabla 'TOP 10 CONFIGURACIONES' muestra alternativas igualmente válidas")
    print("4. Las tarjetas detalladas muestran el rendimiento de cada rango individual")
    print("\n✅ ANÁLISIS COMPLETADO - Revisa el reporte HTML para resultados detallados")