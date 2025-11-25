import sys
import os
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.conectar import obtener_liga
from config.credenciales import LIGAS

PALABRA_CLAVE = "Max" 

# --- CONFIGURACIÓN DE VARIANZA DIARIA ---
# ¿Cuánto puede cambiar una categoría en UN solo día promedio?
# Esto define qué tan "segura" es una ventaja.
SWING_POR_DIA = {
    'PTS': 35,  # Un equipo puede recortar 35 pts en un día bueno
    'REB': 12,
    'AST': 9,
    'STL': 3.5,
    'BLK': 3.5, 
    '3PTM': 4,
    'TO': 4,
    'DD': 1.5,
    # Porcentajes: Es difícil calcular por día, usamos fijos ajustados por tiempo
    'FG%': 0.0, 
    'FT%': 0.0
}

def obtener_factor_tiempo():
    """
    Calcula cuántos días de juego quedan en la semana (Lunes=0 ... Domingo=6)
    """
    dia_actual = datetime.now().weekday() # 0=Lunes, 1=Martes...
    
    # Asumimos semana estándar de Fantasy (Lunes a Domingo)
    dias_restantes = 6 - dia_actual
    if dias_restantes < 0: dias_restantes = 0 # Por si acaso
    
    # Ajuste: Si es temprano en el día, contamos hoy como día jugable
    # Si es muy tarde (ej 11 PM), ya no cuenta.
    hora = datetime.now().hour
    if hora < 22: 
        dias_restantes += 1
        
    return dias_restantes, dia_actual

def calcular_stats_manuales(lineup):
    """ Suma manual de titulares """
    totales = {'PTS':0, 'REB':0, 'AST':0, 'STL':0, 'BLK':0, '3PTM':0, 'TO':0, 'DD':0, 'FGM':0, 'FGA':0, 'FTM':0, 'FTA':0}
    
    for jugador in lineup:
        if jugador.slot_position in ['BE', 'IR']: continue 
        
        stats_data = {}
        if jugador.stats:
            for k, v in jugador.stats.items():
                if 'total' in v:
                    stats_data = v['total']; break
        
        if not stats_data: continue

        totales['PTS'] += stats_data.get('PTS', 0)
        totales['REB'] += stats_data.get('REB', 0)
        totales['AST'] += stats_data.get('AST', 0)
        totales['STL'] += stats_data.get('STL', 0)
        totales['BLK'] += stats_data.get('BLK', 0)
        totales['TO'] += stats_data.get('TO', 0)
        totales['DD'] += stats_data.get('DD', 0)
        totales['3PTM'] += stats_data.get('3PM', stats_data.get('3PTM', 0))
        totales['FGM'] += stats_data.get('FGM', 0); totales['FGA'] += stats_data.get('FGA', 0)
        totales['FTM'] += stats_data.get('FTM', 0); totales['FTA'] += stats_data.get('FTA', 0)

    if totales['FGA'] > 0: totales['FG%'] = totales['FGM'] / totales['FGA']
    else: totales['FG%'] = 0.0
    if totales['FTA'] > 0: totales['FT%'] = totales['FTM'] / totales['FTA']
    else: totales['FT%'] = 0.0

    return totales

