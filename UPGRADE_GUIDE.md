# 🚀 Guía de Actualización - Fantasy GM Pro v3.0

## Cambios Principales

### ✅ Completado

1. **Dependencies Modernizadas**: Actualizado `requirements.txt` con versiones específicas
2. **Sistema de Configuración .env**: Migración de `credenciales.py` a variables de entorno
3. **Retry Logic**: Conexiones automáticas con reintentos en caso de fallo
4. **Logging Profesional**: Sistema de logs con `loguru`
5. **Cache Manager**: Indicadores visuales de frescura de datos
6. **Panel de Diagnóstico**: Herramienta de debugging en sidebar
7. **Alert System**: Sistema de alertas inteligentes

---

## 🔧 Instrucciones de Instalación

### Paso 1: Actualizar Dependencias

```bash
# Activar entorno virtual si usas uno
.\\venv\\Scripts\\activate  # Windows

# Instalar nuevas dependencias
pip install -r requirements.txt
```

### Paso 2: Configurar Variables de Entorno (Recomendado)

#### Opción A: Migrar a .env (Recomendado)

1. Copia el archivo de ejemplo:
```bash
copy .env.example .env
```

2. Edita `.env` con tus credenciales reales:
```env
LIGA_1_NOMBRE="Mi Liga Principal"
LIGA_1_ID=123456789
LIGA_1_YEAR=2026
LIGA_1_SWID="{TU-SWID-AQUI}"
LIGA_1_ESPN_S2="TU-TOKEN-ESPN-S2-LARGO"
LIGA_1_CATEGORIAS="PTS,REB,AST,STL,BLK,3PTM,FG%,FT%,TO"
```

#### Opción B: Seguir usando credenciales.py (Legacy)

- La app seguirá funcionando con tu archivo `config/credenciales.py` existente
- **Nota**: Necesitas actualizar la estructura de tus credenciales:
  - Cambiar `"id"` por `"league_id"` en el diccionario

**Antes:**
```python
LIGAS = {
    "Mi Liga": {
        "id": 123456789,  # ❌ Viejo
        "year": 2026,
        ...
    }
}
```

**Después:**
```python
LIGAS = {
    "Mi Liga": {
        "league_id": 123456789,  # ✅ Nuevo
        "year": 2026,
        ...
    }
}
```

### Paso 3: Crear Carpeta de Logs

```bash
mkdir logs
```

### Paso 4: Ejecutar la Aplicación

```bash
streamlit run app.py
```

---

## 🆕 Nuevas Características

### 1. Panel de Diagnóstico

Ahora en el sidebar verás un nuevo panel de "🔧 Diagnóstico" que muestra:
- Estado de la API de ESPN (🟢 Online / 🔴 Offline)
- Hora actual en Eastern Time
- Estadísticas de cache
- Botón de reset total

### 2. Indicadores de Cache

Los datos ahora muestran su frescura:
- 🟢 Datos frescos (< 30% del TTL usado)
- 🟡 Datos recientes (30-70% del TTL usado)
- 🟠 Datos próximos a actualizar (> 70% del TTL usado)
- 🔴 Cargando datos frescos...

### 3. Reconexión Automática

Si la API de ESPN falla, la app intentará reconectar automáticamente:
- 3 intentos con espera exponencial
- Logs detallados de cada intento
- Mensajes de error más claros

### 4. Logs Persistentes

Todos los eventos se guardan en `logs/fantasy_gm_YYYY-MM-DD.log`:
- Conexiones exitosas/fallidas
- Cargas de datos
- Errores de API
- Rotación diaria automática

---

## 🐛 Solución de Problemas

### Error: "No module named 'dotenv'"

```bash
pip install python-dotenv
```

### Error: "No module named 'loguru'"

```bash
pip install loguru tenacity cachetools
```

### Error: "No se encontraron ligas en .env"

1. Verifica que el archivo `.env` existe en la raíz del proyecto
2. Verifica que las variables empiezan con `LIGA_1_`, `LIGA_2_`, etc.
3. Asegúrate de no tener espacios extras

### La app usa credenciales.py en vez de .env

Esto es normal si:
- No existe el archivo `.env`, o
- El archivo `.env` está mal configurado

La app automáticamente hace fallback a `credenciales.py` para compatibilidad.

### Quiero volver a la versión anterior

```bash
git checkout HEAD~1 app.py src/conectar.py requirements.txt
```

---

## 📊 Comparación v2.0 vs v3.0

| Característica | v2.0 | v3.0 |
|---------------|------|------|
| Configuración | `credenciales.py` manual | `.env` + fallback |
| Retry en fallos | ❌ No | ✅ 3 intentos automáticos |
| Logging | `logging` básico | `loguru` profesional |
| Cache indicators | ❌ No | ✅ Indicadores visuales |
| Diagnóstico | ❌ No | ✅ Panel en sidebar |
| Versiones pinneadas | ❌ No | ✅ Sí |
| Alert system | ❌ No | ✅ Sí |

---

## 🔄 Workflow Recomendado

1. **Desarrollo Local**: Usa `.env` para credenciales
2. **Git**: Nunca commitees `.env` (ya está en `.gitignore`)
3. **Nuevas Ligas**: Agrega `LIGA_X_...` en `.env`
4. **Troubleshooting**: Revisa logs en `logs/fantasy_gm_*.log`
5. **Actualizar Datos**: Usa el botón "🔄 Refrescar Datos" en sidebar

---

## ⚙️ Configuración Avanzada

### Ajustar TTL de Cache

En tu `.env`:
```env
CACHE_TTL_WEEKLY=1800   # Calendario semanal (30 min)
CACHE_TTL_DAILY=900     # Partidos de hoy (15 min)
CACHE_TTL_SOS=21600     # Strength of Schedule (6 horas)
```

### Nivel de Logging

En tu `.env`:
```env
LOG_LEVEL=DEBUG  # Opciones: DEBUG, INFO, WARNING, ERROR
DEBUG_MODE=true  # Para más detalles
```

---

## 📝 Próximos Pasos Sugeridos

1. **Migrar a .env**: Si aún usas `credenciales.py`
2. **Revisar Logs**: Familiarízate con los logs en `logs/`
3. **Explorar Diagnóstico**: Prueba el panel de diagnóstico
4. **Reportar Issues**: Si encuentras problemas, revisa los logs primero

---

## 🆘 Soporte

Si tienes problemas:

1. Revisa los logs en `logs/fantasy_gm_YYYY-MM-DD.log`
2. Verifica el panel de diagnóstico (sidebar)
3. Abre un issue en GitHub con:
   - Logs relevantes
   - Mensaje de error completo
   - Versión de Python (`python --version`)

---

**¡Disfruta de Fantasy GM Pro v3.0! 🏀🔥**
