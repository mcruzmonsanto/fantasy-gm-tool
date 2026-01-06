"""Fantasy GM Pro - Herramienta de análisis para ligas de fantasy basketball

Autor: Max
Versión: 2.0 - The Refactor
Última actualización: 2026-01-06

Mejoras v2.0:
- Separación de funciones: get_calendario_semanal() y get_partidos_hoy()
- Zona horaria Eastern (ESPN)
- Normalización robusta de equipos
- Eliminación de código obsoleto
- Cache optimizado
"""

import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import pytz
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. CONFIGURACIÓN ---
from src.conectar import obtener_liga
from config.credenciales import LIGAS

st.set_page_config(
    page_title="Fantasy GM Pro",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Zona horaria Eastern (ESPN usa ET)
TIMEZONE = pytz.timezone('US/Eastern')

# --- 2. CSS OPTIMIZADO (SCROLL FIX) ---
st.markdown("""
<style>
    /* Padding ajustado para móvil sin romper el scroll */
    .main .block-container {
        padding-top: 4rem;
        padding-bottom: 2rem;
    }
    
    .stDataFrame {border: 1px solid #333; border-radius: 5px;}
    .team-name {font-size: 1.1rem; font-weight: 700; text-align: center; margin-bottom: 0;}
    .vs-tag {font-size: 0.9rem; color: #ff4b4b; text-align: center; font-weight: 800; margin-top: 5px;}
    .league-tag {font-size: 0.8rem; color: #aaa; text-align: center; text-transform: uppercase; letter-spacing: 1px;}
    
    .metric-box {
        background-color: #181818; border: 1px solid #333; border-radius: 8px; 
        padding: 15px; text-align: center;
    }
    .win-val {color: #4caf50; font-size: 1.6rem; font-weight: 900;}
    .lose-val {color: #f44336; font-size: 1.6rem; font-weight: 900;}
    
    .news-card {
        background-color: #262730; padding: 12px; border-radius: 6px; 
        margin-bottom: 8px; border-left: 3px solid #ff4b4b;
    }
    .news-title {font-weight: 600; color: #fff; text-decoration: none; font-size: 0.9rem;}
    .news-date {color: #888; font-size: 0.7rem; margin-top: 4px;}
</style>
""", unsafe_allow_html=True)

# --- 3. MOTOR DE DATOS ---

# Mapeo maestro: ESPN API -> Código estándar de 3 letras
ESPN_TO_STANDARD = {
    'PHI': 'PHI', 'PHL': 'PHI', '76ERS': 'PHI',
    'UTA': 'UTA', 'UTAH': 'UTA', 'UTH': 'UTA',
    'NY': 'NYK', 'NYK': 'NYK', 'NYA': 'NYK',
    'GS': 'GSW', 'GSW': 'GSW', 'GOL': 'GSW',
    'NO': 'NOP', 'NOP': 'NOP', 'NOR': 'NOP',
    'SA': 'SAS', 'SAS': 'SAS', 'SAN': 'SAS',
    'PHO': 'PHX', 'PHX': 'PHX',
    'WAS': 'WAS', 'WSH': 'WAS',
    'CHA': 'CHA', 'CHO': 'CHA',
    'BKN': 'BKN', 'BRK': 'BKN', 'BK': 'BKN',
    'LAL': 'LAL', 'LAC': 'LAC',
    'TOR': 'TOR', 'MEM': 'MEM', 'MIA': 'MIA', 'ORL': 'ORL',
    'MIN': 'MIN', 'MIL': 'MIL', 'DAL': 'DAL', 'DEN': 'DEN',
    'HOU': 'HOU', 'DET': 'DET', 'IND': 'IND', 'CLE': 'CLE',
    'CHI': 'CHI', 'ATL': 'ATL', 'BOS': 'BOS', 'OKC': 'OKC',
    'POR': 'POR', 'SAC': 'SAC'
}

# BACKUP SOS (Actualizado)
BACKUP_SOS = {
    'BOS': 0.80, 'OKC': 0.75, 'DEN': 0.70, 'MIN': 0.70, 'LAC': 0.65, 'CLE': 0.65,
    'NYK': 0.60, 'PHX': 0.60, 'MIL': 0.60, 'NOP': 0.60, 'PHI': 0.55, 'DAL': 0.55,
    'SAC': 0.55, 'IND': 0.55, 'MIA': 0.55, 'ORL': 0.55, 'LAL': 0.50, 'GSW': 0.50,
    'HOU': 0.45, 'CHI': 0.45, 'ATL': 0.40, 'UTA': 0.40, 'BKN': 0.35, 'TOR': 0.30,
    'MEM': 0.30, 'POR': 0.25, 'CHA': 0.25, 'SAS': 0.20, 'WAS': 0.15, 'DET': 0.15
}

# --- FUNCIONES DE NORMALIZACIÓN ---

def normalizar_equipo(abrev):
    """Convierte cualquier variante a formato estándar (GS -> GSW, SA -> SAS)"""
    if not abrev:
        return ""
    s = str(abrev).strip().upper()
    return ESPN_TO_STANDARD.get(s, s)

def equipos_match(eq1, eq2):
    """Verifica si dos equipos son el mismo (normalizado)"""
    return normalizar_equipo(eq1) == normalizar_equipo(eq2)

def jugador_juega_hoy(pro_team, equipos_hoy_list):
    """
    Verifica si el jugador juega hoy
    - pro_team: str, equipo del jugador (ej: 'GS')
    - equipos_hoy_list: list, equipos que juegan (ej: ['GSW', 'LAL'])
    """
    norm_team = normalizar_equipo(pro_team)
    return norm_team in [normalizar_equipo(eq) for eq in equipos_hoy_list]

# --- FUNCIONES DE DATOS ---

@st.cache_data(ttl=1800)  # 30 minutos - para el grid semanal
def get_calendario_semanal():
    """
    Obtiene calendario semanal de partidos NBA desde ESPN API.
    
    Returns:
        dict: {"Lun 06": ["GSW", "LAL", ...], "Mar 07": [...], ...}
              Equipos normalizados que juegan cada día de la semana.
    
    Raises:
        No lanza excepciones. Retorna lista vacía para días con error.
    """
    try:
        ahora = datetime.now(TIMEZONE)
        lunes = ahora - timedelta(days=ahora.weekday())
        calendario = {}
        
        logger.info(f"Cargando calendario semanal desde {lunes.strftime('%Y-%m-%d')}")
        
        for i in range(7):
            d = lunes + timedelta(days=i)
            d_str = d.strftime("%Y%m%d")
            d_fmt = d.strftime("%a %d")
            
            try:
                url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d_str}"
                response = requests.get(url, timeout=5)
                response.raise_for_status()  # Lanza excepción si status != 200
                
                data = response.json()
                equipos_dia = []
                
                eventos = data.get('events', [])
                if not eventos:
                    logger.info(f"No hay partidos el {d_fmt}")
                
                for evento in eventos:
                    comps = evento.get('competitions', [])
                    if not comps:
                        continue
                    
                    competitors = comps[0].get('competitors', [])
                    for comp in competitors:
                        team_data = comp.get('team', {})
                        abrev = team_data.get('abbreviation', '')
                        
                        if abrev:
                            equipo_norm = normalizar_equipo(abrev)
                            if equipo_norm not in equipos_dia:  # Evitar duplicados
                                equipos_dia.append(equipo_norm)
                
                calendario[d_fmt] = equipos_dia
                logger.debug(f"{d_fmt}: {len(equipos_dia)} equipos")
                
            except requests.RequestException as e:
                logger.error(f"Error API para {d_fmt}: {e}")
                calendario[d_fmt] = []
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                logger.error(f"Error parseando datos para {d_fmt}: {e}")
                calendario[d_fmt] = []
        
        return calendario
        
    except Exception as e:
        logger.error(f"Error crítico en get_calendario_semanal: {e}")
        # Retornar calendario vacío en caso de error total
        return {f"{(datetime.now(TIMEZONE) - timedelta(days=datetime.now(TIMEZONE).weekday()) + timedelta(days=i)).strftime('%a %d')}": [] for i in range(7)}

