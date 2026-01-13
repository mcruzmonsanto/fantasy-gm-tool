# Guía de Deployment - Fantasy GM Pro

Esta guía te ayudará a deployar Fantasy GM Pro en Streamlit Cloud.

## 📋 Prerequisitos

1. **Cuenta de GitHub**: Asegúrate de tener una cuenta en GitHub
2. **Repositorio Público/Privado**: El código debe estar en GitHub
3. **Credenciales de ESPN**: Necesitas tu SWID y ESPN_S2 token

## 🚀 Pasos para Deploy en Streamlit Cloud

### 1. Preparar el Repositorio

El código ya está listo para deployment. Asegúrate de que:
- ✅ El archivo `.env` NO esté comiteado (está en `.gitignore`)
- ✅ `requirements.txt` esté actualizado
- ✅ Todos los cambios estén pusheados a GitHub

### 2. Crear App en Streamlit Cloud

1. Ve a [share.streamlit.io](https://share.streamlit.io/)
2. Haz login con tu cuenta de GitHub
3. Click en **"New app"**
4. Completa el formulario:
   - **Repository**: `mcruzmonsanto/fantasy-gm-tool`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL**: Elige una URL personalizada (opcional)

### 3. Configurar Secretos (Variables de Entorno)

En la página de configuración de tu app, ve a **"Advanced settings"** → **"Secrets"**

Copia el contenido de tu archivo `.env` local en el formato TOML de Streamlit:

```toml
# Liga Principal
LIGA_1_NOMBRE = "Mi Liga Principal"
LIGA_1_ID = "123456789"
LIGA_1_YEAR = "2026"
LIGA_1_SWID = "{TU-SWID-AQUI}"
LIGA_1_ESPN_S2 = "TU_TOKEN_ESPN_S2_COMPLETO"
LIGA_1_CATEGORIAS = "PTS,REB,AST,STL,BLK,3PTM,FG%,FT%,TO"
LIGA_1_MY_TEAM_NAME = "Nombre de tu equipo"

# Liga Secundaria (si aplica)
LIGA_2_NOMBRE = "Liga Secundaria"
LIGA_2_ID = "987654321"
LIGA_2_YEAR = "2026"
LIGA_2_SWID = "{TU-SWID-LIGA-2}"
LIGA_2_ESPN_S2 = "TOKEN_LIGA_2"
LIGA_2_CATEGORIAS = "PTS,REB,AST,STL,BLK,3PTM,FG%,FT%,TO"
LIGA_2_MY_TEAM_NAME = "Nombre de tu equipo en liga 2"

# Configuración opcional
DEBUG_MODE = "false"
LOG_LEVEL = "INFO"
```

**Nota**: También puedes usar `.streamlit/secrets.toml.example` como referencia.

### 4. Deploy

1. Click en **"Deploy!"**
2. Streamlit Cloud instalará las dependencias automáticamente
3. La app comenzará a ejecutarse (puede tomar 2-3 minutos la primera vez)

### 5. Verificar Funcionamiento

Una vez deployada:
1. Abre la URL de tu app
2. Verifica que puedes seleccionar tu liga en el sidebar
3. Prueba que los datos se carguen correctamente en la tab "🔥 Hoy"
4. Verifica el matchup en la tab "⚔️ Matchup"

## 🔧 Troubleshooting

### Error: "ModuleNotFoundError"
- **Solución**: Verifica que todos los paquetes estén en `requirements.txt`
- Streamlit Cloud reinstala dependencias cada vez que haces push

### Error: "Failed to connect to ESPN API"
- **Solución**: Verifica que tus credenciales (SWID y ESPN_S2) sean correctas
- Los tokens ESPN pueden expirar; necesitarás actualizarlos periódicamente

### Error: "No data showing"
- **Solución**: 
  - Verifica que `LIGA_X_MY_TEAM_NAME` coincida con el nombre de tu equipo en ESPN
  - Asegúrate de que sea la semana de matchup activa

### La app se reinicia constantemente
- **Solución**: Revisa los logs en Streamlit Cloud
- Es posible que haya un error de importación o configuración

## 🔄 Actualizar la App

Para actualizar la app deployada:

```bash
# Hacer cambios en tu código local
git add .
git commit -m "Descripción de los cambios"
git push origin main
```

Streamlit Cloud detectará el push y re-deployará automáticamente.

## 📊 Obtener Credenciales de ESPN

Para obtener tu SWID y ESPN_S2 token:

1. Abre tu liga en [fantasy.espn.com](https://fantasy.espn.com)
2. Abre las herramientas de desarrollador (F12)
3. Ve a la pestaña **"Application"** (Chrome) o **"Storage"** (Firefox)
4. En **Cookies**, busca `fantasy.espn.com`
5. Copia los valores de:
   - `SWID` (formato: `{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}`)
   - `espn_s2` (un token muy largo)

## 🔒 Seguridad

- ✅ **NUNCA** compartas tus tokens ESPN públicamente
- ✅ **NUNCA** comitees archivos `.env` o `secrets.toml` a Git
- ✅ Usa siempre la sección "Secrets" de Streamlit Cloud para variables sensibles
- ✅ Los tokens ESPN pueden requerir renovación periódica

## 📞 Soporte

Si encuentras problemas:
1. Revisa los logs en Streamlit Cloud
2. Verifica que todas las dependencias estén instaladas
3. Consulta la [documentación oficial de Streamlit](https://docs.streamlit.io/)
