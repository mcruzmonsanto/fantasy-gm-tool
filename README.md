# 🏀 Fantasy GM Pro

Herramienta avanzada de análisis para ligas de Fantasy Basketball en ESPN.

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## 📋 Descripción

Fantasy GM Pro es una aplicación web construida con Streamlit que te ayuda a tomar decisiones inteligentes en tu liga de fantasy basketball. Analiza partidos, jugadores, y oportunidades en el waiver wire con datos en tiempo real de ESPN.

### ✨ Características Principales

- **📅 Grid Semanal**: Visualiza cuántos jugadores tienes activos cada día vs tu rival
- **🔥 Análisis Diario**: Compara tu poder ofensivo vs tu rival para el día actual
- **⚔️ Matchup en Vivo**: Seguimiento categoría por categoría de tu enfrentamiento
- **🪓 Gestión de Roster**: Identifica jugadores de bajo rendimiento para cortar
- **💎 Waiver Wire**: Encuentra las mejores oportunidades de agentes libres
- **⚖️ Simulador de Trades**: Evalúa el impacto de intercambios antes de hacerlos
- **🕵️ Intel de Liga**: Actividad reciente y noticias de la NBA

---

## 🚀 Instalación

### Requisitos Previos

- Python 3.11 o superior
- Cuenta de ESPN Fantasy Basketball
- Credenciales de tu liga (League ID, SWID, ESPN_S2)

### Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/tuusuario/fantasy-gm-tool.git
cd fantasy-gm-tool
```

### Paso 2: Crear Entorno Virtual

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Paso 3: Instalar Dependencias

```bash
pip install -r requirements.txt
```

### Paso 4: Configurar Credenciales

1. Copia el archivo de ejemplo:
   ```bash
   cp config/credenciales_ejemplo.py config/credenciales.py
   ```

2. Edita `config/credenciales.py` con tus datos:
   ```python
   LIGAS = {
       "Mi Liga": {
           "league_id": 123456789,
           "year": 2026,
           "swid": "{TU-SWID}",
           "espn_s2": "TU-ESPN-S2-TOKEN",
           "categorias": ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PTM', 'FG%', 'FT%', 'TO']
       }
   }
   ```

#### 🔑 Cómo Obtener tus Credenciales

1. Inicia sesión en ESPN Fantasy Basketball
2. Abre las herramientas de desarrollador (F12)
3. Ve a la pestaña "Application" > "Cookies"
4. Busca:
   - `SWID`: Copia el valor (incluye las llaves `{}`)
   - `espn_s2`: Copia el valor completo

---

## 🎮 Uso

### Ejecutar la Aplicación

```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en `http://localhost:8501`

### Navegación

1. **Sidebar**: Selecciona tu liga y ajusta configuraciones
2. **Grid Semanal**: Planifica tu semana de matchup
3. **Tabs**:
   - 🔥 **Hoy**: Análisis del día actual
   - ⚔️ **Matchup**: Estado actual del enfrentamiento
   - 🪓 **Cortes**: Candidatos para liberar espacio
   - 💎 **Waiver**: Mejores agentes libres disponibles
   - ⚖️ **Trade**: Simulador de intercambios
   - 🕵️ **Intel**: Actividad de liga y noticias

---

## 🛠️ Tecnologías

