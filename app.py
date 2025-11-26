import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# --- 1. CONFIGURACIÓN Y CONEXIÓN ---
from src.conectar import obtener_liga
from config.credenciales import LIGAS

st.set_page_config(
    page_title="Fantasy GM Pro",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. ESTILOS VISUALES (CSS CORREGIDO) ---
st.markdown("""
<style>
    /* AUMENTADO EL PADDING SUPERIOR PARA EVITAR CORTES EN TÍTULO */
    .block-container {padding-top: 5rem; padding-bottom: 4rem;}
    
    .stDataFrame {border: 1px solid #2b2b2b; border-radius: 5px;}
    .team-name {font-size: 1.1rem; font-weight: 700; text-align: center; margin-bottom: 0;}
    .vs-tag {font-size: 0.9rem; color: #ff4b4b; text-align: center; font-weight: 800; margin-top: 5px;}
    .league-tag {font-size: 0.85rem; color: #aaa; text-align: center; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;}
    .metric-box {
        background-color: #1e1e1e; border: 1px solid #333; border-radius: 8px; 
        padding: 15px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .win-val {color: #00ff00; font-size: 1.5rem; font-weight: bold;}
    .lose-val {color: #ff4b4b; font-size: 1.5rem; font-weight: bold;}
    .label-txt {color: #ccc; font-size: 0.85rem;}
    .news-card {
        background-color: #262730; padding: 12px; border-radius: 6px; 
        margin-bottom: 8px; border-left: 3px solid #ff4b4b;
        transition: transform 0.2s;
    }
    .news-title {font-weight: 600; color: #fff; text-decoration: none; font-size: 0.95rem;}
    .news-date {color: #888; font-size: 0.75rem; margin-top: 4px;}
</style>
""", unsafe_allow_html=True)

# --- 3. MOTOR DE DATOS (LÓGICA) ---

GRUPOS_EQUIPOS = [
    ['PHI', 'PHL', '76ERS'], ['UTA', 'UTAH', 'UTH'], ['NY', 'NYK', 'NYA'], ['GS', 'GSW', 'GOL'],
    ['NO', 'NOP', 'NOR'], ['SA', 'SAS', 'SAN'], ['PHO', 'PHX'], ['WAS', 'WSH'], ['CHA', 'CHO'],
    ['BKN', 'BRK', 'BK'], ['LAL'], ['LAC'], 
    ['TOR'], ['MEM'], ['MIA'], ['ORL'], ['MIN'], ['MIL'], ['DAL'], ['DEN'], ['HOU'], 
    ['DET'], ['IND'], ['CLE'], ['CHI'], ['ATL'], ['BOS'], ['OKC'], ['POR'], ['SAC']
]

def son_mismo_equipo(eq1, eq2):
    r, a = str(eq1).strip().upper(), str(eq2).strip().upper()
    if r == a: return True
    for g in GRUPOS_EQUIPOS:
        if r in g and a in g: return True
    return False

def check_match(eq_roster, lista_api):
    for eq_api in lista_api:
        if son_mismo_equipo(eq_roster, eq_api): return eq_api
    return None

@st.cache_data(ttl=3600) 
def get_data_semanal():
    hoy = datetime.now()
    lunes = hoy - timedelta(days=hoy.weekday())
    calendario = {}
    hoy_str = hoy.strftime("%Y%m%d")
    equipos_hoy_detalle = []
    rivales_map = {}

    for i in range(7):
        d = lunes + timedelta(days=i)
        d_str = d.strftime("%Y%m%d"); d_fmt = d.strftime("%a %d")
        try:
            data = requests.get(f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d_str}", timeout=3).json()
            eqs = []
            for e in data.get('events', []):
                if d_str == hoy_str:
                    comps = e.get('competitions', [])[0].get('competitors', [])
                    if len(comps) == 2:
                        ta, tb = comps[0]['team']['abbreviation'], comps[1]['team']['abbreviation']
                        rivales_map[ta] = tb; rivales_map[tb] = ta
                        equipos_hoy_detalle.extend([ta, tb])
                for c in e.get('competitions', [])[0].get('competitors', []): 
                    eqs.append(c['team']['abbreviation'])
            calendario[d_fmt] = eqs
        except: calendario[d_fmt] = []
    return calendario, equipos_hoy_detalle, rivales_map

@st.cache_data(ttl=21600)
def get_sos_map():
    try:
        d = requests.get("http://site.api.espn.com/apis/site/v2/sports/basketball/nba/standings", timeout=3).json()
        sos = {}
        for c in d.get('children', []):
            for team in c.get('standings', {}).get('entries', []):
                abbr = team['team']['abbreviation']
                for s in team.get('stats', []):
                    if s.get('name') == 'winPercent': sos[abbr] = s.get('value', 0.5); break
        return sos
    except: return {}

def get_sos_icon(opponent, sos_map):
    if not opponent: return ""
    win_pct = sos_map.get(opponent, 0.5)
    if win_pct > 0.60: return "🔴" 
    if win_pct < 0.40: return "🟢" 
    return "⚪"

def get_ownership(liga):
    try:
        url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{liga.year}/segments/0/leagues/{liga.league_id}"
        filters = {"players": {"filterStatus": {"value": ["FREEAGENT","WAIVERS"]}, "limit": 500, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
        headers = {'x-fantasy-filter': json.dumps(filters)}
        r = requests.get(url, params={'view': 'kona_player_info'}, headers=headers, cookies=liga.espn_request.cookies, timeout=5)
        data = r.json()
        return {p['id']: p['player']['ownership'] for p in data.get('players', [])}
    except: return {}

def get_news():
    """Versión BLINDADA de Noticias V8.3"""
    try:
        url = "https://www.espn.com/espn/rss/nba/news"
        # Headers para simular navegador real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        response = requests.get(url, headers=headers, timeout=4)
        
        if response.status_code != 200:
            return []
            
        root = ET.fromstring(response.content)
        items = []
        # Intentamos leer items, si falla XML, capturamos
        for i in root.findall('./channel/item')[:6]:
            try:
                title = i.find('title')
                link = i.find('link')
                pubDate = i.find('pubDate')
                
                if title is not None and link is not None:
                    items.append({
                        't': title.text, 
                        'l': link.text, 
                        'd': pubDate.text if pubDate is not None else ""
                    })
            except:
                continue # Salta noticia corrupta individualmente
        return items
    except Exception: 
        return [] # Si falla todo, retorna lista vacía y NO crashea

def get_league_activity(liga):
    try:
        activity = liga.recent_activity(size=15)
        logs = []
        for act in activity:
            if hasattr(act, 'actions'):
                for a in act.actions:
                    team = a[0].team_name if hasattr(a[0], 'team_name') else str(a[0])
                    player = a[2].name if hasattr(a[2], 'name') else str(a[2])
                    logs.append({'Fecha': datetime.fromtimestamp(act.date/1000).strftime('%d %H:%M'), 'Eq': team, 'Act': a[1], 'Jug': player})
        return pd.DataFrame(logs)
    except: return pd.DataFrame()

def calc_score(player, config, season_id):
    s = player.stats.get(f"{season_id}_total", {}).get('avg', {}) or player.stats.get(f"{season_id}_projected", {}).get('avg', {})
    score = s.get('PTS',0) + s.get('REB',0)*1.2 + s.get('AST',0)*1.5 + s.get('STL',0)*2 + s.get('BLK',0)*2
    if 'DD' in config['categorias']: score += s.get('DD', 0) * 5
    return score, s

def calc_matchup_totals(lineup):
    t = {k: 0 for k in ['PTS','REB','AST','STL','BLK','3PTM','TO','DD','FGM','FGA','FTM','FTA']}
    for p in lineup:
        if p.slot_position in ['BE', 'IR']: continue
        s = p.stats.get('total', {}) or {}
        if not s and p.stats:
             for k, v in p.stats.items():
                if isinstance(v, dict) and 'total' in v: s = v['total']; break
        if not s: continue
        for c in t:
            if c in ['FGM','FGA','FTM','FTA']: t[c] += s.get(c, 0)
            elif c == '3PTM': t[c] += s.get('3PM', s.get('3PTM', 0))
            else: t[c] += s.get(c, 0)
    if t['FGA']: t['FG%'] = t['FGM']/t['FGA']
    if t['FTA']: t['FT%'] = t['FTM']/t['FTA']
    return t

# --- 4. INTERFAZ DE USUARIO (UI) ---

with st.sidebar:
    st.header("⚙️ Configuración")
    nombre_liga = st.selectbox("Liga", list(LIGAS.keys()))
    st.markdown("---")
    limit_slots = st.number_input("Titulares Máximos", 5, 20, 10)
    excluir_out = st.checkbox("Ignorar 'OUT' en Grid", True)
    if st.button("🔄 Refrescar Datos", type="primary"): st.cache_data.clear()

config = LIGAS[nombre_liga]
liga = obtener_liga(nombre_liga)
season_id = config['year']

if not liga: st.error("Error de conexión con ESPN."); st.stop()

box_scores = liga.box_scores()
matchup = next((m for m in box_scores if "Max" in m.home_team.team_name or "Max" in m.away_team.team_name), None)
if not matchup: st.warning("No hay matchup activo esta semana."); st.stop()

soy_home = "Max" in matchup.home_team.team_name
mi_equipo = matchup.home_team if soy_home else matchup.away_team
rival = matchup.away_team if soy_home else matchup.home_team

# HEADER MEJORADO V8.3
st.markdown(f"<div class='league-tag'>{nombre_liga}</div>", unsafe_allow_html=True)
c1, c2, c3 = st.columns([5, 1, 5])
with c1: st.markdown(f"<div class='team-name'>{mi_equipo.team_name}</div>", unsafe_allow_html=True)
with c2: st.markdown("<div class='vs-tag'>VS</div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='team-name'>{rival.team_name}</div>", unsafe_allow_html=True)
st.write("")

# GRID
with st.expander("📅 Planificación Semanal (Grid)", expanded=True):
    cal, hoy_eqs, hoy_rivs = get_data_semanal()
    rows = {"YO": [], "RIVAL": [], "DIFF": []}
    tot_y, tot_r = 0, 0
    
    for dia, eqs in cal.items():
        cy = sum(1 for p in mi_equipo.roster if p.lineupSlot != 'IR' and (not excluir_out or p.injuryStatus != 'OUT') and check_match(p.proTeam, eqs))
        cr = sum(1 for p in rival.roster if p.lineupSlot != 'IR' and (not excluir_out or p.injuryStatus != 'OUT') and check_match(p.proTeam, eqs))
        uy, ur = min(cy, limit_slots), min(cr, limit_slots)
        rows["YO"].append(uy); rows["RIVAL"].append(ur)
        d = uy - ur
        ic = "✅" if d > 0 else "⚠️" if d < 0 else "="
        rows["DIFF"].append(f"{d} {ic}")
        tot_y += uy; tot_r += ur
        
    rows["YO"].append(tot_y); rows["RIVAL"].append(tot_r)
    dt = tot_y - tot_r
    rows["DIFF"].append(f"{dt} {'🔥' if dt > 0 else '💀'}")
    st.dataframe(pd.DataFrame(rows, index=list(cal.keys())+["TOTAL"]).T, use_container_width=True)

# TABS
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🔥 Hoy", "⚔️ Matchup", "🪓 Cortes", "💎 Waiver", "⚖️ Trade", "🕵️ Intel"])
necesidades = []

# 1. FACE-OFF
with tab1:
    sos_map = get_sos_map()
    def get_power(roster):
        l = []
        for p in roster:
            if p.lineupSlot != 'IR' and p.injuryStatus != 'OUT':
                mt = check_match(p.proTeam, hoy_eqs)
                if mt:
                    opp = hoy_rivs.get(mt, "")
                    si = get_sos_icon(opp, sos_map)
                    sc, _ = calc_score(p, config, season_id)
                    l.append({'J': p.name, 'VS': f"{si} {opp}", 'FP': round(sc,1)})
        l = sorted(l, key=lambda x: x['FP'], reverse=True)[:limit_slots]
        return sum(x['FP'] for x in l), l

    my_p, my_l = get_power(mi_equipo.roster)
    rv_p, rv_l = get_power(rival.roster)
    diff_p = my_p - rv_p
    
    c_sc1, c_sc2 = st.columns(2)
    with c_sc1:
        st.markdown(f"<div class='metric-box'><div class='label-txt'>MI PROYECCIÓN</div><div class='{'win-val' if diff_p>=0 else 'lose-val'}'>{round(my_p,1)}</div></div>", unsafe_allow_html=True)
        if my_l: st.dataframe(pd.DataFrame(my_l), use_container_width=True, hide_index=True)
    with c_sc2:
        st.markdown(f"<div class='metric-box'><div class='label-txt'>RIVAL</div><div class='{'win-val' if diff_p<0 else 'lose-val'}'>{round(rv_p,1)}</div></div>", unsafe_allow_html=True)
        if rv_l: st.dataframe(pd.DataFrame(rv_l), use_container_width=True, hide_index=True)

    if diff_p < 0: st.warning(f"Pierdes por {abs(round(diff_p,1))} FP. ¡Busca refuerzos!")

# 2. MATCHUP
with tab2:
    ms = calc_matchup_totals(matchup.home_lineup if soy_home else matchup.away_lineup)
    rs = calc_matchup_totals(matchup.away_lineup if soy_home else matchup.home_lineup)
    dat = []
    w, l, t = 0, 0, 0
    for c in config['categorias']:
        k = '3PTM' if c == '3PTM' and '3PTM' not in ms else c
        m, r = ms.get(k, 0), rs.get(k, 0)
        d = m - r if c != 'TO' else r - m
        if d > 0: stt="🟢"; w+=1
        elif d < 0: stt="🔴"; l+=1; necesidades.append(c)
        else: stt="🟡"; t+=1
        fm = f"{m:.3f}" if c in ['FG%','FT%'] else f"{m:.0f}"
        fr = f"{r:.3f}" if c in ['FG%','FT%'] else f"{r:.0f}"
        dat.append([c, fm, fr, f"{d:.2f}", stt])
    st.info(f"Marcador: {w}-{l}-{t} | Faltan: {', '.join(necesidades)}")
    st.dataframe(pd.DataFrame(dat, columns=['Cat','Yo','Riv','Dif','W']), use_container_width=True, hide_index=True)

# 3. CORTES
with tab3:
    rost_data = []
    active_roster = [p for p in mi_equipo.roster if p.lineupSlot != 'IR']
    sel_p = st.selectbox("Gráfico:", [p.name for p in active_roster], index=None, placeholder="Elige jugador...")
    for p in active_roster:
        sc, s = calc_score(p, config, season_id)
        ic = "⛔" if p.injuryStatus == 'OUT' else "⚠️" if p.injuryStatus == 'DAY_TO_DAY' else "✅"
        rost_data.append({'J': p.name, 'St': ic, 'Pos': p.lineupSlot, 'Score': round(sc,1), 'Min': round(s.get('MIN',0),1)})
    st.dataframe(pd.DataFrame(rost_data).sort_values('Score'), use_container_width=True, hide_index=True)
    
    if sel_p:
        po = next((p for p in active_roster if p.name == sel_p), None)
        if po:
            avgs = lambda k: po.stats.get(f"{season_id}_{k}", {}).get('avg', {}).get('PTS', 0)
            chart = {'Season': avgs('total'), 'L30': avgs('last_30'), 'L15': avgs('last_15'), 'L7': avgs('last_7')}
            st.line_chart(pd.DataFrame({'PTS': chart.values()}, index=chart.keys()))

# 4. WAIVER
with tab4:
    c1, c2 = st.columns(2)
    min_m = c1.number_input("Minutos >", 10, 40, 22)
    s_hoy = c2.checkbox("Juegan HOY", True)
    sort_by = st.selectbox("Ordenar:", ["Score (Rendimiento)", "Trend (Hype)", "FPPM (Eficiencia)"])
    
    if st.button("🔎 Escanear Mercado"):
        with st.spinner("Analizando..."):
            own = get_ownership(liga)
            sos_map = get_sos_map()
            fa = liga.free_agents(size=150)
            w_list = []
            for p in fa:
                if getattr(p, 'acquisitionType', []) or p.injuryStatus == 'OUT': continue
                mt = check_match(p.proTeam, hoy_eqs)
                if s_hoy and not mt: continue
                sc, s = calc_score(p, config, season_id)
                if not s or sc < 5: continue
                mpg = s.get('MIN', 0)
                if mpg < min_m: continue
                
                riv = hoy_rivs.get(mt, "") if mt else ""
                si = get_sos_icon(riv, sos_map)
                od = own.get(p.playerId, {})
                pch = od.get('percentChange', 0.0); pop = od.get('percentOwned', 0.0)
                ti = "🔥🔥" if pch>2 else "🔥" if pch>0.5 else "📈" if pch>0 else "❄️"
                
                cats_hit = [c for c in necesidades if s.get(c,0) > 0]
                if necesidades: sc += len(cats_hit) * 10
                if pch > 1.5: sc += 15
                
                std = s.get('PTS',0)+s.get('REB',0)*1.2+s.get('AST',0)*1.5+s.get('STL',0)*2+s.get('BLK',0)*2
                fppm = sc/mpg if mpg>0 else 0
                ei = "💎" if fppm > 1.1 else ""
                
                w_list.append({'Nombre': p.name, 'Eq': p.proTeam, 'VS': f"{si} {riv}", 
                               'Trend': f"{ti} {pch:+.1f}%", 'Score': round(sc,1), 'FPPM': f"{ei}{fppm:.2f}", 
                               'Aporta': ",".join(cats_hit) if cats_hit else "-", '_tr': pch, '_fp': fppm})
            
            if w_list:
                df = pd.DataFrame(w_list)
                if sort_by == "Trend (Hype)": df = df.sort_values('_tr', ascending=False)
                elif sort_by == "FPPM (Eficiencia)": df = df.sort_values('_fp', ascending=False)
                else: df = df.sort_values('Score', ascending=False)
                st.dataframe(df[['Nombre','Eq','VS','Trend','Score','FPPM','Aporta']].head(25), use_container_width=True, hide_index=True)
            else: st.info("Sin resultados.")

# 5. TRADE
with tab5:
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
with tab6:
    st.subheader("🕵️ Actividad")
    try:
        df_act = get_league_activity(liga)
        if not df_act.empty and 'Error' not in df_act.columns: st.dataframe(df_act, use_container_width=True, hide_index=True)
        else: st.info("Sin movimientos.")
    except: pass
    st.divider()
    st.subheader("📰 Noticias")
    # Llamada segura a noticias
    news_list = get_nba_news()
    if news_list:
        for n in news_list:
            st.markdown(f"<div class='news-card'><a class='news-title' href='{n['l']}' target='_blank'>{n['t']}</a><div class='news-date'>{n['d']}</div></div>", unsafe_allow_html=True)
    else:
        st.info("No hay noticias disponibles.")

st.caption("🚀 Fantasy GM Architect v8.3 | Final Fix")