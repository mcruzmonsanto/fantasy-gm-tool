# Fix para compatibilidad con credenciales.py
# Este archivo asegura que el código legacy siga funcionando

import sys
import os

# Añadir path para importar config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# IMPORTANTE: Si tu archivo credenciales.py usa "id" en vez de "league_id",
# necesitas actualizarlo manualmente o usar este adaptador:

def adaptar_credenciales_legacy():
    """Adapta formato viejo de credenciales al nuevo"""
    try:
        from config.credenciales import LIGAS as LIGAS_ORIGINAL
        
        adapted = {}
        for nombre, config in LIGAS_ORIGINAL.items():
            # Si usa el formato viejo con "id", convertir
            if "id" in config and "league_id" not in config:
                adapted[nombre] = {
                    "league_id": config["id"],  # Convertir "id" -> "league_id"
                    "year": config["year"],
                    "swid": config["swid"],
                    "espn_s2": config["espn_s2"],
                    "categorias": config.get("categorias", ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PTM', 'FG%', 'FT%', 'TO'])
                }
            else:
                # Ya está en formato nuevo
                adapted[nombre] = config
        
        return adapted
        
    except ImportError:
        return {}

# Exportar versión adaptada
LIGAS = adaptar_credenciales_legacy()
