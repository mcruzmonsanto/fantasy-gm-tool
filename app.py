import streamlit as st
import pandas as pd
import requests
import json  # <--- CRUCIAL PARA EL ARREGLO
from datetime import datetime
import sys
import os

# Importamos tu configuración existente
from src.conectar import obtener_liga
from config.credenciales import LIGAS

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Fantasy GM Pro",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .metric-card {background-color: #1E1E1E; padding: 15px; border-radius: 10px; border: 1px solid #333;}
    .big-font {font-size: 24px !important; font-weight: bold;}
    .stDataFrame {border: 1px solid #444;}
    .trend-fire {color: #FF4B4B; font-weight: bold;}
    .trend-up {color: #00FF00; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES AUXILIARES ---
def obtener_equipos_hoy():
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

def calcular_stats_manuales(lineup):
    totales = {'PTS':0, 'REB':0, 'AST':0, 'STL':0, 'BLK':0, '3PTM':0, 'TO':0, 'DD':0, 'FGM':0, 'FGA':0, 'FTM':0, 'FTA':0}
    for jugador in lineup:
        if jugador.slot_position in ['BE', 'IR']: continue 
        stats = {}
        if jugador.stats:
            for k, v in jugador.stats.items():
                if 'total' in v: stats = v['total']; break
        if not stats: continue
        
        totales['PTS'] += stats.get('PTS', 0)
        totales['REB'] += stats.get('REB', 0)
        totales['AST'] += stats.get('AST', 0)
        totales['STL'] += stats.get('STL', 0)
        totales['BLK'] += stats.get('BLK', 0)
        totales['TO'] += stats.get('TO', 0)
        totales['DD'] += stats.get('DD', 0)
        totales['3PTM'] += stats.get('3PM', stats.get('3PTM', 0))
        totales['FGM'] += stats.get('FGM', 0); totales['FGA'] += stats.get('FGA', 0)
        totales['FTM'] += stats.get('FTM', 0); totales['FTA'] += stats.get('FTA', 0)

    if totales['FGA'] > 0: totales['FG%'] = totales['FGM'] / totales['FGA']
    else: totales['FG%'] = 0.0
    if totales['FTA'] > 0: totales['FT%'] = totales['FTM'] / totales['FTA']
    else: totales['FT%'] = 0.0
    return totales

def obtener_datos_ownership(liga):
    """
    Función Parcheada (V2.2):
    Usa requests directo y json.dumps para asegurar que el header sea válido.
    """
    try:
        # 1. Construimos la URL
        year = liga.year
        league_id = liga.league_id
        url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{year}/segments/0/leagues/{league_id}"

        # 2. El Filtro (LA CLAVE: Usar json.dumps)
        # Pedimos jugadores libres/waivers, limitamos a 500 para velocidad
        filters = {
            "players": {
                "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
                "limit": 500,
                "sortPercOwned": {"sortPriority": 1, "sortAsc": False}
            }
        }
        
        headers = {
            'x-fantasy-filter': json.dumps(filters) # <--- AQUÍ ESTABA EL ERROR (necesita json string)
        }
        
        # 3. Parámetros
        params = {'view': 'kona_player_info'}
        
        # 4. Usamos las cookies que ya tiene la librería espn_api
        cookies = liga.espn_request.cookies

        # 5. Petición Manual Blindada
        r = requests.get(url, params=params, headers=headers, cookies=cookies)
        data = r.json()
        
        ownership_map = {}
        for p_data in data.get('players', []):
            pid = p_data.get('id')
            player_info = p_data.get('player', {})
            ownership = player_info.get('ownership', {})
            
            ownership_map[pid] = {
                'percentOwned': ownership.get('percentOwned', 0.0),
                'percentChange': ownership.get('percentChange', 0.0)
            }
        return ownership_map

    except Exception as e:
        print(f"Error ownership V2.2: {e}")
        return {}

# --- INTERFAZ PRINCIPAL ---

st.sidebar.header("⚙️ Centro de Mando")
nombre_liga = st.sidebar.selectbox("Selecciona tu Liga:", list(LIGAS.keys()))

if st.sidebar.button("🔄 Actualizar Datos"):
    st.cache_data.clear()

config = LIGAS[nombre_liga]
liga = obtener_liga(nombre_liga)
season_id = config['year']

st.title(f"🏀 GM Dashboard: {nombre_liga}")

if not liga:
    st.error("Error de conexión.")
    st.stop()

# ==========================================
# SECCIÓN 1: MATCHUP EN VIVO
# ==========================================
st.header("⚔️ Matchup Semanal")

box_scores = liga.box_scores()
mi_matchup = None
soy_home = False
PALABRA_CLAVE = "Max"

for m in box_scores:
    if PALABRA_CLAVE.lower() in m.home_team.team_name.lower(): mi_matchup = m; soy_home = True; break
    elif PALABRA_CLAVE.lower() in m.away_team.team_name.lower(): mi_matchup = m; soy_home = False; break

necesidades = []

if mi_matchup:
    mi_equipo_obj = mi_matchup.home_team if soy_home else mi_matchup.away_team
    rival = mi_matchup.away_team if soy_home else mi_matchup.home_team
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1: st.metric("Mi Equipo", mi_equipo_obj.team_name)
    with col2: st.markdown("<h2 style='text-align: center;'>VS</h2>", unsafe_allow_html=True)
    with col3: st.metric("Oponente", rival.team_name)

    mis_stats = calcular_stats_manuales(mi_matchup.home_lineup if soy_home else mi_matchup.away_lineup)
    rival_stats = calcular_stats_manuales(mi_matchup.away_lineup if soy_home else mi_matchup.home_lineup)
    
    cats_liga = config['categorias']
    data_tabla = []
    
    wins, losses, ties = 0, 0, 0

    for cat in cats_liga:
        key = '3PTM' if cat == '3PTM' and '3PTM' not in mis_stats else cat
        val_mio = mis_stats.get(key, 0)
        val_rival = rival_stats.get(key, 0)
        
        diff = val_mio - val_rival if cat != 'TO' else val_rival - val_mio
        
        estado = "🟡"
        if diff > 0: estado = "🟢"; wins+=1
        elif diff < 0: estado = "🔴"; losses+=1; necesidades.append(cat)
        else: ties+=1
        
        fmt_mio = f"{val_mio:.3f}" if cat in ['FG%','FT%'] else f"{val_mio:.0f}"
        fmt_rival = f"{val_rival:.3f}" if cat in ['FG%','FT%'] else f"{val_rival:.0f}"

        data_tabla.append([cat, fmt_mio, fmt_rival, f"{diff:.2f}", estado])

    st.markdown(f"### 🏆 Marcador: {wins} - {losses} - {ties}")
    df_matchup = pd.DataFrame(data_tabla, columns=['CAT', 'YO', 'RIVAL', 'DIFF', 'WIN?'])
    try:
        st.dataframe(df_matchup, use_container_width=True)
    except:
        st.dataframe(df_matchup)
    
    if necesidades:
        st.warning(f"🔥 PRIORIDAD DE FICHAJE: {', '.join(necesidades)}")
    else:
        st.success("🎉 ¡Vas ganando todo! Mantén la posición.")

else:
    st.warning("No se encontró matchup.")
    st.stop() 

# ==========================================
# SECCIÓN 2: EL VERDUGO (CORTES)
# ==========================================
st.markdown("---")
st.header("🪓 El Verdugo (Candidatos a Corte)")
st.caption("Ordenado de PEOR a MEJOR rendimiento promedio.")

if mi_equipo_obj:
    datos_roster = []
    for jugador in mi_equipo_obj.roster:
        stats = jugador.stats.get(f"{season_id}_total", {}).get('avg', {})
        if not stats: stats = jugador.stats.get(f"{season_id}_projected", {}).get('avg', {})
        
        score = stats.get('PTS', 0) + stats.get('REB', 0)*1.2 + stats.get('AST', 0)*1.5 + stats.get('STL', 0)*2 + stats.get('BLK', 0)*2
        if 'DD' in cats_liga: score += stats.get('DD', 0) * 5

        status_icon = "✅"
        if jugador.injuryStatus == 'OUT': status_icon = "⛔ OUT"
        elif jugador.injuryStatus == 'DAY_TO_DAY': status_icon = "⚠️ GTD"

        datos_roster.append({
            'Jugador': jugador.name,
            'Status': status_icon,
            'Pos': jugador.lineupSlot,
            'Score': round(score, 1),
            'Min': round(stats.get('MIN', 0), 1),
            'PTS': round(stats.get('PTS', 0), 1),
            'REB': round(stats.get('REB', 0), 1),
            'AST': round(stats.get('AST', 0), 1)
        })
    
    df_roster = pd.DataFrame(datos_roster)
    df_roster = df_roster.sort_values(by='Score', ascending=True)
    
    try:
        st.dataframe(df_roster, use_container_width=True)
    except:
        st.dataframe(df_roster)

    lesionados_activos = df_roster[ (df_roster['Status'] == '⛔ OUT') & (df_roster['Pos'] != 'IR') ]
    if not lesionados_activos.empty:
        st.error(f"🚨 JUGADORES 'OUT' EN ACTIVO: {', '.join(lesionados_activos['Jugador'].tolist())}")

# ==========================================
# SECCIÓN 3: WAIVER KING (CON HYPE FIX V2.2)
# ==========================================
st.markdown("---")
st.header("💎 Waiver King (Mercado + Hype)")
st.caption("Busca jugadores que jueguen hoy y que el mundo esté fichando.")

col_filtro1, col_filtro2 = st.columns(2)
with col_filtro1:
    min_minutos = st.slider("Minutos Mínimos", 10, 40, 22)
with col_filtro2:
    solo_hoy = st.checkbox("Solo juegan HOY", value=True)

if st.button("🔎 Buscar Joyas"):
    with st.spinner('Analizando Mercado, Calendario y Tendencias...'):
        equipos_hoy = obtener_equipos_hoy() if solo_hoy else []
        
        if solo_hoy:
            if equipos_hoy: st.info(f"Equipos hoy: {len(equipos_hoy)}")
            else: st.warning("No hay partidos hoy (o error API).")

        # LLAMADA CORREGIDA PARA OBTENER OWNERSHIP
        ownership_map = obtener_datos_ownership(liga)

        free_agents = liga.free_agents(size=250)
        waiver_data = []
        
        for p in free_agents:
            acq = getattr(p, 'acquisitionType', [])
            if len(acq) > 0: continue 
            if p.injuryStatus == 'OUT': continue
            if solo_hoy and equipos_hoy and p.proTeam not in equipos_hoy: continue
            
            stats = p.stats.get(f"{season_id}_total", {}).get('avg', {})
            if not stats: stats = p.stats.get(f"{season_id}_projected", {}).get('avg', {})
            if not stats: continue
            
            mpg = stats.get('MIN', 0)
            if mpg < min_minutos: continue
            
            # CRUCE DE DATOS HYPE
            # Buscamos por ID. Si no está en el mapa, es 0.0
            p_data = ownership_map.get(p.playerId, {})
            own_pct = p_data.get('percentOwned', 0.0)
            own_chg = p_data.get('percentChange', 0.0)
            
            trend_icon = ""
            if own_chg > 4.0: trend_icon = "🔥🔥" 
            elif own_chg > 1.5: trend_icon = "🔥" 
            elif own_chg > 0.1: trend_icon = "📈" 
            elif own_chg < -1.0: trend_icon = "❄️"
            
            trend_txt = f"{trend_icon} {own_chg:+.1f}%"

            score = mpg * 0.5
            match_cats = []
            
            if necesidades:
                for cat in necesidades:
                    val = stats.get(cat, 0)
                    if val > 0:
                        score += val * 10 
                        match_cats.append(cat)
            else:
                score += stats.get('PTS', 0) + stats.get('REB', 0) + stats.get('AST', 0)
            
            if own_chg > 2.0: score += 15
            elif own_chg > 0.5: score += 5

            waiver_data.append({
                'Nombre': p.name,
                'Equipo': p.proTeam,
                'Trend': trend_txt,     
                'Own%': f"{own_pct:.1f}%", 
                'Min': round(mpg, 1),
                'Score': round(score, 1),
                'Ayuda en': ", ".join(match_cats) if match_cats else "General"
            })
            
        if waiver_data:
            df_waiver = pd.DataFrame(waiver_data)
            df_waiver = df_waiver.sort_values(by='Score', ascending=False).head(20)
            try:
                st.dataframe(df_waiver, use_container_width=True)
            except:
                st.dataframe(df_waiver)
        else:
            st.error("No se encontraron jugadores.")

st.markdown("---")
st.caption("🚀 Fantasy GM Architect v2.2 | JSON Header Fix")