@st.cache_data(ttl=900)  # 15 minutos - más frecuente para HOY
def get_partidos_hoy():
    """
    Obtiene partidos de HOY desde ESPN API.
    
    Returns:
        tuple: (equipos_hoy: list, rivales_map: dict)
            - equipos_hoy: Lista de equipos que juegan hoy (normalizados)
            - rivales_map: Diccionario {equipo: rival} para matchups
    
    Example:
        >>> equipos, rivales = get_partidos_hoy()
        >>> print(equipos)  # ['GSW', 'LAL', 'BOS', 'MIA']
        >>> print(rivales)  # {'GSW': 'LAL', 'LAL': 'GSW', 'BOS': 'MIA', 'MIA': 'BOS'}
    """
    try:
        ahora = datetime.now(TIMEZONE)
        hoy_str = ahora.strftime("%Y%m%d")
        equipos_hoy = []
        rivales_map = {}
        
        logger.info(f"Cargando partidos de hoy: {hoy_str}")
        
        url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={hoy_str}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        eventos = data.get('events', [])
        
        if not eventos:
            logger.warning(f"No hay partidos hoy ({hoy_str})")
            return [], {}
        
        for evento in eventos:
            comps = evento.get('competitions', [])
            if not comps:
                continue
            
            competitors = comps[0].get('competitors', [])
            
            if len(competitors) == 2:
                # Extraer y normalizar equipos
                team_a_data = competitors[0].get('team', {})
                team_b_data = competitors[1].get('team', {})
                
                abrev_a = team_a_data.get('abbreviation', '')
                abrev_b = team_b_data.get('abbreviation', '')
                
                if not abrev_a or not abrev_b:
                    logger.warning(f"Partido sin abreviaturas válidas: {team_a_data}, {team_b_data}")
                    continue
                
                eq_a = normalizar_equipo(abrev_a)
                eq_b = normalizar_equipo(abrev_b)
                
                # Agregar a lista de equipos (sin duplicados)
                if eq_a not in equipos_hoy:
                    equipos_hoy.append(eq_a)
                if eq_b not in equipos_hoy:
                    equipos_hoy.append(eq_b)
                
                # Mapear rivales
                rivales_map[eq_a] = eq_b
                rivales_map[eq_b] = eq_a
        
        logger.info(f"Partidos hoy: {len(equipos_hoy)//2} juegos, {len(equipos_hoy)} equipos")
        return equipos_hoy, rivales_map
        
    except requests.RequestException as e:
        logger.error(f"Error de red en get_partidos_hoy: {e}")
        return [], {}
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error parseando datos de hoy: {e}")
        return [], {}
    except Exception as e:
        logger.error(f"Error crítico en get_partidos_hoy: {e}")
        return [], {}

