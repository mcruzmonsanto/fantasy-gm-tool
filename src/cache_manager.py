"""Sistema de cache mejorado con indicadores visuales"""
from datetime import datetime
import streamlit as st
from cachetools import TTLCache
import pytz

class CacheManager:
    """Gestiona cache con metadata de frescura"""
    
    def __init__(self, timezone='US/Eastern'):
        self.tz = pytz.timezone(timezone)
        self.cache_metadata = {}
    
    def get_cache_status(self, cache_key: str, ttl: int) -> dict:
        """Retorna status del cache"""
        if cache_key not in self.cache_metadata:
            return {"fresh": False, "age": None}
        
        cached_time = self.cache_metadata[cache_key]
        now = datetime.now(self.tz)
        age_seconds = (now - cached_time).total_seconds()
        
        freshness = 1 - (age_seconds / ttl) if age_seconds < ttl else 0
        
        return {
            "fresh": age_seconds < ttl,
            "age": age_seconds,
            "freshness": freshness,
            "last_update": cached_time.strftime("%H:%M:%S")
        }
    
    def mark_cached(self, cache_key: str):
        """Marca un dato como cacheado"""
        self.cache_metadata[cache_key] = datetime.now(self.tz)
    
    def show_cache_indicator(self, label: str, cache_key: str, ttl: int):
        """Muestra indicador visual de frescura de cache"""
        status = self.get_cache_status(cache_key, ttl)
        
        if not status["fresh"]:
            icon = "🔴"
            msg = "Cargando datos frescos..."
        elif status["freshness"] > 0.7:
            icon = "🟢"
            msg = f"Datos frescos ({status['last_update']})"
        elif status["freshness"] > 0.3:
            icon = "🟡"
            msg = f"Datos recientes ({status['last_update']})"
        else:
            icon = "🟠"
            msg = f"Datos próximos a actualizar ({status['last_update']})"
        
        # st.caption(f"{icon} {label}: {msg}")
        pass
