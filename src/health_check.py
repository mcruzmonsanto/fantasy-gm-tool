import pandas as pd
import sys
import os

# Ajuste de rutas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.conectar import obtener_liga
from config.credenciales import LIGAS

# CONFIGURACIÓN
PALABRA_CLAVE_EQUIPO = "Max"

def analizar_plantilla(nombre_liga):
    liga = obtener_liga(nombre_liga)
    if not liga: return

    # 1. Buscar tu equipo
    mi_equipo = None
    for team in liga.teams:
        if PALABRA_CLAVE_EQUIPO.lower() in team.team_name.lower():
            mi_equipo = team
            break
            
    if not mi_equipo:
        print(f"❌ No encontré el equipo '{PALABRA_CLAVE_EQUIPO}' en {nombre_liga}")
        return

    print(f"\n🏥 AUDITORÍA: {mi_equipo.team_name} | Liga: {nombre_liga}")
    
    # Configuración de año
    season_id = LIGAS[nombre_liga]['year']
    categorias_objetivo = LIGAS[nombre_liga]['categorias']

    datos_roster = []

    # 2. Analizar cada jugador de TU plantilla
    for jugador in mi_equipo.roster:
        # Status de salud
        status = jugador.injuryStatus
        if status == 'NORMAL': status = '✅' # Sano
        elif status == 'DAY_TO_DAY': status = '⚠️ GTD'
        elif status == 'OUT': status = '⛔ OUT'
        
        # Stats
        key_total = f"{season_id}_total"
        key_projected = f"{season_id}_projected"
        
        stats = jugador.stats.get(key_total, {}).get('avg', {})
        if not stats:
            stats = jugador.stats.get(key_projected, {}).get('avg', {})
            tipo_dato = "(Proj)"
        else:
            tipo_dato = ""

        fila = {
            'JUGADOR': jugador.name,
            'POS': jugador.lineupSlot, # Slot donde lo tienes (G, F, Bench, IR)
            'STATUS': status,
            'TIPO': tipo_dato
        }

        # Agregamos stats principales para decidir a quién cortar
        # Usamos PTS y otra stat clave como referencia rápida
        fila['PTS'] = round(stats.get('PTS', 0), 1)
        
        # Si la liga tiene DD (Doble Doble), lo mostramos, si no, Rebotes
        if 'DD' in categorias_objetivo:
            fila['DD'] = round(stats.get('DD', 0), 1)
        else:
            fila['REB'] = round(stats.get('REB', 0), 1)

        # Criterio de "Corte": Suma simple de fantasía (aprox) para ordenar
        # Esto es solo para ordenar la tabla, no es una métrica oficial
        score_corte = stats.get('PTS', 0) + stats.get('REB', 0) + stats.get('AST', 0)*1.5
        fila['_SCORE'] = score_corte 

        datos_roster.append(fila)

    # 3. Visualización Táctica
    if datos_roster:
        df = pd.DataFrame(datos_roster)
        
        # Ordenamos: Los PEORES arriba (para ver a quién cortar rápido)
        df = df.sort_values(by='_SCORE', ascending=True)
        
        # Ocultamos la columna auxiliar de score
        columnas_visibles = [c for c in df.columns if not c.startswith('_')]
        
        print(f"🔪 CANDIDATOS A CORTE (Ordenados de Menor a Mayor Rendimiento):")
        print(df[columnas_visibles].to_string(index=False))
        print("-" * 60)
        
        # ALERTA DE LESIONADOS EN ACTIVO
        # Si tienes un 'OUT' en una posición titular (no IR, no BE), es GRAVE.
        lesionados_activos = df[ (df['STATUS'] == '⛔ OUT') & (df['POS'] != 'IR') ]
        if not lesionados_activos.empty:
            print("🚨 ¡ALERTA ROJA! TIENES JUGADORES 'OUT' EN TU ALINEACIÓN:")
            for _, row in lesionados_activos.iterrows():
                print(f"   -> Mueve a {row['JUGADOR']} a IR inmediatamente.")
    else:
        print("Tu roster parece vacío...")

if __name__ == "__main__":
    print("🚑 GESTOR DE PLANTILLA Y CORTES 🚑")
    for nombre in LIGAS:
        analizar_plantilla(nombre)