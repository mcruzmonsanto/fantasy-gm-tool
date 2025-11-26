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

st.set_page_config(page_title="Fantasy GM Pro", page_icon="🏀", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .metric-card {background-color: #1E1E1E; padding: 15px; border-radius: 10px; border: 1px solid #333;}
    .stDataFrame {border: 1px solid #444;}
    .block-container {padding-top: 3rem; padding-bottom: 5rem;} 
    .team-name {font-size: 18px; font-weight: bold; text-align: center;}
    .vs-tag {font-size: 14px; color: #FF4B4B; text-align: center; font-weight: bold;}
    .league-tag {font-size: 12px; color: #888; text-align: center; margin-bottom: 5px;}
    .news-card {background-color: #262730; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #FF4B4B;}
    .news-title {font-weight: bold; color: #FFF; font-size: 15px; text-decoration: none;}
    .news-date {color: #BBB; font-size: 12px; margin-top: 4px;}
    .score-box {font-size: 24px; font-weight: bold; text-align: center; padding: 10px; border-radius: 8px; background-color: #1E1E1E; border: 1px solid #444;}
    .win-score {color: #00FF00; border-color: #00FF00;}
    .lose-score {color: #FF4B4B; border-color: #FF4B4B;}
</style>
""", unsafe_allow_html=True)

# --- 2. LÓGICA DE DATOS ---

GRUPOS_EQUIPOS = [
    ['PHI', 'PHL', '76ERS'], ['UTA', 'UTAH', 'UTH'], ['NY', 'NYK', 'NYA'], ['GS', 'GSW', 'GOL'],
    ['NO', 'NOP', 'NOR'], ['SA', 'SAS', 'SAN'], ['PHO', 'PHX'], ['WAS', 'WSH'], ['CHA', 'CHO'],
    ['BKN', 'BRK', 'BK'], ['LAL'], ['LAC'], # LA Separado
    ['TOR'], ['MEM'], ['MIA'], ['ORL'], ['MIN'], ['MIL'], ['DAL'], ['DEN'], ['HOU'], 
    ['DET'], ['IND'], ['CLE'], ['CHI'], ['ATL'], ['BOS'], ['OKC'], ['POR'], ['SAC']
]

def normalizar_equipo(abrev):
    """Convierte cualquier variante a la estándar de 3 letras para el SOS"""
    s = str(abrev).strip().upper()
    for g in GRUPOS_EQUIPOS:
        if s in g:
            # Devolvemos el elemento de 3 letras que no sea raro, o el primero
            for candidato in g:
                if len(candidato) == 3 and candidato not in ['UTH', 'PHL', 'NYA', 'GOL', 'NOR', 'SAN']:
                    return candidato
            return g[0]
    return s

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

@st.cache_data(ttl=21600)
def get_nba_standings_map():
    """Obtiene el % de victorias normalizando las claves de equipo"""
    try:
        url = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/standings"
        data = requests.get(url).json()
        sos_map = {}
        for conf in data.get('children', []):
            for div in conf.get('standings', {}).get('entries', []):
                team_raw = div['team']['abbreviation']
                team_norm = normalizar_equipo(team_raw)
                stats = div.get('stats', [])
                
                win_pct = 0.5
                for s in stats:
                    if s.get('name') == 'winPercent':
                        win_pct = s.get('value', 0.5); break
                
                sos_map[team_norm] = win_pct
                sos_map[team_raw] = win_pct # Guardamos ambos por seguridad
        return sos_map
    except: return {}

def get_sos_icon(opponent, sos_map):
    if not opponent: return ""
    # APLICAMOS NORMALIZACIÓN ANTES DE BUSCAR (EL ARREGLO)
    opp_norm = normalizar_equipo(opponent)
    win_pct = sos_map.get(opp_norm, 0.5)
    
    if win_pct > 0.60: return "🔴" 
    if win_pct < 0.40: return "🟢" 
    return "⚪"

@st.cache_data(ttl=3600) 
def get_calendario_con_rivales():
    hoy = datetime.now().strftime("%Y%m%d")
    url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={hoy}"
    equipos_hoy = []
    mapa_rivales = {} 
    try:
        data = requests.get(url).json()
        for event in data.get('events', []):
            competitors = event.get('competitions', [])[0].get('competitors', [])
            if len(competitors) == 2:
                ta = competitors[0].get('team', {}).get('abbreviation')
                tb = competitors[1].get('team', {}).get('abbreviation')
                equipos_hoy.extend([ta, tb])
                mapa_rivales[ta] = tb; mapa_rivales[tb] = ta
    except: pass
    return equipos_hoy, mapa_rivales

@st.cache_data(ttl=3600)
def get_calendario_semanal_simple():
    hoy = datetime.now()
    lunes = hoy - timedelta(days=hoy.weekday())
    calendario = {}
    for i in range(7):
        dia = lunes + timedelta(days=i)
        dia_url = dia.strftime("%Y%m%d"); dia_fmt = dia.strftime("%a %d")
        try:
            d = requests.get(f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={dia_url}").json()
            eqs = []
            for e in d['events']:
                for c in e['competitions'][0]['competitors']: eqs.append(c['team']['abbreviation'])
            calendario[dia_fmt] = eqs
        except: calendario[dia_fmt] = []
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
    """Obtiene transacciones recientes (Versión Blindada)"""
    try:
        activity = liga.recent_activity(size=20)
        logs = []
        for act in activity:
            if hasattr(act, 'actions'):
                for action in act.actions:
                    try:
                        team = action[0].team_name if hasattr(action[0], 'team_name') else str(action[0])
                        # player = action[2].name if hasattr(action[2], 'name') else str(action[2])
                        # Fix: A veces action[2] es string directo
                        player_raw = action[2]
                        player = player_raw.name if hasattr(player_raw, 'name') else str(player_raw)
                        
                        fecha = datetime.fromtimestamp(act.date/1000).strftime('%d/%m %H:%M')
                        logs.append({'Fecha': fecha, 'Equipo': team, 'Acción': action[1], 'Jugador': player})
                    except: continue
        return pd.DataFrame(logs)
    except Exception as e:
        return pd.DataFrame([{'Error': f"Fallo API: {str(e)}"}])

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

# HEADER
st.markdown(f"<div class='league-tag'>{nombre_liga}</div>", unsafe_allow_html=True)
col_h1, col_h2, col_h3 = st.columns([5, 1, 5])
with col_h1: st.markdown(f"<div class='team-name'>{mi_equipo.team_name}</div>", unsafe_allow_html=True)
with col_h2: st.markdown("<div class='vs-tag'>VS</div>", unsafe_allow_html=True)
with col_h3: st.markdown(f"<div class='team-name'>{rival.team_name}</div>", unsafe_allow_html=True)
st.write("")

# GRID SEMANAL
with st.expander("📅 Planificación Semanal (Grid)", expanded=True):
    calendario = get_calendario_semanal_simple()
    rows = {"YO": [], "RIVAL": [], "DIFF": []}
    tot_y, tot_r = 0, 0
    
    for dia, equipos_api in calendario.items():
        cy = sum(1 for p in mi_equipo.roster if p.lineupSlot != 'IR' and (not excluir_out or p.injuryStatus != 'OUT') and check_match(p.proTeam, equipos_api))
        cr = sum(1 for p in rival.roster if p.lineupSlot != 'IR' and (not excluir_out or p.injuryStatus != 'OUT') and check_match(p.proTeam, equipos_api))
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

# PESTAÑAS
tab_faceoff, tab_matchup, tab_cortes, tab_waiver, tab_trade, tab_intel = st.tabs(["🔥 Face-Off", "⚔️ Matchup", "🪓 Cortes", "💎 Waiver", "⚖️ Trade", "🕵️ Espía"])
necesidades = []

# 1. FACE-OFF (SEMÁFORO FIXED)
with tab_faceoff:
    st.caption("Proyección diaria con Dificultad de Rival (SOS)")
    equipos_hoy, mapa_rivales = get_calendario_con_rivales()
    sos_map = get_nba_standings_map()
    
    def get_daily_power(roster):
        fuerza = 0; lista = []
        for p in roster:
            if p.lineupSlot != 'IR' and p.injuryStatus != 'OUT':
                mt = check_match(p.proTeam, equipos_hoy)
                if mt:
                    opp = mapa_rivales.get(mt, "")
                    # AQUÍ ESTÁ EL ARREGLO:
                    si = get_sos_icon(opp, sos_map) 
                    sc, _ = calcular_score_fantasy(p, config, season_id)
                    lista.append({'J': p.name, 'VS': f"{si} {opp}", 'FP': round(sc,1)})
        l = sorted(lista, key=lambda x: x['FP'], reverse=True)[:limit_slots]
        return sum([x['FP'] for x in l]), l

    mi_fuerza, mi_lista = get_daily_power(mi_equipo.roster)
    riv_fuerza, riv_lista = get_daily_power(rival.roster)
    
    diff_fuerza = mi_fuerza - riv_fuerza
    
    c_sc1, c_sc2 = st.columns(2)
    with c_sc1:
        st.markdown(f"<div class='metric-box'><div class='label-txt'>MI PROYECCIÓN</div><div class='{'win-val' if diff_fuerza>=0 else 'lose-val'}'>{round(mi_fuerza,1)}</div></div>", unsafe_allow_html=True)
        if mi_lista: st.dataframe(pd.DataFrame(mi_lista), use_container_width=True, hide_index=True)
        else: st.info("Descanso.")
    with c_sc2:
        st.markdown(f"<div class='metric-box'><div class='label-txt'>RIVAL</div><div class='{'win-val' if diff_fuerza<0 else 'lose-val'}'>{round(riv_fuerza,1)}</div></div>", unsafe_allow_html=True)
        if riv_lista: st.dataframe(pd.DataFrame(riv_lista), use_container_width=True, hide_index=True)

    st.divider()
    if diff_fuerza < 0:
        brecha = abs(diff_fuerza)
        st.error(f"⚠️ Pierdes por -{round(brecha,1)} FP.")
        if st.button("🚑 BUSCAR RESCATE"):
            with st.spinner("Buscando..."):
                own_data = get_ownership_data(liga)
                fa = liga.free_agents(size=100)
                rescate = []
                for p in fa:
                    if getattr(p, 'acquisitionType', []) or p.injuryStatus == 'OUT': continue
                    mt = check_match(p.proTeam, equipos_hoy)
                    if not mt: continue
                    
                    sc, s = calcular_score_fantasy(p, config, season_id)
                    if sc > 15:
                        di = sc - brecha
                        ic = "🦸‍♂️" if di > 0 else "🩹"
                        
                        opp = mapa_rivales.get(mt, "")
                        si = get_sos_icon(opp, sos_map)
                        
                        rescate.append({'Jugador': p.name, 'Eq': p.proTeam, 'VS': f"{si} {opp}", 'Score': round(sc,1), 'Impacto': f"{ic} {round(di,1)}"})
                
                if rescate: st.dataframe(pd.DataFrame(rescate).sort_values('Score', ascending=False).head(5), use_container_width=True, hide_index=True)
                else: st.warning("Mercado seco.")

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

# 3. CORTES
with tab_cortes:
    st.caption("Selecciona jugador para ver tendencia.")
    roster_list = [p for p in mi_equipo.roster if p.lineupSlot != 'IR']
    p_names = [p.name for p in roster_list]
    sel_p = st.selectbox("Analizar:", p_names)
    
    roster_data = []
    for p in roster_list:
        s = p.stats.get(f"{season_id}_total", {}).get('avg', {}) or p.stats.get(f"{season_id}_projected", {}).get('avg', {})
        score = s.get('PTS',0) + s.get('REB',0)*1.2 + s.get('AST',0)*1.5 + s.get('STL',0)*2 + s.get('BLK',0)*2
        if 'DD' in config['categorias']: score += s.get('DD', 0) * 5
        icon = "⛔" if p.injuryStatus == 'OUT' else "⚠️" if p.injuryStatus == 'DAY_TO_DAY' else "✅"
        roster_data.append({'J': p.name, 'St': icon, 'Pos': p.lineupSlot, 'Scr': round(score,1), 'Min': round(s.get('MIN',0),1)})
    st.dataframe(pd.DataFrame(roster_data).sort_values('Scr'), use_container_width=True, hide_index=True)
    
    if sel_p:
        p_obj = next((p for p in roster_list if p.name == sel_p), None)
        if p_obj:
            sts = {
                'Temp': p_obj.stats.get(f"{season_id}_total", {}).get('avg', {}).get('PTS', 0),
                'Last 30': p_obj.stats.get(f"{season_id}_last_30", {}).get('avg', {}).get('PTS', 0),
                'Last 15': p_obj.stats.get(f"{season_id}_last_15", {}).get('avg', {}).get('PTS', 0),
                'Last 7': p_obj.stats.get(f"{season_id}_last_7", {}).get('avg', {}).get('PTS', 0)
            }
            st.line_chart(pd.DataFrame({'PTS': sts.values()}, index=sts.keys()))

# 4. WAIVER
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
                    mt = check_match(p.proTeam, eq_hoy)
                    if s_hoy and not mt: continue
                    
                    sc, s = calc_score(p, config, season_id)
                    if not s or sc < 5: continue
                    mpg = s.get('MIN', 0)
                    if mpg < min_m: continue
                    
                    # SOS (ARREGLO AQUÍ TAMBIÉN)
                    riv = mapa_riv.get(mt, "") if mt else ""
                    si = get_sos_icon(riv, sos_map)
                    
                    od = own_data.get(p.playerId, {})
                    pch = od.get('percentChange', 0.0); pop = od.get('percentOwned', 0.0)
                    ti = "🔥🔥" if pch>1 else "❄️" if pch<-1 else "➖"
                    
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
                    
                    w_list.append({'Nombre': p.name, 'Eq': p.proTeam, 'VS': f"{si} {riv}", 
                                   'Trend': f"{ti} {pch:+.1f}%", 'Score': round(sc,1), 'FPPM': f"{ei}{fppm:.2f}", 
                                   'Aporta': ",".join(cats_hit) if cats_hit else "-", '_tr': pch, '_fp': fppm})
                
                if w_list:
                    df = pd.DataFrame(w_list)
                    if orden == "Hype": df = df.sort_values('_tr', ascending=False)
                    elif orden == "FPPM": df = df.sort_values('_fp', ascending=False)
                    else: df = df.sort_values('Score', ascending=False)
                    st.dataframe(df[['Nombre','Eq','VS','Trend','Score','FPPM','Aporta']].head(25), use_container_width=True, hide_index=True)
                else: st.info("Sin resultados.")

# 5. TRADE
with tab_trade:
    c_t1, c_t2 = st.columns(2)
    drop_p = c_t1.selectbox("Soltar:", [p.name for p in mi_equipo.roster])
    fa_top = [p.name for p in liga.free_agents(size=50)]
    add_p = c_t2.selectbox("Fichar:", fa_top)
    
    if st.button("Simular Cambio"):
        p_out = next((p for p in mi_equipo.roster if p.name == drop_p), None)
        p_in = next((p for p in liga.free_agents(size=50) if p.name == add_p), None)
        if p_out and p_in:
            s_out = p_out.stats.get(f"{season_id}_total", {}).get('avg', {})
            s_in = p_in.stats.get(f"{season_id}_total", {}).get('avg', {})
            deltas = []
            for c in config['categorias']:
                vo = s_out.get(c, 0); vi = s_in.get(c, 0); d = vi - vo
                ic = "✅" if d > 0 else "🔻" if d < 0 else "="
                deltas.append({'Cat': c, 'Antes': round(vo,1), 'Ahora': round(vi,1), 'Delta': f"{d:+.1f} {ic}"})
            st.table(pd.DataFrame(deltas))

# 6. INTEL
with tab_intel:
    st.subheader("🕵️ Actividad")
    try:
        df_act = get_league_activity(liga)
        if not df_act.empty and 'Error' not in df_act.columns: st.dataframe(df_act, use_container_width=True, hide_index=True)
        else: st.info("Sin movimientos.")
    except: pass
    st.divider()
    st.subheader("📰 Noticias")
    news_list = get_nba_news()
    if news_list:
        for n in news_list:
            st.markdown(f"<div class='news-card'><a class='news-title' href='{n['l']}' target='_blank'>{n['t']}</a><div class='news-date'>{n['d']}</div></div>", unsafe_allow_html=True)
    else:
        st.info("No hay noticias disponibles.")

st.caption("🚀 Fantasy GM Architect v7.2 | SOS Fixed & Restored")