- **[Streamlit](https://streamlit.io/)**: Framework de aplicación web
- **[espn-api](https://github.com/cwendt94/espn-api)**: Cliente Python para ESPN Fantasy API
- **[Pandas](https://pandas.pydata.org/)**: Análisis de datos
- **[Requests](https://requests.readthedocs.io/)**: HTTP requests
- **[pytz](https://pythonhosted.org/pytz/)**: Manejo de zonas horarias

---

## 📊 Arquitectura

```
fantasy-gm-tool/
├── app.py                    # Aplicación principal
├── requirements.txt          # Dependencias
├── config/
│   ├── credenciales.py      # Credenciales de ligas (no incluido en repo)
│   └── credenciales_ejemplo.py
├── src/
│   └── conectar.py          # Conexión con ESPN API
└── README.md
```

### Funciones Clave

#### `get_calendario_semanal()`
Obtiene partidos de toda la semana para el Grid.
- **Cache**: 30 minutos
- **Returns**: `{"Lun 06": ["GSW", "LAL", ...], ...}`

#### `get_partidos_hoy()`
Obtiene solo partidos de HOY para análisis diario.
- **Cache**: 15 minutos
- **Returns**: `(["GSW", "LAL"], {"GSW": "LAL", ...})`

#### `normalizar_equipo(abrev)`
Normaliza abreviaturas de equipos (GS → GSW, SA → SAS).

#### `jugador_juega_hoy(pro_team, equipos_hoy)`
Verifica si un jugador tiene partido hoy.

---

## 🔧 Configuración Avanzada

### Ajustar Cache

Edita los valores de `ttl` en `app.py`:

```python
@st.cache_data(ttl=1800)  # 30 minutos
def get_calendario_semanal():
    ...

@st.cache_data(ttl=900)   # 15 minutos
def get_partidos_hoy():
    ...
```

### Logging

El nivel de logging se puede ajustar en `app.py`:

```python
logging.basicConfig(level=logging.INFO)  # INFO, DEBUG, WARNING, ERROR
```

---

## 🐛 Solución de Problemas

### Error: "No module named 'streamlit'"
```bash
pip install -r requirements.txt
```

### Error: "Invalid league credentials"
- Verifica que `SWID` y `espn_s2` sean correctos
- Asegúrate de que las cookies no hayan expirado (duran ~2 años)

### Grid muestra 0 vs 0
- Verifica tu conexión a internet
- Revisa los logs para errores de API
- Puede que no haya partidos hoy

### Jugadores no se detectan
- Verifica que la normalización de equipos funcione:
  ```python
  from app import normalizar_equipo
  print(normalizar_equipo('GS'))  # Debe retornar 'GSW'
  ```

---

## 📈 Mejoras v2.0 (Enero 2026)

### Cambios Principales

1. **Separación de Funciones**
   - `get_calendario_semanal()`: Solo para Grid
   - `get_partidos_hoy()`: Solo para análisis diario

2. **Zona Horaria Eastern**
   - Cambiada de UTC-4 a US/Eastern (ESPN)
   - Mejor sincronización con datos de ESPN

3. **Normalización Robusta**
   - Mapeo maestro ESPN → estándar
   - Maneja todas las variantes (GS/GSW, SA/SAS, etc.)

4. **Código Limpio**
   - Eliminadas ~100 líneas de código obsoleto
   - Mejor manejo de errores
   - Logging para debugging

5. **Performance**
   - Cache optimizado por función
   - Menos llamadas a API
   - Validaciones de datos

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas! Por favor:

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📝 Roadmap

- [ ] Soporte para múltiples ligas simultáneas
- [ ] Notificaciones push para oportunidades de waiver
- [ ] Análisis de tendencias históricas
- [ ] Predicciones con machine learning
- [ ] Modo oscuro/claro
- [ ] Export de reportes a PDF

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

---

## 👤 Autor

**Max**

- GitHub: [@tuusuario](https://github.com/tuusuario)

---

## 🙏 Agradecimientos

- [ESPN Fantasy API](https://github.com/cwendt94/espn-api) por el excelente wrapper
- [Streamlit](https://streamlit.io/) por el framework increíble
- Comunidad de Fantasy Basketball

---

## 📞 Soporte

Si encuentras algún bug o tienes sugerencias:

1. Abre un [Issue](https://github.com/tuusuario/fantasy-gm-tool/issues)
2. Describe el problema con detalles
3. Incluye logs si es posible

---

**¡Buena suerte en tu liga! 🏆**
