# Archivo: config/credenciales.py

# Diccionario maestro. 
# Define aquí tus dos ligas para no repetir códigos.

LIGAS = {
    "LIGA_A": {
        "id": 1429999933,           # <--- Pon aquí el ID numérico de tu Liga 1
        "year": 2026,             # Temporada actual
        "swid": "{DE106A28-060E-4ED6-8446-32D0D38C33E6}", # <--- Incluye los corchetes {} si aparecen
        "espn_s2": "AEBX4rMETBMhz2Rd3TtFRttnWsrAsd%2BX3ZcDbWAG1HR5HPuvft%2FoXI9Zikm4AAsXC8gpgwh5iuNuoGUQe9m0qguiE1PqgIZmBdB1NA8%2BU1oE5j%2BK8y46OJRRQdtnbfbZYG3JuB%2BKFjsLkFCmzPbnguQDFRlglFobpZZ%2BQJNDu5Jg5NbDnO2KsnJZYjEQvgW10ZCRhaYwmgvDx%2BW%2FVIsVh%2BgRuNX5%2BfM0rNmfA6IxxKNmX7L1TNoOAz3R6ZF2cXoZULz0UggXXJcDxbSxC7OgjD4QfvQYhFyQuizGRJO%2BdZVraUi%2Fz7VoX25ggFlUBtBp7aM%3D",  # <--- Es muy largo, copialo todo
        # Estrategia: 8 Categorías Estándar
        "categorias": ['FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'STL', 'BLK']
    },
    "LIGA_B": {
        "id": 404570834,           # <--- Pon aquí el ID numérico de tu Liga 2
        "year": 2026,
        "swid": "{DE106A28-060E-4ED6-8446-32D0D38C33E6}", # Usualmente es el mismo usuario, así que es el mismo SWID
        "espn_s2": "AEAuX%2B0s1fs9rVaucOvdIOLbLrwFaZ7DtulT7rUO45JKYNdbVxaIhQ%2FxdhaZ8gMaoH%2BxhGPcib855ea6qX%2BU0lIlurHs4V%2FbQi8WsSOcLZMVryTlk3sJNz9%2B2kGrH3QwLoeAqQHZnV8aI8EZYQ82UNPrn%2F6LyXhiD0x6t92Y0%2BxnY3ztZmKSlPTtNzPuohMl0oS3KK8s5fVzUBP8EBTVZvPdfvdMyw%2Fgd3ho4nOsZmayb7eTB6sSL1lRYHvlIAVkJ0q5LRDGy8p8sUsxJyrx02uMoAom9d41VmUNuunhgOSPBJrqOFqdcFGumMuD2uCIKaM%3D",
        # Estrategia: 9 Categorías (Incluye Double-Doubles 'DD')
        "categorias": ['FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'DD']
    }
}