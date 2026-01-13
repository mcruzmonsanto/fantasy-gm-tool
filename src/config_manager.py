"""Sistema de configuración moderno con validación"""
import os
from dotenv import load_dotenv
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Gestiona configuración desde .env con validación"""
    
    def __init__(self):
        load_dotenv()
        self.ligas = self._load_ligas()
    
    def _load_ligas(self) -> Dict:
        """Carga ligas desde variables de entorno"""
        ligas = {}
        i = 1
        
        while True:
            nombre = os.getenv(f"LIGA_{i}_NOMBRE")
            if not nombre:
                break
            
            try:
                liga_config = {
                    "league_id": int(os.getenv(f"LIGA_{i}_ID")),
                    "year": int(os.getenv(f"LIGA_{i}_YEAR")),
                    "swid": os.getenv(f"LIGA_{i}_SWID"),
                    "espn_s2": os.getenv(f"LIGA_{i}_ESPN_S2"),
                    "categorias": os.getenv(f"LIGA_{i}_CATEGORIAS").split(","),
                    "my_team_name": os.getenv(f"LIGA_{i}_MY_TEAM_NAME", "")  # Opcional
                }
                
                # Validación básica
                self._validate_liga(nombre, liga_config)
                ligas[nombre] = liga_config
                logger.info(f"✅ Liga '{nombre}' cargada correctamente")
                
            except Exception as e:
                logger.error(f"❌ Error cargando LIGA_{i} ({nombre}): {e}")
            
            i += 1
        
        if not ligas:
            logger.warning("⚠️ No se encontraron ligas en .env. Usando fallback a credenciales.py")
            try:
                from config.credenciales import LIGAS
                return LIGAS
            except ImportError:
                logger.error("❌ No hay credenciales disponibles")
                return {}
        
        return ligas
    
    def _validate_liga(self, nombre: str, config: Dict):
        """Valida configuración de liga"""
        required = ["league_id", "year", "swid", "espn_s2", "categorias"]
        
        for key in required:
            if not config.get(key):
                raise ValueError(f"Falta campo '{key}' para liga '{nombre}'")
        
        if not config["swid"].startswith("{"):
            raise ValueError(f"SWID debe empezar con {{ para liga '{nombre}'")
        
        if config["year"] < 2020 or config["year"] > 2030:
            raise ValueError(f"Año inválido para liga '{nombre}': {config['year']}")
    
    def get_ligas(self) -> Dict:
        """Retorna todas las ligas configuradas"""
        return self.ligas
    
    def get_cache_ttl(self, cache_type: str) -> int:
        """Obtiene TTL de cache desde config"""
        defaults = {
            "weekly": 1800,
            "daily": 900,
            "sos": 21600
        }
        env_key = f"CACHE_TTL_{cache_type.upper()}"
        return int(os.getenv(env_key, defaults.get(cache_type, 900)))
