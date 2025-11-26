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
    .diff-pos {color: #00FF00; font-weight: bold;}
    .diff-neg {color: #FF4B4B; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# --- DICCIONARIO TRADUCTOR ---
MAPEO_EQUIPOS = {
    'WSH': 'WAS', 'UTAH': 'UTA', 'NO': 'NOP', 'NY': 'NYK', 'SA': 'SAS', 'PHO': 'PHX', 'GS': 'GSW'
}

def normalizar_equipo(abrev):
    return MAPEO_EQUIPOS.get(abrev, abrev)

# --- FUNCIONES ---
@st.cache_data(ttl=3600) 
def obtener_calendario_semanal_nba():
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    calendario_semanal = {}
    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        dia_str = dia.strftime("%Y%m%d"); dia_fmt = dia.strftime("%a %d")
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
        year = liga.year; league_id = liga.league_id
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
    for p in lineup:
        if p.slot_position in ['BE', 'IR']: continue 
        stats = {}
        if p.stats:
            for k, v in p.stats.items():
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
st.sidebar.markdown("---")
limit_slots = st.sidebar.number_input("⚔️ Slots Activos (Titulares)", min_value=5, max_value=20, value=10)

if st.sidebar.button("🔄 Actualizar Datos"): st.cache_data.clear()

config = LIGAS[nombre_liga]
liga = obtener_liga(nombre_liga)
season_id = config['year']

st.title(f"🏀 GM Dashboard: {nombre_liga}")
if not liga: st.error("Error de conexión."); st.stop()

box_scores = liga.box_scores()
mi_matchup = None; soy_home = False; PALABRA_CLAVE = "Max"
for m in box_scores:
    if PALABRA_CLAVE.lower() in m.home_team.team_name.lower(): mi_matchup = m; soy_home = True; break
    elif PALABRA_CLAVE.lower() in m.away_team.team_name.lower(): mi_matchup = m; soy_home = False; break

# 1. GRID SEMANAL
st.header(f"📅 Planificación Semanal (Límite: {limit_slots})")
if mi_matchup:
    with st.spinner("Analizando Calendario..."):
        calendario = obtener_calendario_semanal_nba()
        mi_equipo_obj = mi_matchup.home_team if soy_home else mi_matchup.away_team
        rival_obj = mi_matchup.away_team if soy_home else mi_matchup.home_team
        
        fila_yo = ["YO"]; fila_rival = ["RIVAL"]; fila_diff = ["DIFF"]
        total_yo = 0; total_rival = 0
        
        for dia in calendario:
            equipos_juegan = calendario[dia]
            
            disp_yo = 0
            for p in mi_equipo_obj.roster:
                if p.injuryStatus != 'OUT' and normalizar_equipo(p.proTeam) in equipos_juegan and p.lineupSlot != 'IR': disp_yo += 1
            
            disp_riv = 0
            for p in rival_obj.roster:
                if p.injuryStatus != 'OUT' and normalizar_equipo(p.proTeam) in equipos_juegan and p.lineupSlot != 'IR': disp_riv += 1
            
            usados_yo = min(disp_yo, limit_slots)
            usados_riv = min(disp_riv, limit_slots)
            
            txt_yo = f"{usados_yo}" if disp_yo <= limit_slots else f"{usados_yo} ({disp_yo})"
            txt_riv = f"{usados_riv}" if disp_riv <= limit_slots else f"{usados_riv} ({disp_riv})"
            
            fila_yo.append(txt_yo); fila_rival.append(txt_riv)
            diff = usados_yo - usados_riv
            simbolo = "✅" if diff > 0 else "⚠️" if diff < 0 else "="
            fila_diff.append(f"{diff} {simbolo}")
            
            total_yo += usados_yo; total_rival += usados_riv

        fila_yo.append(total_yo); fila_rival.append(total_rival)
        diff_tot = total_yo - total_rival
        fila_diff.append(f"{diff_tot} {'🔥' if diff_tot > 0 else '💀' if diff_tot < 0 else '='}")
        
        df_grid = pd.DataFrame([fila_yo, fila_rival, fila_diff], columns=["EQUIPO"] + list(calendario.keys()) + ["TOTAL"])
        st.dataframe(df_grid, use_container_width=True)
        if diff_tot < 0: st.error(f"⚠️ ALERTA: Proyectas {abs(diff_tot)} partidos MENOS que el rival.")

st.markdown("---")
c1, c2 = st.columns([1, 1])
necesidades = []

# 2. MATCHUP
with c1:
    st.subheader("⚔️ Matchup")
    if mi_matchup:
        mis_stats = calcular_stats_manuales(mi_matchup.home_lineup if soy_home else mi_matchup.away_lineup)
        rival_stats = calcular_stats_manuales(mi_matchup.away_lineup if soy_home else mi_matchup.home_lineup)
        data_t = []
        w=0; l=0; t=0
        for cat in config['categorias']:
            key = '3PTM' if cat == '3PTM' and '3PTM' not in mis_stats else cat
            vm = mis_stats.get(key, 0); vr = rival_stats.get(key, 0)
            diff = vm - vr if cat != 'TO' else vr - vm
            st_icon = "🟡"
            if diff > 0: st_icon = "🟢"; w+=1
            elif diff < 0: st_icon = "🔴"; l+=1; necesidades.append(cat)
            else: t+=1
            fmt_m = f"{vm:.3f}" if cat in ['FG%','FT%'] else f"{vm:.0f}"
            fmt_r = f"{vr:.3f}" if cat in ['FG%','FT%'] else f"{vr:.0f}"
            data_t.append([cat, fmt_m, fmt_r, f"{diff:.2f}", st_icon])
        
        st.markdown(f"**{w}-{l}-{t}**"); 
        if necesidades: st.caption(f"Necesitas: {', '.join(necesidades)}")
        st.dataframe(pd.DataFrame(data_t, columns=['CAT','YO','RIV','DIF','W']), use_container_width=True, height=300)

# 3. VERDUGO
with c2:
    st.subheader("🪓 El Verdugo")
    if mi_matchup:
        data_r = []
        for p in mi_equipo_obj.roster:
            stats = p.stats.get(f"{season_id}_total", {}).get('avg', {})
            if not stats: stats = p.stats.get(f"{season_id}_projected", {}).get('avg', {})
            sc = stats.get('PTS',0) + stats.get('REB',0)*1.2 + stats.get('AST',0)*1.5 + stats.get('STL',0)*2 + stats.get('BLK',0)*2
            if 'DD' in config['categorias']: sc += stats.get('DD', 0) * 5
            icon = "⛔" if p.injuryStatus == 'OUT' else "⚠️" if p.injuryStatus == 'DAY_TO_DAY' else "✅"
            data_r.append({'J': p.name, 'St': icon, 'Pos': p.lineupSlot, 'Scr': round(sc,1), 'Min': round(stats.get('MIN',0),1)})
        
        df_r = pd.DataFrame(data_r).sort_values(by='Scr', ascending=True)
        st.dataframe(df_r, use_container_width=True, height=300) # <-- AQUI ESTABA EL ERROR, CORREGIDO
        
        les_act = df_r[ (df_r['St'] == '⛔') & (df_r['Pos'] != 'IR') ]
        if not les_act.empty: st.error(f"🚨 JUGADORES OUT ACTIVOS: {', '.join(les_act['J'].tolist())}")

# 4. WAIVER KING
st.markdown("---")
st.header("💎 Waiver King")
fc1, fc2 = st.columns(2)
with fc1: min_m = st.slider("Minutos Mínimos", 10, 40, 22)
with fc2: s_hoy = st.checkbox("Solo juegan HOY", value=True)

if st.button("🔎 Buscar Joyas"):
    with st.spinner('Escaneando...'):
        eq_hoy = obtener_equipos_hoy_simple() if s_hoy else []
        own_map = obtener_datos_ownership(liga)
        fa = liga.free_agents(size=200)
        w_data = []
        
        for p in fa:
            if getattr(p, 'acquisitionType', []) or p.injuryStatus == 'OUT': continue
            
            # TRADUCTOR EN WAIVER
            tm = normalizar_equipo(p.proTeam)
            if s_hoy and eq_hoy and tm not in eq_hoy: continue
            
            stt = p.stats.get(f"{season_id}_total", {}).get('avg', {})
            if not stt: stt = p.stats.get(f"{season_id}_projected", {}).get('avg', {})
            if not stt: continue
            
            mpg = stt.get('MIN', 0)
            if mpg < min_m: continue
            
            od = own_map.get(p.playerId, {})
            pch = od.get('percentChange', 0.0); pop = od.get('percentOwned', 0.0)
            ti = "🔥🔥" if pch>2 else "🔥" if pch>0.5 else "📈" if pch>0 else "❄️"
            
            sc = mpg * 0.5
            mc = []
            if necesidades:
                for c in necesidades:
                    v = stt.get(c, 0)
                    if v > 0: sc += v * 10; mc.append(c)
            else: sc += stt.get('PTS',0) + stt.get('REB',0) + stt.get('AST',0)
            if pch > 1.5: sc += 15
            elif pch > 0.5: sc += 8
            
            w_data.append({'Nombre': p.name, 'Eq': p.proTeam, 'Trend': f"{ti} {pch:+.1f}%", 'Own%': f"{pop:.1f}%",
                           'Min': round(mpg,1), 'Score': round(sc,1), 'Ayuda': ", ".join(mc) if mc else "Gral"})
            
        if w_data:
            df_w = pd.DataFrame(w_data).sort_values(by='Score', ascending=False).head(20)
            try: st.dataframe(df_w, use_container_width=True)
            except: st.dataframe(df_w)
        else: st.error("Sin resultados.")

st.caption("🚀 Fantasy GM Architect v3.4 | Variable Name Fix + Team Translator")