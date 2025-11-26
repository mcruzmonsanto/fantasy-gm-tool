import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import sys
import os
import xml.etree.ElementTree as ET

from src.conectar import obtener_liga
from config.credenciales import LIGAS

st.set_page_config(
    page_title="Fantasy GM Pro", 
    page_icon="🏀", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# CSS
st.markdown("""
<style>
    .stDataFrame {border: 1px solid #333;}
    .block-container {padding-top: 3rem; padding-bottom: 5rem;} 
    .team-name {font-size: 18px; font-weight: bold; text-align: center;}
    .vs-tag {font-size: 14px; color: #FF4B4B; text-align: center; font-weight: bold;}
    .league-tag {font-size: 12px; color: #888; text-align: center; margin-bottom: 5px;}
    .news-card {background-color: #262730; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #FF4B4B;}
    .news-title {font-weight: bold; color: #FFF; font-size: 15px; text-decoration: none;}
    .news-date {color: #BBB; font-size: 12px; margin-top: 4px;}
    /* Estilo Face-Off */
    .score-box {font-size: 24px; font-weight: bold; text-align: center; padding: 10px; border-radius: 8px; background-color: #1E1E1E; border: 1px solid #444;}
    .win-score {color: #00FF00; border-color: #00FF00;}
    .lose-score {color: #FF4B4B; border-color: #FF4B4B;}
</style>
""", unsafe_allow_html=True)

# --- 2. LÓGICA DE DATOS ---

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

def check_juego_hoy(equipo_roster, lista_equipos_api):
    for eq_api in lista_equipos_api:
        if son_mismo_equipo(equipo_roster, eq_api): return True
    return False

@st.cache_data(ttl=3600) 
def get_calendario_semanal():
    hoy = datetime.now()
    lunes = hoy - timedelta(days=hoy.weekday())
    calendario = {}
    for i in range(7):
        dia = lunes + timedelta(days=i)
        dia_api = dia.strftime("%Y%m%d")
        dia_fmt = dia.strftime("%a %d")
        try:
            url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={dia_api}"
            data = requests.get(url).json()
            equipos = []
            for ev in data.get('events', []):
                for comp in ev.get('competitions', []):
                    for c in comp.get('competitors', []):
                        equipos.append(c.get('team', {}).get('abbreviation'))
            calendario[dia_fmt] = equipos
        except: calendario[dia_fmt] = []
    return calendario

def get_equipos_hoy_directo():
    """Obtiene equipos de hoy sin caché para el Face-Off"""
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
        news = []
        for item in root.findall('./channel/item')[:8]: 
            news.append({'title': item.find('title').text, 'link': item.find('link').text, 'pubDate': item.find('pubDate').text})
        return news
    except: return []

def get_league_activity(liga):
    try:
        activity = liga.recent_activity(size=15)
        logs = []
        for act in activity:
            if hasattr(act, 'actions'):
                for action in act.actions:
                    logs.append({'Fecha': datetime.fromtimestamp(act.date/1000).strftime('%d/%m %H:%M'), 'Equipo': action[0].team_name, 'Acción': action[1], 'Jugador': action[2]})
        return pd.DataFrame(logs)
    except: return pd.DataFrame()

def calcular_score_fantasy(player, config, season_id):
    """Calcula el Score Fantasy unificado para toda la app"""
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

# --- CABECERA ---
st.markdown(f"<div class='league-tag'>{nombre_liga}</div>", unsafe_allow_html=True)
col_h1, col_h2, col_h3 = st.columns([5, 1, 5])
with col_h1: st.markdown(f"<div class='team-name'>{mi_equipo.team_name}</div>", unsafe_allow_html=True)
with col_h2: st.markdown("<div class='vs-tag'>VS</div>", unsafe_allow_html=True)
with col_h3: st.markdown(f"<div class='team-name'>{rival.team_name}</div>", unsafe_allow_html=True)
st.write("")

# --- MÓDULO 1: GRID SEMANAL ---
with st.expander("📅 Planificación Semanal (Grid)", expanded=False):
    calendario = get_calendario_semanal()
    rows = {"YO": [], "RIVAL": [], "DIFF": []}
    tot_y, tot_r = 0, 0
    for dia, equipos_api in calendario.items():
        cy = sum(1 for p in mi_equipo.roster if p.lineupSlot != 'IR' and (not excluir_out or p.injuryStatus != 'OUT') and check_juego_hoy(p.proTeam, equipos_api))
        cr = sum(1 for p in rival.roster if p.lineupSlot != 'IR' and (not excluir_out or p.injuryStatus != 'OUT') and check_juego_hoy(p.proTeam, equipos_api))
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

# --- MÓDULO 2: PESTAÑAS TÁCTICAS ---
tab_faceoff, tab_matchup, tab_cortes, tab_waiver, tab_intel = st.tabs(["🔥 Face-Off", "⚔️ Matchup", "🪓 Cortes", "💎 Waiver", "🕵️ Espía"])
necesidades = []

# TAB: FACE-OFF (EL CHOQUE DIARIO)
with tab_faceoff:
    st.caption("Comparación de fuerza de plantillas para HOY.")
    
    equipos_hoy = get_equipos_hoy_directo()
    
    # 1. Calcular Mi Fuerza
    mi_fuerza = 0
    mi_lista = []
    for p in mi_equipo.roster:
        if p.lineupSlot != 'IR' and p.injuryStatus != 'OUT' and check_juego_hoy(p.proTeam, equipos_hoy):
            sc, _ = calcular_score_fantasy(p, config, season_id)
            mi_lista.append({'Jugador': p.name, 'Score': round(sc,1)})
    
    # Ordenar y aplicar cap
    mi_lista = sorted(mi_lista, key=lambda x: x['Score'], reverse=True)[:limit_slots]
    mi_fuerza = sum([x['Score'] for x in mi_lista])

    # 2. Calcular Fuerza Rival
    riv_fuerza = 0
    riv_lista = []
    for p in rival.roster:
        if p.lineupSlot != 'IR' and p.injuryStatus != 'OUT' and check_juego_hoy(p.proTeam, equipos_hoy):
            sc, _ = calcular_score_fantasy(p, config, season_id)
            riv_lista.append({'Jugador': p.name, 'Score': round(sc,1)})
            
    riv_lista = sorted(riv_lista, key=lambda x: x['Score'], reverse=True)[:limit_slots]
    riv_fuerza = sum([x['Score'] for x in riv_lista])

    # 3. Visualización
    diff_fuerza = mi_fuerza - riv_fuerza
    
    col_score1, col_score2 = st.columns(2)
    with col_score1:
        st.markdown(f"<div class='score-box {'win-score' if diff_fuerza > 0 else ''}'>YO: {round(mi_fuerza,1)} FP</div>", unsafe_allow_html=True)
        if mi_lista: st.dataframe(pd.DataFrame(mi_lista), use_container_width=True, hide_index=True)
        else: st.info("No tienes jugadores hoy.")
        
    with col_score2:
        st.markdown(f"<div class='score-box {'lose-score' if diff_fuerza < 0 else ''}'>RIVAL: {round(riv_fuerza,1)} FP</div>", unsafe_allow_html=True)
        if riv_lista: st.dataframe(pd.DataFrame(riv_lista), use_container_width=True, hide_index=True)
        else: st.info("Rival descansa hoy.")

    # 4. Diagnóstico y Rescate
    st.divider()
    if diff_fuerza > 0:
        st.success(f"🚀 PROYECCIÓN: Ganas el día por +{round(diff_fuerza,1)} puntos fantasy. ¡Mantén la alineación!")
    else:
        brecha = abs(diff_fuerza)
        st.error(f"⚠️ PROYECCIÓN: Pierdes el día por -{round(brecha,1)} puntos fantasy.")
        
        if st.button("🚑 BUSCAR RESCATE EN WAIVER (HOY)"):
            with st.spinner(f"Buscando agente libre que proyecte > {round(brecha,1)} FP..."):
                own_data = get_ownership_data(liga)
                fa = liga.free_agents(size=100)
                rescate = []
                for p in fa:
                    if getattr(p, 'acquisitionType', []) or p.injuryStatus == 'OUT': continue
                    if not check_juego_hoy(p.proTeam, equipos_hoy): continue
                    
                    sc, s = calcular_score_fantasy(p, config, season_id)
                    if sc > 15: # Filtro mínimo de decencia
                        diff_impacto = sc - brecha # Cuánto cubre de la brecha
                        # Icono de salvación
                        icon = "🦸‍♂️" if diff_impacto > 0 else "🩹"
                        rescate.append({
                            'Salvador': p.name, 
                            'Equipo': p.proTeam, 
                            'Proyección': round(sc,1), 
                            'Impacto': f"{icon} {round(diff_impacto,1)}"
                        })
                
                if rescate:
                    st.write("### 💎 Opciones para remontar hoy:")
                    df_rescate = pd.DataFrame(rescate).sort_values('Proyección', ascending=False).head(5)
                    st.dataframe(df_rescate, use_container_width=True, hide_index=True)
                else:
                    st.warning("El mercado está seco hoy. Difícil remontar.")


# TAB: MATCHUP
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
    st.info(f"🏆 Marcador: {w}-{l}-{t} | 🎯 Faltan: {', '.join(necesidades)}")
    st.dataframe(pd.DataFrame(data_m, columns=['Cat','Yo','Rival','Diff','W']), use_container_width=True, hide_index=True)

# TAB: CORTES
with tab_cortes:
    roster_data = []
    for p in mi_equipo.roster:
        sc, s = calcular_score_fantasy(p, config, season_id)
        icon = "⛔" if p.injuryStatus == 'OUT' else "⚠️" if p.injuryStatus == 'DAY_TO_DAY' else "✅"
        roster_data.append({'Jugador': p.name, 'St': icon, 'Pos': p.lineupSlot, 'Score': round(sc,1), 'Min': round(s.get('MIN',0),1)})
    st.dataframe(pd.DataFrame(roster_data).sort_values('Score'), use_container_width=True, hide_index=True)

# TAB: WAIVER
with tab_waiver:
    c_filt1, c_filt2 = st.columns(2)
    min_mins = c_filt1.number_input("Minutos >", 10, 40, 22)
    solo_hoy = c_filt2.checkbox("Juegan HOY", True)
    ordenar_por = st.selectbox("Ordenar por:", ["Score (Rendimiento)", "Trend (Hype)", "FPPM (Eficiencia)"])
    
    if st.button("🔎 Escanear Mercado"):
        with st.spinner("Analizando..."):
            eq_hoy = get_equipos_hoy_directo() if solo_hoy else []
            own_data = get_ownership_data(liga)
            fa = liga.free_agents(size=150)
            w_list = []
            for p in fa:
                if getattr(p, 'acquisitionType', []) or p.injuryStatus == 'OUT': continue
                if solo_hoy and not check_juego_hoy(p.proTeam, eq_hoy): continue
                
                sc, s = calcular_score_fantasy(p, config, season_id)
                if sc < 5: continue
                mpg = s.get('MIN', 0)
                if mpg < min_mins: continue
                
                od = own_data.get(p.playerId, {})
                pch = od.get('percentChange', 0.0); pop = od.get('percentOwned', 0.0)
                ti = "🔥🔥" if pch>2 else "🔥" if pch>0.5 else "📈" if pch>0 else "❄️"
                
                # Score Adjustments
                cats_hit = []
                if necesidades:
                    for c in necesidades:
                        v = s.get(c, 0)
                        if v > 0: sc += v * 10; cats_hit.append(c)
                if pch > 1.5: sc += 15
                
                fppm = sc / mpg if mpg > 0 else 0
                eff_icon = "💎" if fppm > 1.1 else ""
                w_list.append({'Nombre': p.name, 'Eq': p.proTeam, 'Trend': f"{ti} {pch:+.1f}%", 'Min': round(mpg,1), 
                               'Score': round(sc,1), 'FPPM': f"{eff_icon} {fppm:.2f}", 'Aporta': ",".join(cats_hit) if cats_hit else "-", '_trend': pch, '_fppm': fppm})
            if w_list:
                df_w = pd.DataFrame(w_list)
                if ordenar_por == "Trend (Hype)": df_w = df_w.sort_values('_trend', ascending=False)
                elif ordenar_por == "FPPM (Eficiencia)": df_w = df_w.sort_values('_fppm', ascending=False)
                else: df_w = df_w.sort_values('Score', ascending=False)
                st.dataframe(df_w[['Nombre','Eq','Trend','FPPM','Min','Score','Aporta']].head(20), use_container_width=True, hide_index=True)
            else: st.info("Sin resultados.")

# TAB: ESPÍA
with tab_intel:
    st.subheader("🕵️ Actividad Reciente")
    try:
        df_act = get_league_activity(liga)
        if not df_act.empty and 'Error' not in df_act.columns: st.dataframe(df_act, use_container_width=True, hide_index=True)
        else: st.info("Sin actividad reciente.")
    except: st.info("Datos no disponibles.")
    st.markdown("---")
    st.subheader("📰 Noticias NBA")
    news = get_nba_news()
    if news:
        for n in news:
            st.markdown(f"<div class='news-card'><a class='news-title' href='{n['link']}' target='_blank'>{n['title']}</a><div class='news-date'>{n['pubDate']}</div></div>", unsafe_allow_html=True)

st.caption("🚀 Fantasy GM Architect v6.0 | The Daily Clash")