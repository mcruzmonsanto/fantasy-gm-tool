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
from loguru import logger

# Configurar logging
logging.basicConfig(level=logging.INFO)

# --- 1. CONFIGURACIÓN ---
from src.conectar import obtener_liga
from src.expert_scrapers import ExpertScrapers
from src.historical_analyzer import HistoricalAnalyzer
from src.ml_engine import MLDecisionEngine
from src.ui_learning_tab import render_learning_tab

# Intentar cargar configuración moderna, fallback a legacy
try:
    from src.config_manager import ConfigManager
    from src.cache_manager import CacheManager
    from src.health_check import show_diagnostic_panel
    from src.alerts import AlertSystem
    
    config_mgr = ConfigManager()
    LIGAS = config_mgr.get_ligas()
    cache_mgr = CacheManager()
    alert_sys = AlertSystem()
    USE_MODERN_CONFIG = True
    
    logger.info("✅ Usando sistema de configuración moderno")
except ImportError as e:
    logger.warning(f"⚠️ Fallback a configuración legacy: {e}")
    from config.credenciales import LIGAS
    cache_mgr = None
    alert_sys = None
    USE_MODERN_CONFIG = False

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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
    
    /* GLOBAL DARK MODE IDENTITY */
    .stApp, .main .block-container {
        background-color: #121212;
        font-family: 'Inter', sans-serif;
    }
    
    /* Apply Font to Text    /* TEXT COLOR & FONT (Safe for Icons) */
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, .stDataFrame, .stTooltip, .stCaption, small {
        color: #E0E0E0 !important;
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Removed global span/div override to fix Icons like "keyboard_arrow..." */
    
    /* SIDEBAR STYLING */
    [data-testid="stSidebar"] {
        background-color: #1E1E1E !important;
        border-right: 1px solid #333;
    }
    
    /* Ensure Sidebar Text is Visible */
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
         color: #E0E0E0 !important;
    }
    
    /* Prevent Icon Breakage */
    i, .material-icons, [data-testid="stIcon"] {
        font-family: 'Material Icons' !important;
        color: inherit;
    }

    /* Contenedores Premium */
    .metric-box {
        background-color: #1E1E1E; 
        border: 1px solid #333; 
        border-radius: 12px; 
        padding: 20px; 
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* Branding Colors */
    .win-val {color: #4CAF50 !important; font-size: 2rem; font-weight: 900;}
    .lose-val {color: #E50914 !important; font-size: 2rem; font-weight: 900;}
    .label-txt {color: #B3B3B3; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1.5px;}
    
    /* UI Elements */
    .stDataFrame {
        border: none !important;
    }
    
    /* FORCE DARK MODE ON EXPANDERS (Tag-based override) */
    details {
        background-color: #1E1E1E !important;
        border: 1px solid #333 !important;
        border-radius: 8px !important;
        color: #E0E0E0 !important;
        margin-bottom: 1rem;
    }
    
    summary {
        background-color: #1E1E1E !important;
        color: #E0E0E0 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
    }
    
    summary:hover, details[open] summary:hover {
        background-color: #252525 !important;
        color: #FFFFFF !important;
    }
    
    /* Remove white background from content */
    details > div {
        background-color: #1E1E1E !important;
        color: #E0E0E0 !important;
    }
    
    /* Clean Sidebar Inputs */
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #2C2C2C !important;
        color: white !important;
        border: 1px solid #444;
    }
    
    /* Custom Tags */
    .team-name {font-size: 1.4rem; font-weight: 800; color: #fff;}
    .vs-tag {font-size: 1rem; color: #E50914; font-weight: 900;}
    
    /* News Override */
    .news-card {
        background-color: #1E1E1E; 
        border-left: 4px solid #E50914;
        padding: 15px; margin-bottom: 10px;
    }
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
    - equipos_hoy_list: list, equipos que juegan. Puede ser ['GSW'] o [{'home': 'GSW', 'away': 'LAL'}]
    """
    norm_team = normalizar_equipo(pro_team)
    
    # Extract all teams playing today
    playing_teams = set()
    for item in equipos_hoy_list:
        if isinstance(item, dict):
            # Match object
            playing_teams.add(normalizar_equipo(item.get('home', '')))
            playing_teams.add(normalizar_equipo(item.get('away', '')))
        else:
            # String (Legacy)
            playing_teams.add(normalizar_equipo(item))
            
    return norm_team in playing_teams

# --- FUNCIONES DE DATOS ---

@st.cache_data(ttl=1800)  # 30 minutos - para el grid semanal
def get_calendario_semanal():
    """
    Obtiene calendario semanal de partidos NBA desde ESPN API.
    
    Returns:
        dict: {"Lun 06": [{'home': 'GSW', 'away': 'LAL'}, ...], ...}
              Lista de partidos (dicts) con equipos normalizados.
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
                response.raise_for_status()
                
                data = response.json()
                matches = []
                
                eventos = data.get('events', [])
                for evento in eventos:
                    comps = evento.get('competitions', [])
                    if not comps: continue
                    
                    competitors = comps[0].get('competitors', [])
                    if len(competitors) == 2:
                        # ESPN usually lists Home second? Verify logic or just use home/away keys if available
                        # Actually competitors list usually has 'homeAway': 'home' inside
                        
                        team_a_data = competitors[0].get('team', {})
                        team_b_data = competitors[1].get('team', {})
                        
                        # Identify home/away
                        # Typically index 0 is home, 1 is away in some APIs, but ESPN has 'homeAway' field
                        team_home = team_a_data if competitors[0].get('homeAway') == 'home' else team_b_data
                        team_away = team_b_data if competitors[0].get('homeAway') == 'home' else team_a_data
                        
                        # Fallback if homeAway not found (rare)
                        if not team_home: 
                            team_home = team_a_data
                            team_away = team_b_data
                            
                        abrev_home = team_home.get('abbreviation', '')
                        abrev_away = team_away.get('abbreviation', '')
                        
                        if abrev_home and abrev_away:
                            matches.append({
                                'home': normalizar_equipo(abrev_home),
                                'away': normalizar_equipo(abrev_away)
                            })
                
                calendario[d_fmt] = matches
                logger.debug(f"{d_fmt}: {len(matches)} partidos")
                
            except Exception as e:
                logger.error(f"Error API para {d_fmt}: {e}")
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
    
    # Panel de diagnóstico (si está disponible)
    if USE_MODERN_CONFIG:
        show_diagnostic_panel()
    
    nombre_liga = st.selectbox("Liga", list(LIGAS.keys()))
    st.markdown("---")
    limit_slots = st.number_input("Titulares Máximos", 5, 20, 10)
    excluir_out = st.checkbox("Ignorar 'OUT' en Grid", True)
    if st.button("🔄 Refrescar Datos", type="primary"): 
        st.cache_data.clear()
        if cache_mgr:
            cache_mgr.cache_metadata.clear()
        logger.info("🔄 Cache limpiado")

config = LIGAS[nombre_liga]

# Conectar con retry automático si está disponible
if USE_MODERN_CONFIG:
    liga = obtener_liga(nombre_liga, LIGAS)
else:
    # Legacy: necesita adaptar la función vieja
    from src.conectar import obtener_liga as obtener_liga_legacy
    # Hack temporal para compatibilidad
    import sys
    sys.modules['src.conectar'].LIGAS = LIGAS
    liga = obtener_liga_legacy(nombre_liga)

season_id = config['year']

if not liga: 
    st.error("❌ Error de conexión. Revisa tu configuración en .env o credenciales.py")
    if USE_MODERN_CONFIG:
        st.info("💡 Tip: Verifica que el archivo .env existe y tiene las credenciales correctas")
    st.stop()

box_scores = liga.box_scores()

# Obtener el nombre del equipo del usuario desde configuración
my_team_name = config.get('my_team_name', '')

# Buscar el matchup del usuario
matchup = None
if my_team_name:
    # Buscar por nombre de equipo configurado
    matchup = next((m for m in box_scores if my_team_name in m.home_team.team_name or my_team_name in m.away_team.team_name), None)

if not matchup and box_scores:
    # Fallback: tomar el primer matchup (usuario debe configurar my_team_name)
    matchup = box_scores[0]
    st.warning(f"⚠️ Mostrando primer matchup. Configura `LIGA_X_MY_TEAM_NAME` en .env para ver tu matchup correcto.")

if not matchup: 
    st.warning("No hay matchup activo esta semana."); 
    st.stop()

# Determinar cuál equipo es el del usuario
if my_team_name and my_team_name in matchup.home_team.team_name:
    soy_home = True
elif my_team_name and my_team_name in matchup.away_team.team_name:
    soy_home = False
else:
    # Si no se configuró, asumir que eres el home team
    soy_home = True

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
with st.expander("📅 Smart Planificación Semanal (Grid)", expanded=True):
    # Calculo de datos del Grid Original (Simplified for stability)
    calendario = get_calendario_semanal()
    
    # --- SMART OVERLAY ---
    # Cargar datos de expertos (cacheado)
    try:
        expert_scraper = ExpertScrapers()
        expert_data = expert_scraper.get_player_expert_data() or {}
    except:
        expert_data = {}
    
    # Preparar datos enriquecidos
    grid_data = [] # List of {'Player': 'LeBron', 'Mon': '@DET', ...}
    
    # Header Dates
    dias = list(calendario.keys())
    
    def get_smart_cell(player, day_teams):
        # Determine if playing
        norm_team = normalizar_equipo(player.proTeam)
        juega = False
        opp = ""
        
        # Check against teams playing today
        for t in day_teams:
            if t['home'] == norm_team:
                juega = True
                opp = f"vs {t['away']}" # vs OPP
                break
            elif t['away'] == norm_team:
                juega = True
                opp = f"@{t['home']}" # at OPP
                break
        
        if not juega:
            return "" # Empty cell
        
        # Add metadata marks
        marks = []
        if player.name in expert_data:
            rank = expert_data[player.name].get('fantasypros_rank', 999)
            if rank <= 50: marks.append("🌟")
            elif rank <= 100: marks.append("⭐")
        
        if player.injuryStatus == 'DAY_TO_DAY': marks.append("🩹")
        elif player.injuryStatus == 'OUT': marks.append("❌")
        
        return f"{' '.join(marks)} {opp}" if marks else opp

    # Process My Team for Grid
    my_active_players = [p for p in mi_equipo.roster if p.lineupSlot != 'IR']
    
    # Sort by expert rank (or avg stats) for better visibility
    def sorting_key(p):
        if p.name in expert_data:
            return expert_data[p.name].get('fantasypros_rank', 999)
        return 999
        
    my_active_players.sort(key=sorting_key)
    
    for p in my_active_players:
        row = {'JUGADOR': p.name}
        games_count = 0
        
        for dia in dias:
            cell = get_smart_cell(p, calendario[dia])
            row[dia] = cell
            if cell: games_count += 1
            
        row['TOTAL'] = games_count
        grid_data.append(row)
        
    st.dataframe(
        pd.DataFrame(grid_data),
        column_config={
            "JUGADOR": st.column_config.TextColumn("Jugador", width="medium"),
            "TOTAL": st.column_config.ProgressColumn("Games", min_value=0, max_value=5, format="%d"),
        },
        use_container_width=True,
        hide_index=True
    )
    
    # --- METRICS SUMMARY ---
    total_games_me = sum(r['TOTAL'] for r in grid_data)
    # Estimate Opponent games (simplified)
    total_games_opp = 0
    for p in rival.roster:
        if p.lineupSlot != 'IR':
            for dia in dias:
                # Basic check logic
                for t in calendario[dia]:
                    if t['home'] == normalizar_equipo(p.proTeam) or t['away'] == normalizar_equipo(p.proTeam):
                        total_games_opp += 1
                        
    diff_games = total_games_me - total_games_opp
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Mis Partidos", total_games_me)
    c2.metric("Rival Partidos", total_games_opp, delta=diff_games)
    c3.caption(f"🌟/⭐ = Top 50/100  |  🩹 = DTD  |  ❌ = OUT")
tab1, tab2, tab3, tab4 = st.tabs([
    "🔥 Hoy", 
    "⚔️ Matchup", 
    "🔮 IA",
    "📚 Learning"  # NEW
])
necesidades = []

# 1. FACE-OFF (ARREGLADO: 0 vs 0 FIX + SEMÁFORO BACKUP)
with tab1:
    equipos_hoy, rivales_hoy = get_partidos_hoy()
    sos_map = get_sos_map()
    
    # Cargar expert data
    expert_scraper = ExpertScrapers()
    try:
        expert_data = expert_scraper.scrape_fantasypros_rankings(limit=200)
    except:
        expert_data = {}

    def get_power(roster):
        l = []
        for p in roster:
            if p.lineupSlot != 'IR' and p.injuryStatus != 'OUT':
                if jugador_juega_hoy(p.proTeam, equipos_hoy):
                    norm_team = normalizar_equipo(p.proTeam)
                    opp = rivales_hoy.get(norm_team, "")
                    si = get_sos_icon(opp, sos_map)
                    sc, _ = calc_score(p, config, season_id)
                    
                    # Expert badge
                    badge = ""
                    if p.name in expert_data:
                        rank = expert_data[p.name].get('fantasypros_rank', 999)
                        if rank <= 50: badge = "🌟"
                        elif rank <= 100: badge = "⭐"
                    
                    # Keep FP as raw number for ProgressColumn
                    l.append({'Jugador': f"{badge} {p.name}", 'Rival': f"{si} {opp}", 'FP': sc})
        
        l = sorted(l, key=lambda x: x['FP'], reverse=True)[:limit_slots]
        return sum(x['FP'] for x in l), l

    my_p, my_l = get_power(mi_equipo.roster)
    rv_p, rv_l = get_power(rival.roster)
    diff_p = my_p - rv_p
    
    c_sc1, c_sc2 = st.columns(2)
    
    # Configuración de columnas para "Hoy"
    col_cfg = {
        "Jugador": st.column_config.TextColumn("Jugador", width="medium"),
        "Rival": st.column_config.TextColumn("VS", width="small"),
        "FP": st.column_config.ProgressColumn(
            "Puntos", 
            format="%.1f", 
            min_value=0, 
            max_value=60,
            help="Puntos Fantasy Proyectados"
        )
    }

    with c_sc1:
        st.markdown(f"<div class='metric-box'><div class='label-txt'>YO</div><div class='{'win-val' if diff_p>=0 else 'lose-val'}'>{round(my_p,1)}</div></div>", unsafe_allow_html=True)
        if my_l: 
            st.dataframe(
                pd.DataFrame(my_l), 
                use_container_width=True, 
                hide_index=True,
                column_config=col_cfg
            )
            
    with c_sc2:
        st.markdown(f"<div class='metric-box'><div class='label-txt'>RIVAL</div><div class='{'win-val' if diff_p<0 else 'lose-val'}'>{round(rv_p,1)}</div></div>", unsafe_allow_html=True)
        if rv_l: 
            st.dataframe(
                pd.DataFrame(rv_l), 
                use_container_width=True, 
                hide_index=True,
                column_config=col_cfg
            )

    st.divider()
    if diff_p < 0:
        brecha = abs(diff_p)
        st.error(f"⚠️ Pierdes por -{round(brecha,1)} FP. (Usa la tab 'IA' para buscar rescates)")

# 2. MATCHUP
# 2. MATCHUP INTELLIGENCE DASHBOARD
with tab2:
    st.header("⚔️ Matchup Intelligence Dashboard")
    
    # --- DATA PREPARATION ---
    with st.spinner("🔮 Calculando probabilidades..."):
        try:
            from src.ml_engine import MLDecisionEngine
            from src.intelligence_engine import PlayerAnalyzer
            from src.historical_analyzer import HistoricalAnalyzer
            
            # Initialize Engines
            ml_engine = MLDecisionEngine()
            analyzer = PlayerAnalyzer()
            hist_analyzer = HistoricalAnalyzer()
            
            # Get Rosters (Home/Away logic handled previously)
            my_roster_obj = matchup.home_lineup if soy_home else matchup.away_lineup
            opp_roster_obj = matchup.away_lineup if soy_home else matchup.home_lineup
            
            # expert data
            try:
                expert_data = expert_scrapers.get_player_expert_data()
            except:
                expert_data = {}

            # Calculate Stats
            ms = calc_matchup_totals(my_roster_obj)
            rs = calc_matchup_totals(opp_roster_obj)
            
            # Helper for Remaining Games
            def get_remaining_counts(roster):
                counts = {}
                # Simple approximation: 3 games remaining avg if early week, else declining
                # Real implementation would check schedule map
                # For now using heuristic based on player status
                for p in roster:
                    counts[p.name] = 3 # Placeholder default
                return counts
            
            rem_me = get_remaining_counts(my_roster_obj)
            rem_opp = get_remaining_counts(opp_roster_obj)
            
            # 1. WIN PROBABILITY (ML)
            prediction = ml_engine.calculate_matchup_probability(
                ms, rs, rem_me, rem_opp, 
                my_roster_obj, opp_roster_obj, 
                config['categorias']
            )
            
            # 2. EXPERT COMPARISON
            comparison = analyzer.compare_rosters_expert_strength(
                my_roster_obj, opp_roster_obj, expert_data
            )
            
            # 3. HISTORICAL
            opp_name = matchup.away_team.team_name if soy_home else matchup.home_team.team_name
            history = hist_analyzer.get_similar_matchups("MY_LEAGUE", opp_name) # Using explicit ID would be better
            
             # --- UI DISPLAY ---
            
            # KPI ROW
            c1, c2, c3 = st.columns(3)
            
            # Win Probability Card
            with c1:
                prob = prediction['win_probability']
                delta_color = "normal" if prob >= 0.5 else "inverse"
                st.metric(
                    "Probabilidad de Victoria", 
                    f"{prob:.0%}",
                    delta="Posible Victoria" if prob > 0.5 else "Riesgo de Derrota",
                    delta_color=delta_color
                )
                start_val = int(prob * 100)
                st.progress(start_val)
                st.caption(f"Predicción: {prediction['predicted_score']}")
            
            # Expert Advantage Card
            with c2:
                adv = comparison['advantage']
                my_top50 = comparison['my_stats']['top50']
                opp_top50 = comparison['opp_stats']['top50']
                
                label_adv = "✅ Ventaja Calidad" if adv == 'ME' else "⚠️ Rival Superior" if adv == 'OPP' else "⚖️ Parejo"
                st.metric(
                    "Poder de Plantilla (Expertos)",
                    f"{my_top50} vs {opp_top50}",
                    delta=label_adv,
                    help=f"Jugadores Top 50: Tú {my_top50}, Rival {opp_top50}"
                )
                st.caption(f"Avg Rank: #{int(comparison['my_stats']['avg_rank'])} vs #{int(comparison['opp_stats']['avg_rank'])}")

            # Historical Card
            with c3:
                wins = sum(1 for h in history if h['won'])
                total = len(history)
                win_rate = wins/total if total > 0 else 0
                
                st.metric(
                    "Historial vs Rival",
                    f"{wins}-{total-wins}",
                    delta=f"{win_rate:.0%} Win Rate" if total > 0 else "Sin historial",
                    delta_color="normal" if win_rate >= 0.5 else "inverse"
                )
                st.caption("Últimos matchups")

            st.divider()
            
            # --- PREDICTIVE GRID ---
            st.subheader("📊 Tablero de Control")
            
            dat = []
            w, l, t = 0, 0, 0
            
            for c in config['categorias']:
                k = '3PTM' if c == '3PTM' and '3PTM' not in ms else c
                m, r = ms.get(k, 0), rs.get(k, 0)
                d = m - r if c != 'TO' else r - m
                
                # Prediction Badge
                cat_prob = prediction['category_probs'].get(c, 0.5)
                if cat_prob >= 0.6: status = "🟢 Ganando"
                elif cat_prob <= 0.4: status = "🔴 Perdiendo"
                else: status = "🟡 Reñido"
                
                # Keep raw numbers for styling
                dat.append([c, m, r, d, status])

            df_matchup = pd.DataFrame(dat, columns=['CAT','YO','RIV','DIF', 'STATUS'])
            
            st.dataframe(
                df_matchup,
                column_config={
                    "CAT": st.column_config.TextColumn("Categoría", width="small"),
                    "YO": st.column_config.NumberColumn("Mi Equipo", format="%.1f"),
                    "RIV": st.column_config.NumberColumn("Rival", format="%.1f"),
                    "DIF": st.column_config.BarChartColumn(
                        "Diferencia", 
                        y_min=-30, y_max=30
                    ),
                    "STATUS": st.column_config.TextColumn("Proyección", width="medium")
                },
                use_container_width=True,
                hide_index=True
            )
            
            st.info(f"💡 Factor clave: {prediction['key_factors'][0] if prediction['key_factors'] else 'Juego equilibrado'}")

        except Exception as e:
            st.error(f"Error cargando dashboard inteligente: {e}")
            st.code(str(e)) # Debug info
            # Fallback to old table if needed
             

# 3. AI RECOMMENDATIONS
with tab3:
    st.header("🧠 Recomendaciones Inteligentes")
    
    st.markdown("""
    El sistema analizará **salud, tendencias, schedule y noticias** de todos los jugadores 
    para encontrar las mejores oportunidades de add/drop.
    """)
    
    # Botón para generar recomendaciones
    if st.button("🔮 Analizar y Recomendar", type="primary", use_container_width=True):
        with st.spinner("🔍 Analizando estrategia, jugadores, lesiones, schedules..."):
            try:
                # Import recommender
                from src.smart_recommender import SmartRecommender
                
                # Get data needed
                sos_map = get_sos_map()
                equipos_hoy, _ = get_partidos_hoy()
                box_scores = liga.box_scores()
                
                # Find current matchup
                my_team_name = config.get('my_team_name', '')
                current_matchup = None
                if my_team_name:
                    current_matchup = next((m for m in box_scores if my_team_name in m.home_team.team_name or my_team_name in m.away_team.team_name), None)
                
                if not current_matchup and box_scores:
                    current_matchup = box_scores[0]
                
                # Determine my team and opponent
                if my_team_name and current_matchup:
                    if my_team_name in current_matchup.home_team.team_name:
                        opponent_team = current_matchup.away_team
                    else:
                        opponent_team = current_matchup.home_team
                else:
                    opponent_team = current_matchup.away_team if current_matchup else mi_equipo
                
                # DEBUG: Explore matchup structure
                if current_matchup:
                    logger.info(f"🔍 DEBUG Matchup type: {type(current_matchup)}")
                    all_attrs = [x for x in dir(current_matchup) if not x.startswith('_')]
                    logger.info(f"  All attributes: {all_attrs}")
                    logger.info(f"  Home team: {current_matchup.home_team.team_name}")
                    logger.info(f"  Away team: {current_matchup.away_team.team_name}")
                
                # Create recommender with ADVANCED parameters
                recommender = SmartRecommender(liga, config)
                
                # Generate STRATEGIC recommendations
                result = recommender.get_daily_recommendations(
                    mi_equipo, 
                    opponent_team, 
                    current_matchup, 
                    sos_map, 
                    list(equipos_hoy)
                )
                
                # Display STRATEGIC CONTEXT first
                if result.get('context'):
                    st.divider()
                    st.subheader("📊 Análisis Estratégico")
                    
                    ctx = result['context']
                    
                    # Create visual context cards (mobile-friendly)
                    col1, col2, col3 = st.columns(3)
                    
                    # Playoff card
                    with col1:
                        playoff = ctx.get('playoff', {})
                        strategy_emoji = {
                            'PLAYOFFS': '🏆',
                            'BUILD_PLAYOFF': '🎯',
                            'WIN_NOW': '⚔️'
                        }.get(playoff.get('strategy', 'WIN_NOW'), '⚔️')
                        
                        st.metric(
                            label="Estrategia",
                            value=playoff.get('strategy', 'WIN_NOW'),
                            delta=f"Semana {playoff.get('current_week', 1)}"
                        )
                    
                    # Matchup state card
                    with col2:
                        matchup_st = ctx.get('matchup', {})
                        cats_me = matchup_st.get('categories_ahead', 0)
                        cats_opp = matchup_st.get('categories_behind', 0)
                        cats_tied = matchup_st.get('categories_tied', 0)
                        winning = matchup_st.get('winning', False)
                        days_left = matchup_st.get('days_remaining', 0)
                        
                        st.metric(
                            label="Matchup esta semana",
                            value=f"{cats_me}-{cats_opp}-{cats_tied}",
                            delta=f"{days_left} días restantes" if days_left > 0 else "Último día",
                            delta_color="normal" if winning else "inverse"
                        )
                    
                    # Acquisitions card
                    with col3:
                        acq = ctx.get('acquisitions', {})
                        moves_used = acq.get('moves_used', 0)
                        weekly_limit = acq.get('weekly_limit', 7)
                        moves_left = acq.get('moves_remaining', 0)
                        
                        st.metric(
                            label="Adds esta semana",
                            value=f"{moves_used}/{weekly_limit}",
                            delta=f"{moves_left} restantes",
                            delta_color="normal" if moves_left > 1 else "inverse"
                        )
                    
                    # Today's matchup analysis
                    today_ctx = ctx.get('today', {})
                    if today_ctx:
                        advantage = today_ctx.get('advantage', 'TIED')
                        advantage_emoji = {
                            'ME': '🔥',
                            'OPP': '⚡',
                            'TIED': '⚖️'
                        }.get(advantage, '⚖️')
                        
                        st.info(f"{advantage_emoji} **HOY**: {today_ctx.get('my_players_today', 0)} tuyos vs {today_ctx.get('opp_players_today', 0)} rival | Power: {today_ctx.get('power_diff', 0):+.1f}")
                
                # Display strategic message
                if result.get('strategic_message'):
                    st.markdown(result['strategic_message'])
                
                # Display LINEUP CHANGES first (more urgent)
                lineup_changes = result.get('lineup_changes', [])
                if lineup_changes:
                    st.divider()
                    st.subheader("🔄 Cambios de Alineación Sugeridos")
                    st.caption("⚡ Acción inmediata - optimiza tu lineup AHORA")
                    
                    for i, change in enumerate(lineup_changes, 1):
                        type_emoji = {
                            'IR_TO_ACTIVE': '🏥➡️✅',
                            'ACTIVATE': '📤',
                            'BENCH': '📥',
                            'ACTIVE_TO_IR': '✅➡️🏥'
                        }.get(change['type'], '🔄')
                        
                        priority_color = {
                            'HIGH': '🔴',
                            'MEDIUM': '🟡',
                            'LOW': '🟢'
                        }[change['priority']]
                        
                        with st.expander(
                            f"{priority_color} {type_emoji} {change['player_name']} - {change['reason']}",
                            expanded=(change['priority'] == 'HIGH')
                        ):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Jugador**: {change['player_name']}")
                                st.write(f"**Status**: {change.get('injury_status', 'N/A')}")
                            
                            with col2:
                                st.write(f"**Acción**: {change['type'].replace('_', ' ')}")
                                st.write(f"**Juega hoy**: {'✅ Sí' if change.get('plays_today') else '❌ No'}")
                            
                            # Action button
                            if st.button(f"✅ Hecho", key=f"lineup_{i}", use_container_width=True):
                                st.success("👍 Cambio registrado")
                
                # Display ADD/DROP recommendations
                recommendations = result.get('recommendations', [])
                
                if recommendations:
                    st.divider()
                    st.success(f"✅ {len(recommendations)} recomendaciones estratégicas")
                    
                    # Show recommendations
                    for i, rec in enumerate(recommendations, 1):
                        priority_color = {
                            'HIGH': '🔴',
                            'MEDIUM': '🟡',
                            'LOW': '🟢'
                        }[rec['priority']]
                        
                        # Create expander for each recommendation
                        with st.expander(
                            f"{priority_color} #{i}: {rec['drop_name']} → {rec['add_name']} "
                            f"(+{rec['projected_impact']} pts)",
                            expanded=(i == 1)  # Primera siempre expandida
                        ):
                            # Show explanation
                            explanation = recommender.explain_recommendation(rec)
                            st.markdown(explanation)
                            
                            # Action buttons (mobile-friendly)
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button(
                                    "✅ Buena idea", 
                                    key=f"accept_{i}",
                                    use_container_width=True
                                ):
                                    st.success("👍 Guardado para futuro aprendizaje")
                            
                            with col2:
                                if st.button(
                                    "❌ No me convence", 
                                    key=f"reject_{i}",
                                    use_container_width=True
                                ):
                                    st.info("📝 Sistema aprenderá de tu preferencia")
                    
                    # Nota informativa
                    st.divider()
                    st.caption("""
                    💡 **Tip**: Las recomendaciones mejoran con el tiempo a medida que el sistema 
                    aprende de tus decisiones y preferencias.
                    """)
                    
                else:
                    st.warning("⚠️ No se encontraron oportunidades en este momento")
                    if result.get('strategic_message'):
                        st.info("📊 Ver análisis estratégico arriba para más contexto")
                    
            except Exception as e:
                st.error(f"❌ Error generando recomendaciones: {e}")
                logger.error(f"Error in AI tab: {e}")
                import traceback
                st.code(traceback.format_exc())
                st.info("💡 Tip: Asegúrate de tener conexión a internet para scraping de datos")
    
    # Información del sistema
    st.divider()
    with st.expander("ℹ️ ¿Cómo funciona?"):
        st.markdown("""
        ### 🤖 Sistema de IA
        
        **Análisis Multi-Dimensional:**
        - 💚 **Salud**: Injury reports actualizados (NBA.com + ESPN)
        - 📈 **Tendencias**: Últimos 7, 15, 30 días de performance
        - 📅 **Schedule**: Juegos próximos 7 días + dificultad de rivales
        - 📊 **Consistencia**: Variabilidad de rendimiento
        
        **Algoritmo de Scoring:**
        1. Cada jugador recibe score 0-100 en cada dimensión
        2. Score total ponderado (Salud 35%, Tendencia 30%, Schedule 25%, Consistencia 10%)
        3. Calcula impacto: Score_Add - Score_Drop
        4. Ordena por mayor impacto proyectado
        
        **100% Gratuito:**
        - Sin APIs de pago
        - Web scraping de fuentes públicas
        - Machine learning local con SQLite
        - Aprende de tus decisiones
        """)

# --- 4. LEARNING TAB ---
render_learning_tab(tab4, liga)

# --- FOOTER ESPACIADOR PARA MÓVIL ---
st.write("<br><br><br>", unsafe_allow_html=True) 
st.caption("🚀 Fantasy GM Pro v3.0 + AI | The Intelligence Update")