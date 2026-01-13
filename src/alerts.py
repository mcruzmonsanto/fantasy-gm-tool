"""Sistema de alertas inteligentes"""
import streamlit as st
from datetime import datetime, timedelta
import pytz

class AlertSystem:
    """Gestiona alertas y notificaciones"""
    
    def __init__(self, timezone='US/Eastern'):
        self.tz = pytz.timezone(timezone)
        self.alerts = []
    
    def check_waiver_opportunities(self, free_agents, threshold_score=50):
        """Detecta oportunidades HOT en waiver"""
        hot_picks = [p for p in free_agents if p.get('score', 0) > threshold_score]
        
        if hot_picks:
            self.alerts.append({
                "type": "waiver_hot",
                "severity": "high",
                "message": f"🔥 {len(hot_picks)} jugadores HOT en waiver",
                "data": hot_picks
            })
    
    def check_injured_players(self, roster):
        """Alerta sobre jugadores lesionados"""
        injured = [p for p in roster if p.injuryStatus == 'OUT']
        
        if injured:
            self.alerts.append({
                "type": "injury",
                "severity": "medium",
                "message": f"⚠️ {len(injured)} jugadores OUT en tu roster",
                "data": injured
            })
    
    def check_underperforming_players(self, roster, min_score=15):
        """Detecta jugadores de bajo rendimiento"""
        underperformers = [p for p in roster if hasattr(p, 'score') and p.score < min_score]
        
        if underperformers:
            self.alerts.append({
                "type": "performance",
                "severity": "low",
                "message": f"📉 {len(underperformers)} jugadores bajo rendimiento",
                "data": underperformers
            })
    
    def show_alerts(self):
        """Muestra alertas en UI"""
        if not self.alerts:
            return
        
        st.divider()
        st.subheader("🚨 Alertas")
        
        for alert in self.alerts:
            if alert["severity"] == "high":
                st.error(alert["message"])
            elif alert["severity"] == "medium":
                st.warning(alert["message"])
            else:
                st.info(alert["message"])
        
        self.alerts = []  # Clear después de mostrar
    
    def clear_alerts(self):
        """Limpia todas las alertas"""
        self.alerts = []
