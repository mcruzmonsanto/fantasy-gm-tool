"""User Feedback Tracker - Sistema de aprendizaje basado en decisiones del usuario"""
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class UserFeedbackTracker:
    """Rastrea y aprende de las decisiones del usuario sobre recomendaciones de la IA"""
    
    def __init__(self, db_path='data/fantasy_brain.db'):
        import os
        # Ensure absolute path
        if not os.path.isabs(db_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, db_path)
            
        self.db_path = db_path
        self._ensure_tables()

    # ... existing code ...

    def should_show_recommendation(self, recommendation: dict) -> bool:
        """
        Determina si una recomendación debe mostrarse basándose en historial
        """
        try:
            drop_name = recommendation.get('drop_name')
            add_name = recommendation.get('add_name')
            
            # Obtener patrones rechazados recientes
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Buscar si el usuario rechazó esta EXACTA combinación antes
            # DEBUG log
            # logger.info(f"🔍 Checking history filter for: {drop_name} -> {add_name}")
            
            cursor.execute("""
                SELECT COUNT(*) FROM decisions_enhanced
                WHERE user_choice = 'REJECTED'
                AND player_dropped = ?
                AND player_added = ?
                AND decision_date >= date('now', '-30 days')
            """, (drop_name, add_name))
            
            exact_match = cursor.fetchone()[0]
            
            if exact_match > 0:
                logger.info(f"🚫 Filtering {add_name} for {drop_name} - found {exact_match} rejections in DB")
                conn.close()
                return False
            
            # Buscar si el usuario rechazó SOLTAR este jugador varias veces
            cursor.execute("""
                SELECT COUNT(*) FROM decisions_enhanced
                WHERE user_choice = 'REJECTED'
                AND player_dropped = ?
                AND decision_date >= date('now', '-30 days')
            """, (drop_name,))
            
            drop_rejections = cursor.fetchone()[0]
            
            if drop_rejections >= 3:
                logger.info(f"🚫 Filtering drop of {drop_name} - user rejected dropping them 3+ times")
                conn.close()
                return False
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking recommendation filter: {e}")
            return True  # En caso de error, mostrar la recomendación
    
    def get_statistics(self) -> Dict:
        """Obtiene estadísticas de uso del sistema de feedback"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Total de decisiones
            cursor.execute("SELECT COUNT(*) FROM decisions_enhanced")
            total = cursor.fetchone()[0]
            
            # Aceptadas vs Rechazadas
            cursor.execute("""
                SELECT user_choice, COUNT(*) 
                FROM decisions_enhanced 
                WHERE user_choice IN ('ACCEPTED', 'REJECTED')
                GROUP BY user_choice
            """)
            
            breakdown = {row[0]: row[1] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                'total_decisions': total,
                'accepted': breakdown.get('ACCEPTED', 0),
                'rejected': breakdown.get('REJECTED', 0),
                'acceptance_rate': breakdown.get('ACCEPTED', 0) / max(total, 1) * 100
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting statistics: {e}")
            return {
                'total_decisions': 0,
                'accepted': 0,
                'rejected': 0,
                'acceptance_rate': 0
            }


# Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    tracker = UserFeedbackTracker()
    
    # Test recommendation
    test_rec = {
        'drop_name': 'Test Player A',
        'add_name': 'Test Player B',
        'priority': 'HIGH',
        'confidence': 75,
        'projected_impact': 15.5,
        'add_analysis': {'opportunities': ['Expert rank #85']},
        'drop_analysis': {'opportunities': ['Expert rank #120']}
    }
    
    # Save feedback
    tracker.save_user_feedback(test_rec, 'ACCEPTED')
    
    # Get stats
    stats = tracker.get_statistics()
    print(f"\n📊 Stats: {stats}")
    
    print("\n✅ UserFeedbackTracker ready!")
