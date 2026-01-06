"""
Archivo de ejemplo de credenciales.
Copia este archivo como 'credenciales.py' y completa con tus datos reales.
"""

LIGAS = {
    "Mi Liga Principal": {
        "league_id": 123456789,  # ID de tu liga (número en la URL)
        "year": 2026,  # Año de la temporada
        "swid": "{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}",  # Tu SWID (incluye las llaves)
        "espn_s2": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",  # Tu token ESPN_S2
        "categorias": ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PTM', 'FG%', 'FT%', 'TO']  # Categorías de tu liga
    },
    
    # Puedes agregar más ligas aquí
    "Liga Secundaria": {
        "league_id": 987654321,
        "year": 2026,
        "swid": "{YYYYYYYY-YYYY-YYYY-YYYY-YYYYYYYYYYYY}",
        "espn_s2": "YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY",
        "categorias": ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PTM', 'FG%', 'FT%', 'TO', 'DD']
    }
}

"""
CÓMO OBTENER TUS CREDENCIALES:

1. LEAGUE_ID:
   - Ve a tu liga en ESPN Fantasy Basketball
   - Mira la URL: https://fantasy.espn.com/basketball/league?leagueId=123456789
   - El número después de 'leagueId=' es tu league_id

2. SWID y ESPN_S2:
   - Inicia sesión en ESPN Fantasy
   - Abre las herramientas de desarrollador (F12 en Chrome/Firefox)
   - Ve a la pestaña "Application" (Chrome) o "Storage" (Firefox)
   - Busca "Cookies" > "https://fantasy.espn.com"
   - Encuentra:
     * SWID: Copia el valor completo (incluye las llaves {})
     * espn_s2: Copia el valor completo (es muy largo, ~500 caracteres)

3. CATEGORIAS:
   - Lista las categorías que usa tu liga
   - Opciones comunes:
     * Conteo: 'PTS', 'REB', 'AST', 'STL', 'BLK', '3PTM', 'TO', 'DD', 'TD'
     * Porcentaje: 'FG%', 'FT%'
   - Usa exactamente los nombres que aparecen en ESPN

IMPORTANTE:
- NO compartas este archivo con nadie
- NO lo subas a GitHub (está en .gitignore)
- Las cookies expiran después de ~2 años
- Si cambias de contraseña, necesitarás nuevas cookies
"""
