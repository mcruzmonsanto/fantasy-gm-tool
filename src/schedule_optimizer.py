import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict

def obtener_juegos_nba(fecha_str):
    """
    Consulta la API pública de ESPN para una fecha específica (YYYYMMDD).
    Retorna una lista de abreviaturas de equipos (ej: ['LAL', 'BOS']).
    """
    # URL Pública de ESPN (No requiere cookies ni login)
    url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={fecha_str}"
    
    try:
        r = requests.get(url)
        data = r.json()
        
        equipos_jugando = []
        
        # Navegamos el JSON público
        events = data.get('events', [])
        for event in events:
            competitions = event.get('competitions', [])
            for comp in competitions:
                competitors = comp.get('competitors', [])
                for team in competitors:
                    # Buscamos la abreviatura (LAL, BOS, MIA)
                    abrev = team.get('team', {}).get('abbreviation')
                    if abrev:
                        equipos_jugando.append(abrev)
        
        return equipos_jugando

    except Exception as e:
        print(f"❌ Error consultando fecha {fecha_str}: {e}")
        return []

def ejecutar_optimizador():
    print("\n📅 ANÁLISIS DE CALENDARIO (FUENTE: NBA PÚBLICA)")
    print("=" * 50)

    # 1. Definir fechas: HOY y MAÑANA
    hoy = datetime.now()
    manana = hoy + timedelta(days=1)
    
    fechas = [
        ("HOY", hoy.strftime("%Y%m%d")),
        ("MAÑANA", manana.strftime("%Y%m%d"))
    ]

    conteo_estrategico = defaultdict(int)

    # 2. Iterar y Buscar
    for etiqueta, fecha_id in fechas:
        equipos = obtener_juegos_nba(fecha_id)
        equipos.sort()
        
        print(f"🏀 {etiqueta} ({fecha_id}): {len(equipos)} equipos juegan")
        if equipos:
            print(f"   -> {', '.join(equipos)}")
            
            # Acumulamos para la estrategia
            for eq in equipos:
                conteo_estrategico[eq] += 1
        else:
            print("   -> 💤 No hay partidos programados.")

    print("\n" + "-" * 50)
    print("🧠 ESTRATEGIA DE STREAMING:")
    
    # 3. Detectar Back-to-Backs
    joyas = [eq for eq, count in conteo_estrategico.items() if count >= 2]
    joyas.sort()
    
    # Obtener equipos de HOY para el plan B
    equipos_hoy = obtener_juegos_nba(fechas[0][1])
    equipos_hoy.sort()

    if joyas:
        print(f"💎 ORO PURO (Juegan Hoy y Mañana):")
        print(f"   Estos equipos te dan 2 partidos por el precio de 1 fichaje.")
        print(f"   👉 {joyas}")
        print(f"\n✅ ACCIÓN: Copia esto en 'waiver_king.py':")
        print(f"   EQUIPOS_JUGANDO_HOY = {joyas}")
    elif equipos_hoy:
        print(f"ℹ️ No hay Back-to-Backs inmediatos.")
        print(f"   Prioridad: Fichar cualquiera que juegue HOY.")
        print(f"\n✅ ACCIÓN: Copia esto en 'waiver_king.py':")
        print(f"   EQUIPOS_JUGANDO_HOY = {equipos_hoy}")
    else:
        print("⚠️ No hay partidos hoy. Prepara tu equipo para mañana.")

if __name__ == "__main__":
    ejecutar_optimizador()