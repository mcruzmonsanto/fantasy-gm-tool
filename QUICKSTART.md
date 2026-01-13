# 🚀 Inicio Rápido - Fantasy GM Pro v3.0

## Estado Actual

✅ **Dependencias instaladas correctamente**
✅ **App ejecutándose en: http://localhost:8501**

⚠️ **Falta**: Configurar credenciales

---

## Configurar Credenciales (2 Opciones)

### Opción 1: Usar .env (RECOMENDADO)

1. Copia `.env.example` a `.env`:
   ```bash
   copy .env.example .env
   ```

2. Abre `.env` y completa con tus datos reales:
   ```env
   LIGA_1_NOMBRE="Mi Liga"
   LIGA_1_ID=123456789                    # Tu League ID
   LIGA_1_YEAR=2026
   LIGA_1_SWID="{XXXXXXXX-...}"           # Tu SWID con las llaves
   LIGA_1_ESPN_S2="AEBxxx..."             # Tu token ESPN_S2
   LIGA_1_CATEGORIAS="PTS,REB,AST,STL,BLK,3PTM,FG%,FT%,TO"
   ```

3. Guarda el archivo y recarga la app en el navegador (F5)

### Opción 2: Usar credenciales.py (Legacy)

Si ya tienes `config/credenciales.py`, **verifica** que use este formato:

```python
LIGAS = {
    "Mi Liga": {
        "league_id": 123456789,  # ✅ NUEVO (no "id")
        "year": 2026,
        "swid": "{TU-SWID}",
        "espn_s2": "TU-ESPN-S2",
        "categorias": ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PTM', 'FG%', 'FT%', 'TO']
    }
}
```

**IMPORTANTE**: Cambiar `"id"` por `"league_id"`

---

## Cómo Obtener tus Credenciales

### League ID
- Ve a tu liga en ESPN
- URL: `https://fantasy.espn.com/basketball/league?leagueId=123456789`
- El número es tu `LIGA_1_ID`

### SWID y ESPN_S2
1. Abre tu liga en el navegador
2. Presiona **F12** (DevTools)
3. Ve a **Application** > **Cookies** > `https://fantasy.espn.com`
4. Busca:
   - **SWID**: Copia el valor completo (incluye las llaves `{}`)
   - **espn_s2**: Copia el valor completo (muy largo, ~500 caracteres)

---

## La app está corriendo

Abre tu navegador en: **http://localhost:8501**

Cuando agregues tus credenciales, presiona **F5** para recargar.

---

## ¿Problemas?

- Revisa los logs en `logs/fantasy_gm_YYYY-MM-DD.log`
- Usa el panel de "🔧 Diagnóstico" en el sidebar
- Lee `UPGRADE_GUIDE.md` para más detalles
