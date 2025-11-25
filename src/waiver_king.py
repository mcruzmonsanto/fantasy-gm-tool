import pandas as pd
import sys
import os
import requests
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.conectar import obtener_liga
from src.matchup_analyzer import analizar_necesidades
from config.credenciales import LIGAS

# --- CONFIGURACIÓN DE ESTRATEGIA ---
CANTIDAD_A_ANALIZAR = 250      # Escaneamos profundo
FILTRAR_POR_CALENDARIO = True  # True = Solo muestra jugadores que juegan HOY
MIN_MINUTOS_PROMEDIO = 22.0    # Mínimo de minutos para considerar (Volumen)

def obtener_equipos_jugando_hoy():
    """ Consulta API pública NBA para el calendario de hoy """
    hoy_str = datetime.now().strftime("%Y%m%d")
    url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={hoy_str}"
    equipos = []
    try:
        data = requests.get(url).json()
        for event in data.get('events', []):
            for comp in event.get('competitions', []):
                for competitor in comp.get('competitors', []):
                    abrev = competitor.get('team', {}).get('abbreviation')
                    if abrev: equipos.append(abrev)
    except: pass
    return equipos

def waiver_tactico(nombre_liga):
    necesidades = analizar_necesidades(nombre_liga)
    if necesidades is None: necesidades = []

    liga = obtener_liga(nombre_liga)
    season_id = LIGAS[nombre_liga]['year']
    
    # --- PREPARACIÓN DE FILTROS ---
    equipos_hoy = []
    if FILTRAR_POR_CALENDARIO:
        print("📡 Consultando calendario en tiempo real...")
        equipos_hoy = obtener_equipos_jugando_hoy()
        if equipos_hoy:
            print(f"📅 Filtro Activo: {len(equipos_hoy)} equipos juegan hoy.")
        else:
            print("⚠️ No se detectaron partidos hoy (o error de API). Mostrando todo.")

    print(f"\n💎 BÚSQUEDA DE ELITE: {nombre_liga}")
    print(f"   Requisitos: Free Agent (Sin Waiver) | Minutos > {MIN_MINUTOS_PROMEDIO}")

    # --- MINERÍA DE DATOS ---
    free_agents = liga.free_agents(size=CANTIDAD_A_ANALIZAR)
    datos = []

    for jugador in free_agents:
        # 1. FILTRO DE ACQUISITION (EL MÁS IMPORTANTE)
        # Si la lista no está vacía (ej: ['WAIVERS']), lo saltamos.
        # Solo queremos [] (Agente Libre Puro)
        acq_type = getattr(jugador, 'acquisitionType', [])
        if len(acq_type) > 0:
            continue

        # 2. FILTRO DE SALUD
        if jugador.injuryStatus == 'OUT': continue
        
        # 3. FILTRO DE CALENDARIO
        if equipos_hoy and jugador.proTeam not in equipos_hoy:
            continue

        # 4. EXTRACCIÓN DE STATS
        # Buscamos stats reales (total) o proyectadas
        stats = jugador.stats.get(f"{season_id}_total", {}).get('avg', {})
        if not stats: 
            stats = jugador.stats.get(f"{season_id}_projected", {}).get('avg', {})
        if not stats: continue

        # 5. FILTRO DE MINUTOS (Volumen)
        mpg = stats.get('MIN', 0)
        if mpg < MIN_MINUTOS_PROMEDIO: continue

        # --- ALGORITMO DE PUNTUACIÓN (SCORING) ---
        score_tactico = (mpg * 0.5) # Base por minutos jugados

        if not necesidades:
            # Score General (Best Player Available)
            score_tactico += stats.get('PTS', 0) + stats.get('REB', 0)*1.2 + stats.get('AST', 0)*1.5 + stats.get('STL', 0)*2 + stats.get('BLK', 0)*2
        else:
            # Score Especialista (Need-based)
            for cat in necesidades:
                valor = stats.get(cat, 0)
                if valor == 0: continue

                # Pesos agresivos para lo que necesitamos
                if cat in ['BLK', 'STL']: score_tactico += valor * 30
                elif cat in ['REB', 'AST']: score_tactico += valor * 6
                elif cat == '3PTM': score_tactico += valor * 8
                elif cat == 'DD': score_tactico += valor * 20
                elif cat == 'PTS': score_tactico += valor * 0.8
                
                # Porcentajes (Premio a la eficiencia)
                if cat == 'FG%' and valor >= 0.50: score_tactico += 25
                if cat == 'FT%' and valor >= 0.85: score_tactico += 25

        if score_tactico < 10: continue 

        # Formateo de la posición para que no ocupe mucho espacio
        pos = getattr(jugador, 'position', 'F/G')
        
        fila = {
            'JUGADOR': jugador.name,
            'EQUIPO': jugador.proTeam,
            'POS': pos,
            'MIN': round(mpg, 1),
            'SCORE': round(score_tactico, 1)
        }
        
        # Agregamos visualmente las stats clave
        if necesidades:
            stats_str = []
            for cat in necesidades:
                val = stats.get(cat, 0)
                if val > 0:
                    txt = f"{round(val*100,0)}%" if cat in ['FG%','FT%'] else str(round(val,1))
                    stats_str.append(f"{cat}:{txt}")
            fila['APORTE'] = " | ".join(stats_str)
        else:
            fila['APORTE'] = f"PTS:{round(stats.get('PTS',0),1)} REB:{round(stats.get('REB',0),1)}"

        datos.append(fila)

    # --- VISUALIZACIÓN FINAL ---
    if datos:
        df = pd.DataFrame(datos)
        df = df.sort_values(by='SCORE', ascending=False).head(12)
        
        print(f"\n🚀 RECOMENDACIONES DE FICHAJE (Hoy + {int(MIN_MINUTOS_PROMEDIO)}m + Free Agent):")
        print(df.to_string(index=False))
        print("-" * 80)
    else:
        print(f"❌ No hay jugadores 'Agente Libre' (sin waiver) que jueguen hoy >{MIN_MINUTOS_PROMEDIO} mins.")
        print("   -> Intenta bajar el filtro MIN_MINUTOS_PROMEDIO en el script.")

if __name__ == "__main__":
    for liga in LIGAS:
        waiver_tactico(liga)