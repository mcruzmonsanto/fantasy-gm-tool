import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import sys
import os

# Importamos tu configuración
from src.conectar import obtener_liga
from config.credenciales import LIGAS

# --- CONFIGURACIÓN PÁGINA ---
st.set_page_config(
    page_title="Fantasy GM Pro",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS ---
st.markdown("""
<style>
    .metric-card {background-color: #1E1E1E; padding: 15px; border-radius: 10px; border: 1px solid #333;}
    .stDataFrame {border: 1px solid #444;}
    /* Colores para diferencias */
    .diff-pos {color: #00FF00; font-weight: bold;}
    .diff-neg {color: #FF4B4B; font-weight: bold;}
    .diff-neu {color: #888888;}
</style>
""", unsafe_allow_html=True)

# --- DICCIONARIO TRADUCTOR (ROSTER -> CALENDARIO) ---
MAPEO_EQUIPOS = {
    'WSH': 'WAS',
    'UTAH': 'UTA',
    'NO': 'NOP',
    'NY': 'NYK',
    'SA': 'SAS',
    'PHO': 'PHX',
    'GS': 'GSW'
}

def normalizar_equipo(abrev):
    """Convierte abreviaturas raras de ESPN a estándar NBA"""
    return MAPEO_EQUIPOS.get(abrev, abrev)

# --- CACHÉ DE CALENDARIO ---
@st.cache_data(ttl=3600) 
def obtener_calendario_semanal_nba():
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    calendario_semanal = {}
    
    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        dia_str = dia.strftime("%Y%m%d")
        dia_fmt = dia.strftime("%a %d")
        
        url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={dia_str}"
        equipos_dia = []
        try:
            data = requests.get(url).json()
            for event in data.get('events', []):
                for comp in event.get('competitions', []):
                    for competitor in comp.get('competitors', []):
                        abrev = competitor.get('team', {}).get('abbreviation')
                        if abrev: equipos_dia.append(abrev)
        except: pass
        calendario_semanal[dia_fmt] = equipos_dia
    return calendario_semanal

def obtener_equipos_hoy_simple():
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

def obtener_datos_ownership(liga):
    try:
        year = liga.year
        league_id = liga.league_id
        url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{year}/segments/0/leagues/{league_id}"
        filters = {"players": {"filterStatus": {"value": ["FREEAGENT", "WAIVERS"]}, "limit": 500, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
        headers = {'x-fantasy-filter': json.dumps(filters)}
        params = {'view': 'kona_player_info'}
        cookies = liga.espn_request.cookies
        r = requests.get(url, params=params, headers=headers, cookies=cookies)
        data = r.json()
        own_map = {}
        for p in data.get('players', []):
            pid = p.get('id')
            own = p.get('player', {}).get('ownership', {})
            own_map[pid] = {'percentOwned': own.get('percentOwned', 0.0), 'percentChange': own.get('percentChange', 0.0)}
        return own_map
    except: return {}

def calcular_stats_manuales(lineup):
    totales = {'PTS':0, 'REB':0, 'AST':0, 'STL':0, 'BLK':0, '3PTM':0, 'TO':0, 'DD':0, 'FGM':0, 'FGA':0, 'FTM':0, 'FTA':0}
    for jugador in lineup:
        if jugador.slot_position in ['BE', 'IR']: continue 
        stats = {}
        if jugador.stats:
            for k, v in jugador.stats.items():
                if 'total' in v: stats = v['total']; break
        if not stats: continue
        totales['PTS'] += stats.get('PTS', 0); totales['REB'] += stats.get('REB', 0); totales['AST'] += stats.get('AST', 0)
        totales['STL'] += stats.get('STL', 0); totales['BLK'] += stats.get('BLK', 0); totales['TO'] += stats.get('TO', 0)
        totales['DD'] += stats.get('DD', 0); totales['3PTM'] += stats.get('3PM', stats.get('3PTM', 0))
        totales['FGM'] += stats.get('FGM', 0); totales['FGA'] += stats.get('FGA', 0)
        totales['FTM'] += stats.get('FTM', 0); totales['FTA'] += stats.get('FTA', 0)
    if totales['FGA'] > 0: totales['FG%'] = totales['FGM'] / totales['FGA']
    if totales['FTA'] > 0: totales['FT%'] = totales['FTM'] / totales['FTA']
    return totales

# --- INTERFAZ ---

st.sidebar.header("⚙️ Centro de Mando")
nombre_liga = st.sidebar.selectbox("Selecciona tu Liga:", list(LIGAS.keys()))

# CONTROL MANUAL DE SLOTS
st.sidebar.markdown("---")
limit_slots = st.sidebar.number_input("⚔️ Slots Activos (Titulares)", min_value=5, max_value=20, value=10)

if st.sidebar.button("🔄 Actualizar Datos"):
    st.cache_data.clear()

config = LIGAS[nombre_liga]
liga = obtener_liga(nombre_liga)
season_id = config['year']

st.title(f"🏀 GM Dashboard: {nombre_liga}")

if not liga:
    st.error("Error de conexión.")
    st.stop()

box_scores = liga.box_scores()
mi_matchup = None
soy_home = False
PALABRA_CLAVE = "Max"

for m in box_scores:
    if PALABRA_CLAVE.lower() in m.home_team.team_name.lower(): mi_matchup = m; soy_home = True; break
    elif PALABRA_CLAVE.lower() in m.away_team.team_name.lower(): mi_matchup = m; soy_home = False; break

# ==========================================
# 1. THE WEEKLY GRID (CON TRADUCTOR)
# ==========================================
st.header(f"📅 Planificación Semanal (Límite: {limit_slots} jug.)")

if mi_matchup:
    with st.spinner("Calculando Matrix..."):
        calendario = obtener_calendario_semanal_nba()
        
        mi_equipo_obj = mi_matchup.home_team if soy_home else mi_matchup.away_team
        rival_obj = mi_matchup.away_team if soy_home else mi_matchup.home_team
        
        fila_yo = ["YO"]
        fila_rival = ["RIVAL"]
        fila_diff = ["DIFF"]
        
        total_yo_real = 0
        total_rival_real = 0
        
        dias_semana = list(calendario.keys())

        for dia in dias_semana:
            equipos_juegan = calendario[dia]
            
            # 1. Contamos JUGADORES DISPONIBLES (Sin IR)
            disponibles_yo = 0
            for p in mi_equipo_obj.roster:
                # TRADUCCIÓN CRÍTICA DE NOMBRE DE EQUIPO
                team_abbrev = normalizar_equipo(p.proTeam)
                
                if p.injuryStatus != 'OUT' and team_abbrev in equipos_juegan and p.lineupSlot != 'IR':
                    disponibles_yo += 1
            
            disponibles_rival = 0
            for p in rival_obj.roster:
                team_abbrev = normalizar_equipo(p.proTeam)
                if p.injuryStatus != 'OUT' and team_abbrev in equipos_juegan and p.lineupSlot != 'IR':
                    disponibles_rival += 1
            
            # 2. Aplicamos el CAP
            usados_yo = min(disponibles_yo, limit_slots)
            usados_rival = min(disponibles_rival, limit_slots)
            
            txt_yo = f"{usados_yo}"
            if disponibles_yo > limit_slots: txt_yo = f"{usados_yo} (de {disponibles_yo})"
            
            txt_rival = f"{usados_rival}"
            if disponibles_rival > limit_slots: txt_rival = f"{usados_rival} (de {disponibles_rival})"

            fila_yo.append(txt_yo)
            fila_rival.append(txt_rival)
            
            diff = usados_yo - usados_rival
            simbolo = "✅" if diff > 0 else "⚠️" if diff < 0 else "="
            fila_diff.append(f"{diff} {simbolo}")
            
            total_yo_real += usados_yo
            total_rival_real += usados_rival

        fila_yo.append(total_yo_real)
        fila_rival.append(total_rival_real)
        
        diff_total = total_yo_real - total_rival_real
        simbolo_tot = "🔥" if diff_total > 0 else "💀" if diff_total < 0 else "="
        fila_diff.append(f"{diff_total} {simbolo_tot}")
        
        cols = ["EQUIPO"] + dias_semana + ["TOTAL"]
        df_grid = pd.DataFrame([fila_yo, fila_rival, fila_diff], columns=cols)
        st.dataframe(df_grid, use_container_width=True)
        
        if diff_total < 0:
            st.error(f"⚠️ ALERTA DE VOLUMEN: Proyectas jugar {abs(diff_total)} partidos MENOS.")

# ==========================================
# 2. MATCHUP & 3. VERDUGO & 4. WAIVER
# ==========================================
st.markdown("---")
col_main1, col_main2 = st.columns([1, 1])

necesidades = []

with col_main1:
    st.subheader("⚔️ Matchup Actual")
    if mi_matchup:
        mis_stats = calcular_stats_manuales(mi_matchup.home_lineup if soy_home else mi_matchup.away_lineup)
        rival_stats = calcular_stats_manuales(mi_matchup.away_lineup if soy_home else mi_matchup.home_lineup)
        cats_liga = config['categorias']
        data_tabla = []
        wins=0; losses=0; ties=0
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
        st.markdown(f"**Marcador: {wins}-{losses}-{ties}**")
        if necesidades: st.caption(f"Necesitas: {', '.join(necesidades)}")
        df_m = pd.DataFrame(data_tabla, columns=['CAT','YO','RIV','DIF','W'])
        st.dataframe(df_m, use_container_width=True, height=300)

with col_main2:
    st.subheader("🪓 El Verdugo")
    if mi_matchup:
        datos_roster = []
        for p in mi_equipo_obj.roster:
            stats = p.stats.get(f"{season_id}_total", {}).get('avg', {})
            if not stats: stats = p.stats.get(f"{season_id}_projected", {}).get('avg', {})
            score = stats.get('PTS',0) + stats.get('REB',0)*1.2 + stats.get('AST',0)*1.5 + stats.get('STL',0)*2 + stats.get('BLK',0)*2
            if 'DD' in cats_liga: score += stats.get('DD', 0) * 5
            icon = "⛔" if p.injuryStatus == 'OUT' else "⚠️" if p.injuryStatus == 'DAY_TO_DAY' else "✅"
            datos_roster.append({'J': p.name, 'St': icon, 'Pos': p.lineupSlot, 'Scr': round(score,1), 'Min': round(stats.get('MIN',0),1)})
        df_r = pd.DataFrame(datos_roster).sort_values(by='Scr', ascending=True)
        st.dataframe(df_r, use_container_width=True, height=300)
        lesionados_activos = df_roster[ (df_roster['Status'] == '⛔ OUT') & (df_roster['Pos'] != 'IR') ]
        if not lesionados_activos.empty: st.error(f"🚨 SACAR JUGADORES 'OUT': {', '.join(lesionados_activos['Jugador'].tolist())}")

st.markdown("---")
st.header("💎 Waiver King (Hype + Needs)")
c1, c2 = st.columns(2)
with c1: min_minutos = st.slider("Minutos Mínimos", 10, 40, 22)
with c2: solo_hoy = st.checkbox("Solo juegan HOY", value=True)

if st.button("🔎 Buscar Joyas"):
    with st.spinner('Escaneando...'):
        equipos_hoy = obtener_equipos_hoy_simple() if solo_hoy else []
        ownership_map = obtener_datos_ownership(liga)
        free_agents = liga.free_agents(size=200)
        waiver_data = []
        for p in free_agents:
            acq = getattr(p, 'acquisitionType', [])
            if len(acq) > 0: continue 
            if p.injuryStatus == 'OUT': continue
            
            # APLICAMOS TRADUCTOR TAMBIEN EN WAIVER POR SI ACASO
            team_abbrev = normalizar_equipo(p.proTeam)
            if solo_hoy and equipos_hoy and team_abbrev not in equipos_hoy: continue
            
            stats = p.stats.get(f"{season_id}_total", {}).get('avg', {})
            if not stats: stats = p.stats.get(f"{season_id}_projected", {}).get('avg', {})
            if not stats: continue
            mpg = stats.get('MIN', 0)
            if mpg < min_minutos: continue
            p_data = ownership_map.get(p.playerId, {})
            own_chg = p_data.get('percentChange', 0.0)
            own_pct = p_data.get('percentOwned', 0.0)
            trend_icon = "🔥🔥" if own_chg > 2.0 else "🔥" if own_chg > 0.5 else "📈" if own_chg > 0.0 else "❄️"
            trend_txt = f"{trend_icon} {own_chg:+.1f}%"
            score = mpg * 0.5
            match_cats = []
            if necesidades:
                for cat in necesidades:
                    val = stats.get(cat, 0)
                    if val > 0: score += val * 10; match_cats.append(cat)
            else: score += stats.get('PTS', 0) + stats.get('REB', 0) + stats.get('AST', 0)
            if own_chg > 1.5: score += 15
            elif own_chg > 0.5: score += 8
            waiver_data.append({
                'Nombre': p.name, 'Eq': p.proTeam, 'Trend': trend_txt, 'Own%': f"{own_pct:.1f}%",
                'Min': round(mpg,1), 'Score': round(score,1), 'Ayuda': ", ".join(match_cats) if match_cats else "Gral"
            })
        if waiver_data:
            df_w = pd.DataFrame(waiver_data).sort_values(by='Score', ascending=False).head(20)
            try: st.dataframe(df_w, use_container_width=True)
            except: st.dataframe(df_w)
        else: st.error("Sin resultados.")

st.caption("🚀 Fantasy GM Architect v3.3 | Team Name Fix")