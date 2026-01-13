"""Lineup Optimizer - Manages active lineup changes"""
import logging
from typing import List, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class LineupOptimizer:
    """Optimizes daily lineup based on games, injuries, and slot availability"""
    
    def __init__(self):
        pass
    
    def get_lineup_recommendations(
        self,
        roster: list,
        injuries: dict,
        today_games: list,
        categories: list
    ) -> List[dict]:
        """
        Analyzes entire roster and suggests lineup changes
        
        Returns list of recommendations:
        - ACTIVATE: Move from bench to active
        - BENCH: Move from active to bench
        - IR_TO_ACTIVE: Player recovered, move from IR
        - ACTIVE_TO_IR: Player injured, move to IR
        """
        recommendations = []
        
        # 1. Check IR slots - players that recovered
        ir_players = [p for p in roster if p.lineupSlot == 'IR']
        for player in ir_players:
            if self._should_activate_from_ir(player, injuries):
                recommendations.append({
                    'type': 'IR_TO_ACTIVE',
                    'priority': 'HIGH',
                    'player': player,
                    'player_name': player.name,
                    'reason': f"Ya no está OUT - mover a lineup activo",
                    'injury_status': injuries.get(player.name, {}).get('status', 'UNKNOWN'),
                    'plays_today': player.proTeam in today_games
                })
        
        # 2. Check bench - players that should be activated TODAY
        bench_players = [p for p in roster if p.lineupSlot == 'BE']
        for player in bench_players:
            if self._should_activate_from_bench(player, today_games, injuries):
                priority = 'HIGH' if player.proTeam in today_games else 'MEDIUM'
                recommendations.append({
                    'type': 'ACTIVATE',
                    'priority': priority,
                    'player': player,
                    'player_name': player.name,
                    'reason': f"Juega HOY - activar para sumar stats",
                    'injury_status': injuries.get(player.name, {}).get('status', 'HEALTHY'),
                    'plays_today': True
                })
        
        # 3. Check active lineup - players that should be benched
        active_players = [p for p in roster if p.lineupSlot not in ['IR', 'BE']]
        for player in active_players:
            if self._should_bench_player(player, injuries, today_games):
                priority = 'HIGH' if player.injuryStatus == 'OUT' else 'MEDIUM'
                recommendations.append({
                    'type': 'BENCH',
                    'priority': priority,
                    'player': player,
                    'player_name': player.name,
                    'reason': self._get_bench_reason(player, injuries, today_games),
                    'injury_status': injuries.get(player.name, {}).get('status', player.injuryStatus),
                    'plays_today': player.proTeam in today_games
                })
        
        # 4. Check for new injuries - players to move to IR
        for player in roster:
            if player.lineupSlot != 'IR' and self._should_move_to_ir(player, injuries):
                recommendations.append({
                    'type': 'ACTIVE_TO_IR',
                    'priority': 'HIGH',
                    'player': player,
                    'player_name': player.name,
                    'reason': f"OUT - libera espacio moviendo a IR",
                    'injury_status': injuries.get(player.name, {}).get('status', 'OUT'),
                    'plays_today': False
                })
        
        # Sort by priority
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        recommendations.sort(key=lambda x: priority_order[x['priority']])
        
        return recommendations
    
    def _should_activate_from_ir(self, player, injuries: dict) -> bool:
        """
        Check if IR player is ready to return
        Must NOT be OUT in either ESPN or scraped data
        """
        # First check ESPN injury status (most reliable)
        if hasattr(player, 'injuryStatus'):
            # If ESPN says OUT, definitely don't activate
            if player.injuryStatus == 'OUT':
                return False
            # If ESPN says anything else (QUESTIONABLE, PROBABLE, DAY_TO_DAY, etc), 
            # still check scraped data to be safe
        
        # Check scraped injuries (more detailed, might have return date)
        if player.name in injuries:
            status = injuries[player.name].get('status', '').upper()
            # Only activate if status is QUESTIONABLE, PROBABLE, or better
            # NOT if OUT or DOUBTFUL
            if status in ['OUT', 'DOUBTFUL']:
                return False
        
        # If we have no injury info at all, don't auto-suggest
        # (Better safe than sorry)
        if not hasattr(player, 'injuryStatus') and player.name not in injuries:
            return False
        
        # Only suggest activation if:
        # - ESPN doesn't say OUT
        # - Scraped data doesn't say OUT or DOUBTFUL
        # - We actually have injury info confirming they're better
        if hasattr(player, 'injuryStatus'):
            # Player has status and it's not OUT
            if player.injuryStatus in ['QUESTIONABLE', 'PROBABLE', 'DAY_TO_DAY']:
                return True
        
        if player.name in injuries:
            status = injuries[player.name].get('status', '').upper()
            if status in ['QUESTIONABLE', 'PROBABLE', 'ACTIVE']:
                return True
        
        return False
    
    def _should_activate_from_bench(self, player, today_games: list, injuries: dict) -> bool:
        """Check if bench player should be activated"""
        # Must be playing today
        if player.proTeam not in today_games:
            return False
        
        # Must not be injured
        if hasattr(player, 'injuryStatus') and player.injuryStatus == 'OUT':
            return False
        
        if player.name in injuries:
            status = injuries[player.name].get('status', '')
            if status in ['OUT', 'DOUBTFUL']:
                return False
        
        return True
    
    def _should_bench_player(self, player, injuries: dict, today_games: list) -> bool:
        """Check if active player should be benched"""
        # If OUT or SUSPENDED, definitely bench
        if hasattr(player, 'injuryStatus'):
            status = str(player.injuryStatus).upper()
            # Explicit suspension checks
            if status == 'OUT' or status == 'SUSPENSION' or status == 'SUSPENDED' or 'SUSPEND' in status or status == 'SSPD':
                return True
        
        if player.name in injuries:
            status = injuries[player.name].get('status', '').upper()
            if status == 'OUT' or status == 'SUSPENSION' or 'SUSPEND' in status or status == 'SSPD':
                return True
        
        # If not playing today and there are bench players playing
        if player.proTeam not in today_games:
            # This is a potential bench candidate
            return False  # For now, don't auto-suggest benching healthy players
        
        return False
    
    def _should_move_to_ir(self, player, injuries: dict) -> bool:
        """Check if player should be moved to IR"""
        # Must be OUT (SUSPENDED players should NOT go to IR, just bench)
        if hasattr(player, 'injuryStatus'):
            status = str(player.injuryStatus).upper()
            # Only OUT, NOT suspended
            if status == 'OUT' and status != 'SUSPENSION' and status != 'SUSPENDED' and 'SUSPEND' not in status:
                return True
        
        if player.name in injuries:
            status = injuries[player.name].get('status', '').upper()
            # Only OUT, NOT suspended
            if status == 'OUT' and 'SUSPEND' not in status:
                return True
        
        return False
    
    def _get_bench_reason(self, player, injuries: dict, today_games: list) -> str:
        """Get reason why player should be benched"""
        if hasattr(player, 'injuryStatus'):
            status = str(player.injuryStatus).upper()
            if status == 'SUSPENSION' or status == 'SUSPENDED' or 'SUSPEND' in status or status == 'SSPD':
                return "SUSPENDIDO - bench inmediatamente"
            if status == 'OUT':
                return "OUT - bench para liberar slot activo"
        
        if player.name in injuries:
            status = injuries[player.name].get('status', '').upper()
            if status == 'SUSPENSION' or 'SUSPEND' in status or status == 'SSPD':
                return f"SUSPENDIDO - bench inmediatamente"
            if status == 'OUT':
                return f"OUT ({injuries[player.name].get('injury', 'lesión')}) - bench"
        
        if player.proTeam not in today_games:
            return "No juega hoy - considera bench si hay mejor opción"
        
        return "Rendimiento bajo - considera bench"


# Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🔄 LineupOptimizer ready!")
