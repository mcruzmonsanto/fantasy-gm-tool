"""Conexión robusta con ESPN Fantasy API"""
import sys
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from espn_api.basketball import League
from loguru import logger
import requests

# Ajuste de rutas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configuración de logging mejorada
logger.add(
    "logs/fantasy_gm_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="INFO"
)

class ConnectionError(Exception):
    """Error personalizado de conexión"""
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, ConnectionError))
)
def obtener_liga(nombre_liga, config_dict):
    """
    Conecta a una liga con retry automático
    
    Args:
        nombre_liga: Nombre de la liga
        config_dict: Diccionario con configuración de liga
    
    Returns:
        League object o None
    
    Raises:
        ConnectionError: Si falla después de reintentos
    """
    if nombre_liga not in config_dict:
        logger.error(f"❌ Liga '{nombre_liga}' no existe en configuración")
        return None

    datos = config_dict[nombre_liga]
    
    try:
        logger.info(f"📡 Conectando a {nombre_liga}...")
        
        league = League(
            league_id=datos['league_id'], 
            year=datos['year'], 
            espn_s2=datos['espn_s2'], 
            swid=datos['swid']
        )
        
        # Validar que la conexión funciona
        _ = league.settings.name  # Trigger API call
        
        logger.success(f"✅ Conectado a {league.settings.name}")
        return league
        
    except requests.exceptions.Timeout as e:
        logger.warning(f"⏱️ Timeout conectando a {nombre_liga}: {e}")
        raise ConnectionError(f"Timeout: {e}")
        
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"🔌 Error de red conectando a {nombre_liga}: {e}")
        raise ConnectionError(f"Network error: {e}")
        
    except Exception as e:
        logger.error(f"❌ Error inesperado en {nombre_liga}: {e}")
        raise ConnectionError(f"Unexpected error: {e}")

def verificar_conexion(config_dict):
    """Verifica conexión a todas las ligas configuradas"""
    logger.info("🔍 VERIFICANDO CONEXIONES...")
    logger.info("=" * 60)
    
    resultados = {}
    
    for nombre in config_dict.keys():
        try:
            liga = obtener_liga(nombre, config_dict)
            
            if liga:
                resultados[nombre] = {
                    "status": "✅ ONLINE",
                    "nombre_liga": liga.settings.name,
                    "semana": liga.currentMatchupPeriod,
                    "equipos": len(liga.teams)
                }
            else:
                resultados[nombre] = {
                    "status": "❌ OFFLINE",
                    "error": "No se pudo conectar"
                }
                
        except Exception as e:
            resultados[nombre] = {
                "status": "❌ ERROR",
                "error": str(e)
            }
    
    # Imprimir resumen
    for nombre, info in resultados.items():
        logger.info(f"\n📊 {nombre}")
        for k, v in info.items():
            logger.info(f"   {k}: {v}")
    
    logger.info("\n" + "=" * 60)
    
    return resultados

# --- BLOQUE DE PRUEBA DE SISTEMA (SYSTEM CHECK) ---
if __name__ == "__main__":
    print("\n🖥️  INICIANDO VERIFICACIÓN DE SISTEMAS...")
    print("="*50)
    
    # Intentar cargar configuración
    try:
        from config_manager import ConfigManager
        config_mgr = ConfigManager()
        LIGAS = config_mgr.get_ligas()
    except ImportError:
        # Fallback a credenciales.py
        from config.credenciales import LIGAS
    
    if LIGAS:
        verificar_conexion(LIGAS)
    else:
        print("❌ No hay ligas configuradas")
    
    print("\n🏁 Verificación finalizada.")