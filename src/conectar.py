import sys
import os

# Ajuste de rutas para encontrar la carpeta config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from espn_api.basketball import League
from config.credenciales import LIGAS 

def obtener_liga(nombre_liga):
    """
    Conecta a una liga específica definida en credenciales.py
    Retorna el objeto 'league' o None si falla.
    """
    if nombre_liga not in LIGAS:
        print(f"❌ Error: La liga '{nombre_liga}' no existe en credenciales.")
        return None

    datos = LIGAS[nombre_liga]
    
    # Intento de conexión silencioso (para no llenar la pantalla si lo llamamos muchas veces)
    try:
        league = League(
            league_id=datos['id'], 
            year=datos['year'], 
            espn_s2=datos['espn_s2'], 
            swid=datos['swid']
        )
        return league
        
    except Exception as e:
        print(f"❌ Error conectando a {nombre_liga}: {e}")
        return None

# --- BLOQUE DE PRUEBA DE SISTEMA (SYSTEM CHECK) ---
if __name__ == "__main__":
    print("\n🖥️  INICIANDO VERIFICACIÓN DE SISTEMAS...")
    print("="*50)

    # Iteramos automáticamente por TODAS las ligas configuradas
    todas_las_ligas = list(LIGAS.keys()) # ['LIGA_A', 'LIGA_B']

    for nombre in todas_las_ligas:
        print(f"\n📡 Conectando a: {nombre}...")
        
        mi_liga = obtener_liga(nombre)
        
        if mi_liga:
            print(f"   ✅ ESTADO: ONLINE")
            print(f"   🏆 Liga: {mi_liga.settings.name}")
            print(f"   📅 Semana Actual: {mi_liga.currentMatchupPeriod}")
            # Verificamos tu equipo (asumiendo que los datos de cookies coinciden con un equipo)
            # Nota: Esto lista el primer equipo encontrado como referencia
            print(f"   🏀 Ejemplo de Equipo: {mi_liga.teams[0].team_name}")
        else:
            print(f"   ❌ ESTADO: OFFLINE (Revisa tus credenciales)")
            
    print("\n" + "="*50)
    print("🏁 Verificación finalizada.")