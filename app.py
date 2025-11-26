import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import sys
import os
import xml.etree.ElementTree as ET

# --- 1. CONFIGURACIÓN INICIAL ---
from src.conectar import obtener_liga
from config.credenciales import LIGAS

st.set_page_config(
    page_title="Fantasy GM Pro", 
    page_icon="🏀", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# CSS AVANZADO
st.markdown("""
<style>
    .stDataFrame {border: 1px solid #333;}
    .block-container {padding-top: 3rem; padding-bottom: 5rem;} 
    .team-name {font-size: 18px; font-weight: bold; text-align: center;}
    .vs-tag {font-size: 14px; color: #FF4B4B; text-align: center; font-weight: bold;}
    .news-card {background-color: #262730; padding: 10px; border-radius: 5px; margin-bottom: 10px; border-left: 4px solid #FF4B4B;}
    .news-title {font-weight: bold; color: #FFF; font-size: 14px; text-decoration: none;}
    
    /* Estilos para Deltas en Trade */
    .delta-pos {color: #00FF00; font-weight: bold;}
    .delta-neg {color: #FF4B4B; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# --- 2. CEREBRO DE DATOS ---

GRUPOS_EQUIPOS = [
    ['PHI', 'PHL', '76ERS'], ['UTA', 'UTAH', 'UTH'], ['NY', 'NYK', 'NYA'], ['GS', 'GSW', 'GOL'],
    ['NO', 'NOP', 'NOR'], ['SA', 'SAS', 'SAN'], ['PHO', 'PHX'], ['WAS', 'WSH'], ['CHA', 'CHO'],
    ['BKN', 'BRK', 'BK'], ['LAL'], ['LAC'],
    ['TOR'], ['MEM'], ['MIA'], ['ORL'], ['MIN'], ['MIL'], ['DAL'], ['DEN'], ['HOU'], 
    ['DET'], ['IND'], ['CLE'], ['CHI'], ['ATL'], ['BOS'], ['OKC'], ['POR'], ['SAC']
]

def son_mismo_equipo(eq_roster, eq_api):
    r, a = eq_roster.strip().upper(), eq_api.strip().upper()
    if r == a: return True
    for grupo in GRUPOS_EQUIPOS:
        if r in grupo and a in grupo: return True
    return False

def obtener_match_exacto(equipo_roster, lista_equipos_hoy_api):
    for eq_api in lista_equipos_hoy_api:
        if son_mismo_equipo(equipo_roster, eq_api): return eq_api
    return None

# --- NUEVA FUNCIÓN: CACHÉ DE STANDINGS (SOS) ---
@st.cache_data(ttl=21600) # 6 horas
def get_nba_standings_map():
    """Devuelve un mapa {EQUIPO: Win%} para calcular dificultad"""
    try:
        url = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/standings"
        data = requests.get(url).json()
        sos_map = {}
        for conf in data.get('children', []):
            for div in conf.get('standings', {}).get('entries', []):
                team = div['team']['abbreviation']
                stats = div.get('stats', [])
                # Buscar win percentage (suele ser el stat con name 'winPercent')
                # Método rápido: wins / (wins+losses)
                # La API de standings es compleja, usaremos un mock basado en record texto si falla
                # Simplificación: Usamos el 'record' summary y parseamos, o buscamos la stat
                # Para no complicar, asumimos 0.5 si falla
                sos_map[team] = 0.5 
                
                # Intento de extracción real
                for s in stats:
                    if s.get('name') == 'winPercent':
                        sos_map[team] = s.get('value', 0.5)
                        break
        return sos_map
    except:
        return {}

def get_sos_icon(opponent, sos_map):
    """Devuelve icono basado en la dificultad del rival (Win%)"""
    if not opponent: return ""
    win_pct = sos_map.get(opponent, 0.5)
    if win_pct > 0.60: return "🔴" # Rival difícil (Celtics, etc)
    if win_pct < 0.40: return "🟢" # Rival fácil (Wizards, etc)
    return "⚪" # Rival promedio

@st.cache_data(ttl=3600) 
def get_calendario_con_rivales():
    """
    Retorna:
    1. Calendario simple (lista de equipos que juegan)
    2. Mapa de rivales {EQUIPO_QUE_JUEGA: RIVAL}
    """
    hoy = datetime.now()
    hoy_str = hoy.strftime("%Y%m%d")
    url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={hoy_str}"
    
    equipos_hoy = []
    mapa_rivales = {} # Ej: {'LAL': 'BOS', 'BOS': 'LAL'}
    
    try:
        data = requests.get(url).json()
        for event in data.get('events', []):
            competitors = event.get('competitions', [])[0].get('competitors', [])
            if len(competitors) == 2:
                team_a = competitors[0].get('team', {}).get('abbreviation')
                team_b = competitors[1].get('team', {}).get('abbreviation')
                
                equipos_hoy.extend([team_a, team_b])
                mapa_rivales[team_a] = team_b
                mapa_rivales[team_b] = team_a
    except: pass
    return equipos_hoy, mapa_rivales

@st.cache_data(ttl=3600)
def get_calendario_semanal_simple():
    # Función ligera para el grid (solo nombres)
    hoy = datetime.now()
    lunes = hoy - timedelta(days=hoy.weekday())
    calendario = {}
    for i in range(7):
        dia = lunes + timedelta(days=i)
        dia_str = dia.strftime("%Y%m%d"); dia_fmt = dia.strftime("%a %d")
        url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={dia_str}"
        eqs = []
        try:
            d = requests.get(url).json()
            for e in d['events']:
                for c in e['competitions'][0]['competitors']: eqs.append(c['team']['abbreviation'])
        except: pass
        calendario[dia_fmt] = eqs
    return calendario

def get_ownership_data(liga):
    try:
        url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{liga.year}/segments/0/leagues/{liga.league_id}"
        filters = {"players": {"filterStatus": {"value": ["FREEAGENT", "WAIVERS"]}, "limit": 500, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
        headers = {'x-fantasy-filter': json.dumps(filters)}
        r = requests.get(url, params={'view': 'kona_player_info'}, headers=headers, cookies=liga.espn_request.cookies)
        data = r.json()
        return {p['id']: p['player']['ownership'] for p in data.get('players', [])}
    except: return {}

def get_nba_news():
    try:
        url = "https://www.espn.com/espn/rss/nba/news"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        root = ET.fromstring(response.content)
        return [{'title': i.find('title').text, 'link': i.find('link').text, 'pubDate': i.find('pubDate').text} for i in root.findall('./channel/item')[:6]]
    except: return []

def get_league_activity(liga):
    try:
        activity = liga.recent_activity(size=15)
        logs = []
        for act in activity:
            if hasattr(act, 'actions'):
                for a in act.actions: logs.append({'Fecha': datetime.fromtimestamp(act.date/1000).strftime('%d %H:%M'), 'Eq': a[0].team_name, 'Act': a[1], 'Jug': a[2]})
        return pd.DataFrame(logs)
    except: return pd.DataFrame()

def calcular_score_fantasy(player, config, season_id):
    s = player.stats.get(f"{season_id}_total", {}).get('avg', {})
    if not s: s = player.stats.get(f"{season_id}_projected", {}).get('avg', {})
    score = s.get('PTS',0) + s.get('REB',0)*1.2 + s.get('AST',0)*1.5 + s.get('STL',0)*2 + s.get('BLK',0)*2
    if 'DD' in config['categorias']: score += s.get('DD', 0) * 5
    return score, s

def calcular_stats_matchup(lineup):
    totales = {k: 0 for k in ['PTS','REB','AST','STL','BLK','3PTM','TO','DD','FGM','FGA','FTM','FTA']}
    for p in lineup:
        if p.slot_position in ['BE', 'IR']: continue
        s = p.stats.get('total', {}) if 'total' in p.stats else {}
        if not s and p.stats:
             for k, v in p.stats.items():
                if isinstance(v, dict) and 'total' in v: s = v['total']; break
        if not s: continue
        for cat in totales:
            if cat in ['FGM','FGA','FTM','FTA']: totales[cat] += s.get(cat, 0)
            elif cat == '3PTM': totales[cat] += s.get('3PM', s.get('3PTM', 0))
            else: totales[cat] += s.get(cat, 0)
    if totales['FGA'] > 0: totales['FG%'] = totales['FGM'] / totales['FGA']
    if totales['FTA'] > 0: totales['FT%'] = totales['FTM'] / totales['FTA']
    return totales

# --- 3. INTERFAZ DE USUARIO ---

with st.sidebar:
    st.header("⚙️ Configuración")
    nombre_liga = st.selectbox("Liga", list(LIGAS.keys()))
    st.divider()
    limit_slots = st.number_input("Titulares Máximos", 5, 20, 10)
    excluir_out = st.checkbox("Ignorar 'OUT' en Grid", True)
    if st.button("🔄 Refrescar"): st.cache_data.clear()

config = LIGAS[nombre_liga]
liga = obtener_liga(nombre_liga)
season_id = config['year']

if not liga: st.error("Error de conexión"); st.stop()

box_scores = liga.box_scores()
matchup = next((m for m in box_scores if "Max" in m.home_team.team_name or "Max" in m.away_team.team_name), None)
soy_home = matchup and "Max" in matchup.home_team.team_name

if not matchup: st.warning("No hay matchup activo."); st.stop()

mi_equipo = matchup.home_team if soy_home else matchup.away_team
rival = matchup.away_team if soy_home else matchup.home_team

# CABECERA
st.markdown(f"<div class='league-tag'>{nombre_liga}</div>", unsafe_allow_html=True)
col_h1, col_h2, col_h3 = st.columns([5, 1, 5])
with col_h1: st.markdown(f"<div class='team-name'>{mi_equipo.team_name}</div>", unsafe_allow_html=True)
with col_h2: st.markdown("<div class='vs-tag'>VS</div>", unsafe_allow_html=True)
with col_h3: st.markdown(f"<div class='team-name'>{rival.team_name}</div>", unsafe_allow_html=True)
st.write("")

# GRID SEMANAL
with st.expander("📅 Planificación Semanal (Grid)", expanded=False):
    calendario = get_calendario_semanal_simple()
    rows = {"YO": [], "RIVAL": [], "DIFF": []}
    tot_y, tot_r = 0, 0
    for dia, equipos_api in calendario.items():
        cy = sum(1 for p in mi_equipo.roster if p.lineupSlot != 'IR' and (not excluir_out or p.injuryStatus != 'OUT') and obtener_match_exacto(p.proTeam, equipos_api))
        cr = sum(1 for p in rival.roster if p.lineupSlot != 'IR' and (not excluir_out or p.injuryStatus != 'OUT') and obtener_match_exacto(p.proTeam, equipos_api))
        uy, ur = min(cy, limit_slots), min(cr, limit_slots)
        rows["YO"].append(uy); rows["RIVAL"].append(ur)
        diff = uy - ur
        icon = "✅" if diff > 0 else "⚠️" if diff < 0 else "="
        rows["DIFF"].append(f"{diff} {icon}")
        tot_y += uy; tot_r += ur
    rows["YO"].append(tot_y); rows["RIVAL"].append(tot_r)
    dt = tot_y - tot_r
    rows["DIFF"].append(f"{dt} {'🔥' if dt > 0 else '💀'}")
    st.dataframe(pd.DataFrame(rows, index=list(calendario.keys()) + ["TOTAL"]).T, use_container_width=True)

# PESTAÑAS TÁCTICAS
tab_faceoff, tab_matchup, tab_cortes, tab_waiver, tab_trade, tab_intel = st.tabs(["🔥 Face-Off", "⚔️ Matchup", "🪓 Cortes", "💎 Waiver", "⚖️ Trade", "🕵️ Espía"])
necesidades = []

# 1. FACE-OFF (Con SOS)
with tab_faceoff:
    st.caption("Proyección diaria con Dificultad de Rival (SOS)")
    equipos_hoy, mapa_rivales = get_calendario_con_rivales()
    sos_map = get_nba_standings_map()
    
    def get_daily_power(roster):
        fuerza = 0; lista = []
        for p in roster:
            if p.lineupSlot != 'IR' and p.injuryStatus != 'OUT':
                match_team = obtener_match_exacto(p.proTeam, equipos_hoy)
                if match_team:
                    rival_real = mapa_rivales.get(match_team, "N/A")
                    sos_icon = get_sos_icon(rival_real, sos_map)
                    sc, _ = calcular_score_fantasy(p, config, season_id)
                    lista.append({'J': p.name, 'VS': f"{sos_icon} {rival_real}", 'FP': round(sc,1)})
        lista = sorted(lista, key=lambda x: x['FP'], reverse=True)[:limit_slots]
        return sum([x['FP'] for x in lista]), lista

    mi_fuerza, mi_lista = get_daily_power(mi_equipo.roster)
    riv_fuerza, riv_lista = get_daily_power(rival.roster)
    
    diff_fuerza = mi_fuerza - riv_fuerza
    col_sc1, col_sc2 = st.columns(2)
    with col_sc1:
        st.metric("YO (FP)", round(mi_fuerza,1), delta=round(diff_fuerza,1))
        if mi_lista: st.dataframe(pd.DataFrame(mi_lista), use_container_width=True, hide_index=True)
    with col_sc2:
        st.metric("RIVAL (FP)", round(riv_fuerza,1))
        if riv_lista: st.dataframe(pd.DataFrame(riv_lista), use_container_width=True, hide_index=True)

# 2. MATCHUP
with tab_matchup:
    ms = calcular_stats_matchup(matchup.home_lineup if soy_home else matchup.away_lineup)
    rs = calcular_stats_matchup(matchup.away_lineup if soy_home else matchup.home_lineup)
    data_m = []
    w, l, t = 0, 0, 0
    for c in config['categorias']:
        k = '3PTM' if c == '3PTM' and '3PTM' not in ms else c
        m, r = ms.get(k, 0), rs.get(k, 0)
        diff = m - r if c != 'TO' else r - m
        if diff > 0: stt = "🟢"; w += 1
        elif diff < 0: stt = "🔴"; l += 1; necesidades.append(c)
        else: stt = "🟡"; t += 1
        fmt_m = f"{m:.3f}" if c in ['FG%','FT%'] else f"{m:.0f}"
        fmt_r = f"{r:.3f}" if c in ['FG%','FT%'] else f"{r:.0f}"
        data_m.append([c, fmt_m, fmt_r, f"{diff:.2f}", stt])
    st.info(f"🏆 {w}-{l}-{t} | Faltan: {', '.join(necesidades)}")
    st.dataframe(pd.DataFrame(data_m, columns=['Cat','Yo','Riv','Dif','W']), use_container_width=True, hide_index=True)

# 3. CORTES (Con Gráficas de Tendencia)
with tab_cortes:
    st.caption("Selecciona un jugador para ver su tendencia reciente.")
    roster_list = [p for p in mi_equipo.roster if p.lineupSlot != 'IR']
    
    # Selector para Deep Dive
    player_names = [p.name for p in roster_list]
    selected_player_name = st.selectbox("🔍 Analizar Jugador:", player_names)
    
    # Tabla Resumen
    roster_data = []
    for p in roster_list:
        s = p.stats.get(f"{season_id}_total", {}).get('avg', {}) or p.stats.get(f"{season_id}_projected", {}).get('avg', {})
        score = s.get('PTS',0) + s.get('REB',0)*1.2 + s.get('AST',0)*1.5 + s.get('STL',0)*2 + s.get('BLK',0)*2
        if 'DD' in config['categorias']: score += s.get('DD', 0) * 5
        icon = "⛔" if p.injuryStatus == 'OUT' else "⚠️" if p.injuryStatus == 'DAY_TO_DAY' else "✅"
        roster_data.append({'J': p.name, 'St': icon, 'Pos': p.lineupSlot, 'Scr': round(score,1), 'Min': round(s.get('MIN',0),1)})
    st.dataframe(pd.DataFrame(roster_data).sort_values('Scr'), use_container_width=True, hide_index=True)
    
    # Gráfico de Tendencia del Seleccionado
    if selected_player_name:
        p_obj = next((p for p in roster_list if p.name == selected_player_name), None)
        if p_obj:
            # Extraemos splits si existen
            stats_season = p_obj.stats.get(f"{season_id}_total", {}).get('avg', {}).get('PTS', 0)
            stats_7 = p_obj.stats.get(f"{season_id}_last_7", {}).get('avg', {}).get('PTS', 0)
            stats_15 = p_obj.stats.get(f"{season_id}_last_15", {}).get('avg', {}).get('PTS', 0)
            stats_30 = p_obj.stats.get(f"{season_id}_last_30", {}).get('avg', {}).get('PTS', 0)
            
            chart_data = pd.DataFrame({
                'Periodo': ['Temp', 'Last 30', 'Last 15', 'Last 7'],
                'PTS': [stats_season, stats_30, stats_15, stats_7]
            })
            st.line_chart(chart_data.set_index('Periodo'))

# 4. WAIVER (Con SOS)
with tab_waiver:
    c1, c2 = st.columns(2)
    min_m = c1.number_input("Minutos >", 10, 40, 22)
    s_hoy = c2.checkbox("Juegan HOY", True)
    orden = st.selectbox("Ordenar:", ["Score", "Hype", "FPPM"])
    
    if st.button("🔎 Escanear"):
        with st.spinner("Analizando..."):
            eq_hoy, mapa_riv = get_calendario_con_rivales()
            if not eq_hoy and s_hoy: st.warning("No hay partidos hoy.")
            else:
                own_data = get_ownership_data(liga)
                sos_map = get_nba_standings_map()
                fa = liga.free_agents(size=150)
                w_list = []
                for p in fa:
                    if getattr(p, 'acquisitionType', []) or p.injuryStatus == 'OUT': continue
                    match_team = obtener_match_exacto(p.proTeam, eq_hoy)
                    if s_hoy and not match_team: continue
                    
                    s = p.stats.get(f"{season_id}_total", {}).get('avg', {}) or p.stats.get(f"{season_id}_projected", {}).get('avg', {})
                    if not s: continue
                    mpg = s.get('MIN', 0)
                    if mpg < min_m: continue
                    
                    # SOS
                    rival_real = mapa_riv.get(match_team, "") if match_team else ""
                    sos_icon = get_sos_icon(rival_real, sos_map)
                    
                    od = own_data.get(p.playerId, {})
                    pch = od.get('percentChange', 0.0); pop = od.get('percentOwned', 0.0)
                    ti = "🔥" if pch>1 else "❄️" if pch<-1 else "➖"
                    
                    sc = mpg * 0.5
                    cats_hit = []
                    if necesidades:
                        for c in necesidades:
                            v = s.get(c, 0)
                            if v > 0: sc += v * 10; cats_hit.append(c)
                    else: sc += s.get('PTS',0) + s.get('REB',0)*1.2
                    if pch > 1.5: sc += 15
                    
                    std = s.get('PTS',0)+s.get('REB',0)*1.2+s.get('AST',0)*1.5+s.get('STL',0)*2+s.get('BLK',0)*2
                    fppm = std/mpg if mpg>0 else 0
                    ei = "💎" if fppm > 1.1 else ""
                    
                    w_list.append({'Nombre': p.name, 'Eq': p.proTeam, 'VS': f"{sos_icon} {rival_real}", 
                                   'Trend': f"{ti} {pch:+.1f}%", 'Score': round(sc,1), 'FPPM': f"{ei}{fppm:.2f}", 
                                   'Aporta': ",".join(cats_hit) if cats_hit else "-", '_tr': pch, '_fp': fppm})
                
                if w_list:
                    df = pd.DataFrame(w_list)
                    if orden == "Hype": df = df.sort_values('_tr', ascending=False)
                    elif orden == "FPPM": df = df.sort_values('_fp', ascending=False)
                    else: df = df.sort_values('Score', ascending=False)
                    st.dataframe(df[['Nombre','Eq','VS','Trend','Score','FPPM','Aporta']].head(20), use_container_width=True, hide_index=True)
                else: st.info("Sin resultados.")

# 5. TRADE SIMULATOR (NUEVO)
with tab_trade:
    st.subheader("⚖️ Simulador de Intercambio")
    
    col_t1, col_t2 = st.columns(2)
    # Mis Jugadores
    mis_jugadores = [p.name for p in mi_equipo.roster]
    drop_player = col_t1.selectbox("Voy a soltar a:", mis_jugadores)
    
    # Jugadores Rival/Waiver (Top 50 disponibles + Rival)
    # Para simplificar y que sea rápido, usamos los top FA cargados previamente o manual
    # Aquí haremos una versión "Quick Check": Escribe el nombre o selecciona de una lista pequeña
    target_source = col_t2.radio("Objetivo:", ["Waiver (Top)", "Rival"])
    
    target_player = None
    if target_source == "Waiver (Top)":
        fa_names = [p.name for p in liga.free_agents(size=50)]
        target_name = col_t2.selectbox("Quiero fichar a:", fa_names)
        if st.button("Simular Cambio"):
            # Buscar objetos
            p_drop = next((p for p in mi_equipo.roster if p.name == drop_player), None)
            p_add = next((p for p in liga.free_agents(size=50) if p.name == target_name), None) # Re-query puede ser lento, optimización idealmente caché
            
            if p_drop and p_add:
                s_out = p_drop.stats.get(f"{season_id}_total", {}).get('avg', {})
                s_in = p_add.stats.get(f"{season_id}_total", {}).get('avg', {})
                
                deltas = []
                for c in config['categorias']:
                    v_out = s_out.get(c, 0)
                    v_in = s_in.get(c, 0)
                    diff = v_in - v_out
                    
                    icon = "✅" if diff > 0 else "🔻" if diff < 0 else "="
                    deltas.append({'Cat': c, 'Antes': round(v_out,1), 'Después': round(v_in,1), 'Delta': f"{diff:+.1f} {icon}"})