import pandas as pd
import numpy as np
from datetime import datetime

print("🔥 ANALIZADOR DE HORAS RENTABLES VS NO RENTABLES")
print("="*60)

# Cargar datos
try:
    df = pd.read_csv('trades_detalle.csv')
    print(f"📂 Cargadas {len(df)} operaciones")
except FileNotFoundError:
    print("❌ Error: No se encontró 'trades_detalle.csv'")
    exit()

# Procesar datos
df['entry_time'] = pd.to_datetime(df['entry_time'])
df['hour'] = df['entry_time'].dt.hour
df['profit_percent'] = pd.to_numeric(df['profit_percent'], errors='coerce')

# Analizar cada hora individualmente
print("\n" + "="*60)
print("📊 ANÁLISIS POR HORA INDIVIDUAL")
print("="*60)

resultados_horas = []

for hour in range(24):
    # Filtrar operaciones de esta hora
    hour_data = df[df['hour'] == hour]
    
    if len(hour_data) == 0:
        continue
    
    # Calcular métricas
    total_profit = hour_data['profit_percent'].sum()
    avg_profit = hour_data['profit_percent'].mean()
    wins = len(hour_data[hour_data['result'] == 'WIN'])
    losses = len(hour_data[hour_data['result'] == 'LOSS'])
    total = len(hour_data)
    winrate = (wins / total * 100) if total > 0 else 0
    
    # Determinar si es rentable
    if total_profit > 0:
        categoria = "✅ RENTABLE"
        color = "🟢"
    else:
        categoria = "❌ EVITAR"
        color = "🔴"
    
    resultados_horas.append({
        'hour': hour,
        'total_profit': total_profit,
        'avg_profit': avg_profit,
        'wins': wins,
        'losses': losses,
        'total': total,
        'winrate': winrate,
        'categoria': categoria,
        'color': color
    })

# Ordenar por rentabilidad (mejores primero)
resultados_horas.sort(key=lambda x: x['total_profit'], reverse=True)

# Mostrar resultados
print("\n🏆 TOP 5 HORAS MÁS RENTABLES:")
for i, r in enumerate(resultados_horas[:5]):
    print(f"   {i+1}. Hora {r['hour']:02d}:00 → {r['total_profit']:+.2f}% total ({r['wins']}W/{r['losses']}L, {r['winrate']:.1f}% WR)")

print("\n💀 TOP 5 HORAS MENOS RENTABLES (EVITAR):")
for i, r in enumerate(reversed(resultados_horas[-5:])):
    print(f"   {i+1}. Hora {r['hour']:02d}:00 → {r['total_profit']:+.2f}% total ({r['wins']}W/{r['losses']}L, {r['winrate']:.1f}% WR)")

# Mostrar tabla completa
print("\n" + "="*60)
print("📋 TABLA COMPLETA DE HORAS")
print("="*60)

print(f"{'Hora':<6} {'Profit':<10} {'Promedio':<10} {'W/L':<12} {'Winrate':<8} {'Categoría'}")
print("-"*70)

for r in resultados_horas:
    print(f"{r['hour']:02d}:00  {r['total_profit']:+7.2f}%   {r['avg_profit']:+6.2f}%   "
          f"{r['wins']}/{r['losses']:<5}   {r['winrate']:5.1f}%   {r['color']} {r['categoria']}")

# Resumen ejecutivo
print("\n" + "="*60)
print("📌 RECOMENDACIÓN FINAL")
print("="*60)

horas_rentables = [r for r in resultados_horas if r['total_profit'] > 0]
horas_evitar = [r for r in resultados_horas if r['total_profit'] <= 0]

print(f"\n✅ Horas RENTABLES ({len(horas_rentables)} horas):")
rentables_str = ', '.join([f"{r['hour']:02d}:00" for r in horas_rentables])
print(f"   {rentables_str}")

print(f"\n❌ Horas a EVITAR ({len(horas_evitar)} horas):")
evitar_str = ', '.join([f"{r['hour']:02d}:00" for r in horas_evitar])
print(f"   {evitar_str}")

if horas_rentables:
    mejor_hora = max(resultados_horas, key=lambda x: x['total_profit'])
    print(f"\n🏆 MEJOR HORA: {mejor_hora['hour']:02d}:00 con {mejor_hora['total_profit']:+.2f}% total")

if horas_evitar:
    peor_hora = min(resultados_horas, key=lambda x: x['total_profit'])
    print(f"💀 PEOR HORA: {peor_hora['hour']:02d}:00 con {peor_hora['total_profit']:+.2f}% total")

# Guardar resultados
df_resultados = pd.DataFrame(resultados_horas)
df_resultados.to_csv('analisis_horas.csv', index=False)
print("\n💾 Resultados guardados en 'analisis_horas.csv'")