"""Intelligence Engine - V2.1 - WITH INJURY REPLACEMENT DETECTION"""

# Nota: Este archivo contiene solo las nuevas funciones que se agregarán a intelligence_engine.py
# Para ser insertadas en la clase PlayerAnalyzer después de _calculate_consistency_score

def _detect_injury_replacement(self, player, injuries: dict, expert_data: dict = None, schedule_score: float = 0) -> dict:
    """
    Detects if a player is an 'injury replacement' (temporary opportunity)
    
    Criteria:
    1. Low historical expert rank (>150) BUT high schedule score (>80)
    2. Recent minutes spike vs season average
    3. Team has injured starter in same position
    
    Returns:
        {
            'is_replacement': bool,
            'replacing': str | None,  # name of injured starter
            'injury_type': str,
            'estimated_return': str,  # '7-10 days', '2-3 weeks', etc.
            'timeline_message': str  # Human-readable message
        }
    """
    result = {
        'is_replacement': False,
       'replacing': None,
        'injury_type': '',
        'estimated_return': '',
        'timeline_message': ''
    }
    
    try:
        player_name = player.name
        
        # Criterion 1: Schedule spike without historical value
        # (Good schedule but low expert rank = probably benefiting from injuries)
        has_schedule_spike = schedule_score > 80
        
        low_historical_rank = True
        if expert_data and player_name in expert_data:
            rank = expert_data[player_name].get('fantasypros_rank', 999)
            if rank <= 150:
                low_historical_rank = False
        
        # Criterion 2: Minutes spike in last 7 games
        has_minutes_spike = False
        try:
            stats_7 = player.stats.get('2026_last_7', {}).get('avg', {})
            stats_total = player.stats.get('2026_total', {}).get('avg', {})
            
            mpg_7 = stats_7.get('MIN', 0)
            mpg_season = stats_total.get('MIN', 0)
            
            if mpg_season > 0 and mpg_7 > mpg_season * 1.3:  # 30%+ increase
                has_minutes_spike = True
                logger.info(f"📈 {player_name}: Minutes spike {mpg_season:.1f} → {mpg_7:.1f}")
        except:
            pass
        
        # If both conditions met, likely injury replacement
        if has_schedule_spike and (low_historical_rank or has_minutes_spike):
            # Try to find who they're replacing
            team = player.proTeam if hasattr(player, 'proTeam') else None
            
            if team and injuries:
                # Look for injured teammates
                for injured_name, injury_data in injuries.items():
                    injured_team = injury_data.get('team', '')
                    
                    # Same team and OUT status
                    if injured_team == team and injury_data.get('status') == 'OUT':
                        # Found likely injured starter
                        injury_type = injury_data.get('type', 'injury')
                        
                        # Estimate return timeline
                        timeline = self.injury_estimator.estimate_return(
                            'OUT',
                            injury_type
                        )
                        
                        result = {
                            'is_replacement': True,
                            'replacing': injured_name,
                            'injury_type': injury_type,
                            'estimated_return': timeline['description'],
                            'timeline_message': self.injury_estimator.get_timeline_message(
                                'OUT', injury_type, injured_name
                            )
                        }
                        
                        logger.info(f"🩺 {player_name} identified as injury replacement for {injured_name}")
                        break
            
            # Even if we can't identify WHO, flag as likely temp opportunity
            if not result['is_replacement'] and has_minutes_spike:
                result['is_replacement'] = True
                result['timeline_message'] = f"⚠️ {player_name} tiene minutos elevados recientes - posible oportunidad temporal"
        
    except Exception as e:
        logger.debug(f"Error detecting injury replacement for {player.name}: {e}")
    
    return result
