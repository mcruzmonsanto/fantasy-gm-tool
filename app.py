import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import sys
import os

from src.conectar import obtener_liga
from config.credenciales import LIGAS

st.set_page_config(page_title="Fantasy GM Pro", page_icon="🏀", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .metric-card {background-color: #1E1E1E; padding: 15px; border-radius: 10px; border: 1px solid #333;}
    .stDataFrame {border: 1px solid #444;}
</style>
""", unsafe_allow_html=True)

# --- MAPEO MAESTRO ---
MAPEO_EQUIPOS = {
    'WSH': 'WAS', 'UTAH': 'UTA', 'NO': 'NOP', 'NY': 'NYK', 'SA': 'SAS', 
    'PHO': 'PHX', 'GS': 'GSW', 'UTH': 'UTA', 'SAN': 'SAS', 'NOR': 'NOP',
    'GSW': 'GSW', 'WAS': 'WAS', 'NYK': 'NYK' # Redundancia segura
}

def normalizar_equipo(abrev):
    return MAPEO_EQUIPOS.get(abrev.upper(), abrev.upper())

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
        dias_keys = list(calendario.keys())
        
        for dia in dias_keys:
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
        
        df_grid = pd.DataFrame([fila_yo, fila_rival, fila_diff], columns=["EQUIPO"] + dias_keys + ["TOTAL"])
        st.dataframe(df_grid, use_container_width=True)

        # --- SECCIÓN DE DIAGNÓSTICO (DEBUGGER) ---
        with st.expander("🕵️ Diagnóstico de Roster (Debug)"):
            st.write("Usa esto para ver qué jugadores no se están contando.")
            
            # Buscar la columna de hoy (miércoles 26)
            hoy_fmt = datetime.now().strftime("%a %d")
            # Fallback por si el formato de fecha varía
            col_hoy = next((k for k in dias_keys if str(datetime.now().day) in k), dias_keys[0])
            
            st.write(f"**Analizando para el día: {col_hoy}**")
            teams_playing = calendario.get(col_hoy, [])
            st.caption(f"Equipos jugando hoy (API): {', '.join(teams_playing)}")
            
            debug_data = []
            for p in mi_equipo_obj.roster:
                raw_team = p.proTeam
                norm_team = normalizar_equipo(raw_team)
                juega = "✅ SÍ" if norm_team in teams_playing else "❌ NO"
                if p.injuryStatus == 'OUT': juega = "⛔ OUT"
                
                debug_data.append({
                    'Jugador': p.name,
                    'Equipo (Raw)': raw_team,
                    'Equipo (Norm)': norm_team,
                    '¿Juega Hoy?': juega
                })
            st.dataframe(pd.DataFrame(debug_data))

# Resto de secciones (Matchup, Verdugo, Waiver) simplificadas para no exceder límites de respuesta
st.markdown("---")
c1, c2 = st.columns(2)
with c1:
    st.subheader("⚔️ Matchup"); necesidades=[]
    if mi_matchup:
        ms = calcular_stats_manuales(mi_matchup.home_lineup if soy_home else mi_matchup.away_lineup)
        rs = calcular_stats_manuales(mi_matchup.away_lineup if soy_home else mi_matchup.home_lineup)
        dt = []
        for c in config['categorias']:
            k='3PTM' if c=='3PTM' and '3PTM' not in ms else c
            m=ms.get(k,0); r=rs.get(k,0); d=m-r if c!='TO' else r-m
            stt="🟢" if d>0 else "🔴" if d<0 else "🟡"
            if d<0: necesidades.append(c)
            dt.append([c,f"{m:.2f}",f"{r:.2f}",f"{d:.2f}",stt])
        st.dataframe(pd.DataFrame(dt, columns=['C','Y','R','D','W']), use_container_width=True)

with c2:
    st.subheader("🪓 Verdugo")
    if mi_matchup:
        dr=[]
        for p in mi_equipo_obj.roster:
            s=p.stats.get(f"{season_id}_total",{}).get('avg',{})
            if not s: s=p.stats.get(f"{season_id}_projected",{}).get('avg',{})
            scr=s.get('PTS',0)+s.get('REB',0)*1.2+s.get('AST',0)*1.5
            icon="⛔" if p.injuryStatus=='OUT' else "✅"
            dr.append({'J':p.name,'St':icon,'Sc':round(scr,1)})
        st.dataframe(pd.DataFrame(dr).sort_values(by='Sc'), use_container_width=True)

st.caption("🚀 Fantasy GM Architect v3.5 | Debug Mode")