@st.cache_data(ttl=21600)  # 6 horas - standings cambian lento
def get_sos_map():
    """
    Obtiene Strength of Schedule (SOS) basado en win percentage.
    Intenta API de ESPN, si falla usa valores de backup.
    
    Returns:
        dict: {"GSW": 0.65, "LAL": 0.50, ...} - Win percentage por equipo
    """
    sos = {}
    
    try:
        logger.info("Cargando SOS desde ESPN API")
        url = "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/standings"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        for conference in data.get('children', []):
            for team in conference.get('standings', {}).get('entries', []):
                abbr = team.get('team', {}).get('abbreviation', '')
                if not abbr:
                    continue
                
                # Buscar winPercent en stats
                for stat in team.get('stats', []):
                    if stat.get('name') == 'winPercent':
                        win_pct = stat.get('value', 0.5)
                        sos[normalizar_equipo(abbr)] = win_pct
                        break
        
        logger.info(f"SOS cargado para {len(sos)} equipos desde API")
        
    except requests.RequestException as e:
        logger.warning(f"Error API de standings: {e}. Usando backup.")
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.warning(f"Error parseando standings: {e}. Usando backup.")
    
    # Fusionar con backup (para equipos faltantes o si API falló)
    equipos_faltantes = 0
    for equipo, win_pct in BACKUP_SOS.items():
        if equipo not in sos:
            sos[equipo] = win_pct
            equipos_faltantes += 1
    
    if equipos_faltantes > 0:
        logger.info(f"Agregados {equipos_faltantes} equipos desde backup SOS")
    
    return sos

def get_sos_icon(opponent, sos_map):
    """
    Retorna icono de dificultad basado en win percentage del rival.
    
    Args:
        opponent: Abreviatura del equipo rival
        sos_map: Diccionario de win percentages
    
    Returns:
        str: 🔴 (difícil >=60%), 🟢 (fácil <=40%), ⚪ (medio)
    """
    if not opponent:
        return "⚪"
    
    opp_norm = normalizar_equipo(opponent)
    win_pct = sos_map.get(opp_norm, 0.5)  # Default 0.5 si no existe
    
    if win_pct >= 0.60:
        return "🔴"  # Rival fuerte
    elif win_pct <= 0.40:
        return "🟢"  # Rival débil
    else:
        return "⚪"  # Rival promedio

