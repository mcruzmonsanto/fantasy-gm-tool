import sys
import os
import pprint # Para imprimir bonito los diccionarios

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.conectar import obtener_liga
from config.credenciales import LIGAS

PALABRA_CLAVE = "Max"

def auditar_datos(nombre_liga):
    liga = obtener_liga(nombre_liga)
    if not liga: return

    print(f"\n🔬 AUDITORÍA FORENSE: {nombre_liga}")
    
    # 1. Traemos el Box Score
    try:
        box_scores = liga.box_scores() # Usamos el default (semana actual)
    except Exception as e:
        print(f"❌ Error al traer box scores: {e}")
        return

    mi_matchup = None
    
    # 2. Buscamos tu partido
    for matchup in box_scores:
        if PALABRA_CLAVE.lower() in matchup.home_team.team_name.lower() or \
           PALABRA_CLAVE.lower() in matchup.away_team.team_name.lower():
            mi_matchup = matchup
            break
    
    if not mi_matchup:
        print("❌ No te encontré en los box scores.")
        return

    # 3. IMPRIMIMOS LA VERDAD CRUDA
    # Aquí veremos qué demonios está devolviendo la API
    print(f"⚔️ Enfrentamiento encontrado: {mi_matchup.home_team.team_name} vs {mi_matchup.away_team.team_name}")
    
    print("\n----- 🕵️ INSPECCIÓN DE DATOS DE HOME_STATS -----")
    # Usamos pprint para ver la estructura exacta del diccionario
    pprint.pprint(mi_matchup.home_stats)
    
    print("\n----- 🕵️ INSPECCIÓN DE AWAY_STATS -----")
    pprint.pprint(mi_matchup.away_stats)

    print("\n----- 🕵️ INSPECCIÓN DE UN JUGADOR (HOME LINEUP) -----")
    # A veces los stats totales están vacíos y hay que sumar jugador por jugador
    if mi_matchup.home_lineup:
        jugador_ejemplo = mi_matchup.home_lineup[0]
        print(f"Jugador: {jugador_ejemplo.name}")
        print(f"Stats Semana: {jugador_ejemplo.stats}")
    
    print("-" * 60)

if __name__ == "__main__":
    # Prueba solo con la Liga A primero para no llenar la pantalla
    auditar_datos("LIGA_A")
    auditar_datos("LIGA_A")