def analizar_necesidades(nombre_liga):
    liga = obtener_liga(nombre_liga)
    if not liga: return None

    # Datos temporales
    dias_restantes, dia_idx = obtener_factor_tiempo()
    nombres_dias = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dia_nombre = nombres_dias[dia_idx]

    print(f"\n⏳ TIEMPO RESTANTE: {dias_restantes} días de juego (Hoy es {dia_nombre})")
    
    # Configuración
    config = LIGAS[nombre_liga]
    OBJETIVO_VICTORIAS = 5 
    
    try: box_scores = liga.box_scores()
    except: return None
    
    mi_matchup = None
    soy_home = False 
    for m in box_scores:
        if PALABRA_CLAVE.lower() in m.home_team.team_name.lower(): mi_matchup = m; soy_home = True; break
        elif PALABRA_CLAVE.lower() in m.away_team.team_name.lower(): mi_matchup = m; soy_home = False; break
    
    if not mi_matchup: print("❌ Matchup no encontrado."); return None

    # Stats
    mis_stats = calcular_stats_manuales(mi_matchup.home_lineup if soy_home else mi_matchup.away_lineup)
    rival_stats = calcular_stats_manuales(mi_matchup.away_lineup if soy_home else mi_matchup.home_lineup)

    necesidades = []
    datos_tabla = []
    
    wins = 0; losses = 0; ties = 0
    cats_volatiles = 0

    cats_liga = config['categorias']
    
    for cat in cats_liga:
        key = '3PTM' if cat == '3PTM' and '3PTM' not in mis_stats else cat
        val_mio = mis_stats.get(key, 0)
        val_rival = rival_stats.get(key, 0)
        
        if cat == 'TO': diff = val_rival - val_mio 
        else: diff = val_mio - val_rival
        
        if diff > 0: estado = "🟢 GANA"; wins += 1
        elif diff < 0: estado = "🔴 PIERDE"; losses += 1
        else: estado = "🟡 EMPATE"; ties += 1

        # --- LÓGICA DE PROBABILIDAD BASADA EN TIEMPO ---
        # Calculamos el umbral dinámico para HOY
        if cat in ['FG%', 'FT%']:
            # Porcentajes: Al inicio de semana (dias>4) todo es volátil
            # Al final (dias<2), es difícil cambiar más de un 2-3%
            umbral = 0.10 if dias_restantes > 4 else (0.02 * dias_restantes)
        else:
            # Stats de conteo: Swing Diario * Días que faltan
            base_swing = SWING_POR_DIA.get(cat, 5)
            umbral = base_swing * dias_restantes

        # Análisis de Seguridad
        distancia = abs(diff)
        probabilidad = "🔒" # Candado cerrado (Seguro)
        
        if distancia <= umbral:
            probabilidad = "🎲" # Dado (Volátil / Suerte / Gestión)
            cats_volatiles += 1
            
            # Si es volátil y voy perdiendo, ES UNA OPORTUNIDAD
            if diff < 0:
                necesidades.append(cat)
        
        # Formateo bonito para la tabla
        txt_umbral = f"(+/- {round(umbral,1)})"
        datos_tabla.append({
            'CAT': cat, 
            'YO': round(val_mio, 2), 
            'RIVAL': round(val_rival, 2), 
            'DIFF': round(diff, 2), 
            'PROB': probabilidad,
            'MARGEN_SEGURIDAD': txt_umbral,
            'ESTADO': estado
        })

    # --- REPORTE DEL GENERAL MANAGER ---
    df = pd.DataFrame(datos_tabla)
    print(f"\n📊 ANÁLISIS DE MATCHUP: {nombre_liga}")
    print(f"   Leyenda: 🎲 = Resultado Incierto (Atacable) | 🔒 = Resultado Probable (Difícil cambiar)")
    print(df[['CAT', 'YO', 'RIVAL', 'DIFF', 'ESTADO', 'PROB', 'MARGEN_SEGURIDAD']].to_string(index=False))
    
    print("-" * 60)
    print(f"🏆 MARCADOR: {wins}-{losses}-{ties}")
    
    # PREDICCIÓN MATEMÁTICA
    escenario_pesimista = wins # Asume que pierdes todos los dados
    escenario_optimista = wins + cats_volatiles + ties # Asume que ganas todos los dados
    
    print(f"🔮 PROYECCIÓN SEMANAL (Faltan {dias_restantes} días):")
    print(f"   -> Piso (Peor caso): {escenario_pesimista} Victorias")
    print(f"   -> Techo (Mejor caso): {escenario_optimista} Victorias")
    print(f"   -> Meta Requerida: {OBJETIVO_VICTORIAS}")

    if escenario_pesimista >= OBJETIVO_VICTORIAS:
        print("✅ PREDICCIÓN: VICTORIA ASEGURADA (Salvo catástrofe).")
    elif escenario_optimista < OBJETIVO_VICTORIAS:
        print("💀 PREDICCIÓN: DERROTA MATEMÁTICAMENTE MUY PROBABLE.")
    else:
        # Estamos en el limbo, todo depende del waiver
        print("⚔️ PREDICCIÓN: BATALLA ABIERTA. EL WAIVER DECIDE.")
        if necesidades:
            print(f"   🚀 TÁCTICA: Debes atacar estas categorías 🎲: {necesidades}")
        else:
            print("   🛡️ TÁCTICA: Defiende tus categorías volátiles.")

    return necesidades

if __name__ == "__main__":
    for liga in LIGAS:
        analizar_necesidades(liga)