def get_ownership(liga):
    """
    Obtiene datos de ownership (% owned, % change) de free agents.
    
    Args:
        liga: Objeto de liga de espn_api
    
    Returns:
        dict: {player_id: {'percentOwned': float, 'percentChange': float}}
    """
    try:
        url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{liga.year}/segments/0/leagues/{liga.league_id}"
        filters = {
            "players": {
                "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
                "limit": 500,
                "sortPercOwned": {"sortPriority": 1, "sortAsc": False}
            }
        }
        headers = {'x-fantasy-filter': json.dumps(filters)}
        
        response = requests.get(
            url,
            params={'view': 'kona_player_info'},
            headers=headers,
            cookies=liga.espn_request.cookies,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        ownership_data = {}
        
        for player in data.get('players', []):
            player_id = player.get('id')
            ownership = player.get('player', {}).get('ownership', {})
            
            if player_id and ownership:
                ownership_data[player_id] = ownership
        
        logger.info(f"Ownership cargado para {len(ownership_data)} jugadores")
        return ownership_data
        
    except requests.RequestException as e:
        logger.error(f"Error obteniendo ownership: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error crítico en get_ownership: {e}")
        return {}

def get_news_safe():
    try:
        r = requests.get("https://www.espn.com/espn/rss/nba/news", headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        if r.status_code != 200: return []
        root = ET.fromstring(r.content)
        items = []
        for i in root.findall('./channel/item')[:6]:
            t = i.find('title'); l = i.find('link'); d = i.find('pubDate')
            if t is not None and l is not None:
                items.append({'t': t.text, 'l': l.text, 'd': d.text if d is not None else ""})
        return items
    except: return []

def get_league_activity(liga):
    try:
        activity = liga.recent_activity(size=15)
        logs = []
        for act in activity:
            if hasattr(act, 'actions'):
                for a in act.actions:
                    try:
                        tm = a[0].team_name if hasattr(a[0], 'team_name') else str(a[0])
                        pl = a[2].name if hasattr(a[2], 'name') else str(a[2])
                        logs.append({'Fecha': datetime.fromtimestamp(act.date/1000).strftime('%d %H:%M'), 'Eq': tm, 'Act': a[1], 'Jug': pl})
                    except: continue
        return pd.DataFrame(logs)
    except: return pd.DataFrame()

def calc_score(player, config, season_id):
    s = player.stats.get(f"{season_id}_total", {}).get('avg', {}) 
    if not s: s = player.stats.get(f"{season_id}_projected", {}).get('avg', {})
    if not s: s = player.stats.get(f"{season_id}_last_15", {}).get('avg', {})
    
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

# --- 4. UI ---

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

if not liga: st.error("Error de conexión"); st.stop()

box_scores = liga.box_scores()
matchup = next((m for m in box_scores if "Max" in m.home_team.team_name or "Max" in m.away_team.team_name), None)
if not matchup: st.warning("No hay matchup activo."); st.stop()

soy_home = "Max" in matchup.home_team.team_name
mi_equipo = matchup.home_team if soy_home else matchup.away_team
rival = matchup.away_team if soy_home else matchup.home_team

# HEADER
st.markdown(f"<div class='league-tag'>{nombre_liga}</div>", unsafe_allow_html=True)
c1, c2, c3 = st.columns([5, 1, 5])
with c1: st.markdown(f"<div class='team-name'>{mi_equipo.team_name}</div>", unsafe_allow_html=True)
with c2: st.markdown("<div class='vs-tag'>VS</div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='team-name'>{rival.team_name}</div>", unsafe_allow_html=True)
st.write("")

# GRID
with st.expander("📅 Planificación Semanal (Grid)", expanded=True):
    calendario = get_calendario_semanal()
    rows = {"YO": [], "RIVAL": [], "DIFF": []}
    tot_y, tot_r = 0, 0
    
    for dia, equipos_dia in calendario.items():
        # Contar jugadores que juegan este día específico
        cy = sum(
            1 for p in mi_equipo.roster 
            if p.lineupSlot != 'IR' 
            and (not excluir_out or p.injuryStatus != 'OUT') 
            and jugador_juega_hoy(p.proTeam, equipos_dia)
        )
        cr = sum(
            1 for p in rival.roster 
            if p.lineupSlot != 'IR' 
            and (not excluir_out or p.injuryStatus != 'OUT') 
            and jugador_juega_hoy(p.proTeam, equipos_dia)
        )
        uy, ur = min(cy, limit_slots), min(cr, limit_slots)
        rows["YO"].append(uy); rows["RIVAL"].append(ur)
        d = uy - ur
        ic = "✅" if d > 0 else "⚠️" if d < 0 else "="
        rows["DIFF"].append(f"{d} {ic}")
        tot_y += uy; tot_r += ur
        
    rows["YO"].append(tot_y); rows["RIVAL"].append(tot_r)
    dt = tot_y - tot_r
    rows["DIFF"].append(f"{dt} {'🔥' if dt > 0 else '💀'}")
    st.dataframe(pd.DataFrame(rows, index=list(calendario.keys())+["TOTAL"]).T, use_container_width=True)

# TABS
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🔥 Hoy", "⚔️ Matchup", "🪓 Cortes", "💎 Waiver", "⚖️ Trade", "🕵️ Intel"])
necesidades = []

# 1. FACE-OFF (ARREGLADO: 0 vs 0 FIX + SEMÁFORO BACKUP)
with tab1:
    equipos_hoy, rivales_hoy = get_partidos_hoy()
    sos_map = get_sos_map()
    
    def get_power(roster):
        l = []
        for p in roster:
            if p.lineupSlot != 'IR' and p.injuryStatus != 'OUT':
                if jugador_juega_hoy(p.proTeam, equipos_hoy):
                    norm_team = normalizar_equipo(p.proTeam)
                    opp = rivales_hoy.get(norm_team, "")
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
        st.markdown(f"<div class='metric-box'><div class='label-txt'>YO</div><div class='{'win-val' if diff_p>=0 else 'lose-val'}'>{round(my_p,1)}</div></div>", unsafe_allow_html=True)
        if my_l: st.dataframe(pd.DataFrame(my_l), use_container_width=True, hide_index=True)
    with c_sc2:
        st.markdown(f"<div class='metric-box'><div class='label-txt'>RIVAL</div><div class='{'win-val' if diff_p<0 else 'lose-val'}'>{round(rv_p,1)}</div></div>", unsafe_allow_html=True)
        if rv_l: st.dataframe(pd.DataFrame(rv_l), use_container_width=True, hide_index=True)

    st.divider()
    if diff_p < 0:
        brecha = abs(diff_p)
        st.error(f"⚠️ Pierdes por -{round(brecha,1)} FP.")
        if st.button("🚑 BUSCAR RESCATE"):
            with st.spinner("Buscando..."):
                own_data = get_ownership(liga)
                fa = liga.free_agents(size=100)
                rescate = []
                for p in fa:
                    if getattr(p, 'acquisitionType', []) or p.injuryStatus == 'OUT': continue
                    if not jugador_juega_hoy(p.proTeam, equipos_hoy): continue
                    sc, s = calc_score(p, config, season_id)
                    if sc > 15:
                        di = sc - brecha
                        ic = "🦸‍♂️" if di > 0 else "🩹"
                        norm_team = normalizar_equipo(p.proTeam)
                        opp = rivales_hoy.get(norm_team, "")
                        si = get_sos_icon(opp, sos_map)
                        rescate.append({'Jugador': p.name, 'Eq': p.proTeam, 'VS': f"{si} {opp}", 'Score': round(sc,1), 'Impacto': f"{ic} {round(di,1)}"})
                if rescate: st.dataframe(pd.DataFrame(rescate).sort_values('Score', ascending=False).head(5), use_container_width=True, hide_index=True)
                else: st.warning("Mercado seco.")

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
    sort_by = st.selectbox("Ordenar:", ["Score", "Hype", "FPPM"])
    
    if st.button("🔎 Escanear"):
        with st.spinner("Analizando..."):
            equipos_hoy, rivales_hoy = get_partidos_hoy()
            own = get_ownership(liga)
            sos_map = get_sos_map()
            fa = liga.free_agents(size=150)
            w_list = []
            for p in fa:
                if getattr(p, 'acquisitionType', []) or p.injuryStatus == 'OUT': continue
                juega_hoy = jugador_juega_hoy(p.proTeam, equipos_hoy)
                if s_hoy and not juega_hoy: continue
                sc, s = calc_score(p, config, season_id)
                if not s or sc < 5: continue
                mpg = s.get('MIN', 0)
                if mpg < min_m: continue
                
                norm_team = normalizar_equipo(p.proTeam)
                riv = rivales_hoy.get(norm_team, "") if juega_hoy else ""
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
                if sort_by == "Trend": df = df.sort_values('_tr', ascending=False)
                elif sort_by == "FPPM": df = df.sort_values('_fp', ascending=False)
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
        if not df_act.empty: st.dataframe(df_act, use_container_width=True, hide_index=True)
        else: st.info("Sin movimientos.")
    except: pass
    st.divider()
    st.subheader("📰 Noticias")
    news_list = get_news_safe()
    if news_list:
        for n in news_list:
            st.markdown(f"<div class='news-card'><a class='news-title' href='{n['l']}' target='_blank'>{n['t']}</a><div class='news-date'>{n['d']}</div></div>", unsafe_allow_html=True)
    else: st.info("Noticias no disponibles.")

# --- FOOTER ESPACIADOR PARA MÓVIL ---
st.write("<br><br><br>", unsafe_allow_html=True) 
st.caption("🚀 Fantasy GM Architect v10.1 | The Hotfix")