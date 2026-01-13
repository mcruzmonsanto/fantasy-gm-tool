"""Advanced Strategy Analyzer - Playoff-focused recommendations"""
import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AdvancedStrategyAnalyzer:
    """Analyzes strategic context: playoffs, acquisitions, timing"""
    
    def __init__(self, league):
        self.league = league
    
    def get_playoff_context(self) -> dict:
        """
        Determines playoff implications
        
        Returns:
            {
                'weeks_to_playoffs': int,
                'current_standing': int,
                'playoff_bound': bool,
                'must_win_weeks': int,
                'strategy': 'WIN_NOW' | 'BUILD_PLAYOFF' | 'PLAYOFFS'
            }
        """
        try:
            # Obtener standings
            standings = self.league.standings()
            my_team_id = self.league.teams[0].team_id  # Assuming first team is user's
            
            # Find user's position
            my_standing = next((i+1 for i, team in enumerate(standings) if team.team_id == my_team_id), 0)
            
            # ESPN usually has 18-20 week seasons, playoffs weeks 16-18
            current_week = self.league.current_week
            weeks_to_playoffs = max(0, 16 - current_week)
            
            # Top 6 usually make playoffs
            playoff_bound = my_standing <= 6
            
            # Determine strategy
            if current_week >= 16:
                strategy = 'PLAYOFFS'
            elif playoff_bound and weeks_to_playoffs <= 2:
                strategy = 'BUILD_PLAYOFF'  # Optimize for playoff roster
            else:
                strategy = 'WIN_NOW'  # Focus on weekly wins
            
            return {
                'weeks_to_playoffs': weeks_to_playoffs,
                'current_standing': my_standing,
                'playoff_bound': playoff_bound,
                'must_win_weeks': max(0, 8 - my_standing),  # Rough estimate
                'strategy': strategy,
                'current_week': current_week
            }
            
        except Exception as e:
            logger.error(f"Error analyzing playoff context: {e}")
            return {
                'weeks_to_playoffs': 10,
                'current_standing': 5,
                'playoff_bound': True,
                'must_win_weeks': 0,
                'strategy': 'WIN_NOW',
                'current_week': 1
            }
    
    def analyze_matchup_state(self, my_team, matchup) -> dict:
        """
        Analyzes current matchup state
        
        Returns:
            {
                'winning': bool,
                'categories_ahead': int,
                'categories_behind': int,
                'categories_tied': int,
                'can_win': bool,
                'days_remaining': int,
                'recommendation': 'AGGRESSIVE' | 'CONSERVATIVE' | 'PUNT'
            }
        """
        try:
            # Determine if user is home or away
            is_home = matchup.home_team.team_id == my_team.team_id
            
            # Get actual category scores from matchup
            # H2HCategoryBoxScore has: home_wins, away_wins, home_ties, away_ties
            if is_home:
                my_cats_won = matchup.home_wins
                opp_cats_won = matchup.away_wins
                tied_cats = matchup.home_ties
            else:
                my_cats_won = matchup.away_wins
                opp_cats_won = matchup.home_wins
                tied_cats = matchup.away_ties
            
            winning = my_cats_won > opp_cats_won
            score_diff = my_cats_won - opp_cats_won
            
            # Days remaining in matchup (ESPN: Lunes-Domingo)
            today = datetime.now()
            current_day = today.weekday()  # 0=Monday, 6=Sunday
            
            # Si es domingo (6), quedan 0 días
            # Si es sábado (5), queda 1 día
            # etc.
            days_remaining = 6 - current_day if current_day < 6 else 0
            
            # Strategic recommendation
            if days_remaining == 0:
                recommendation = 'PUNT'  # Matchup terminó o termina hoy
            elif winning and score_diff >= 3:
                recommendation = 'CONSERVATIVE'  # Mantener ventaja
            elif not winning and abs(score_diff) >= 3:
                recommendation = 'AGGRESSIVE'  # Necesitas cambios grandes
            else:
                recommendation = 'AGGRESSIVE'  # Default: pelear
            
            return {
                'winning': winning,
                'categories_ahead': my_cats_won,
                'categories_behind': opp_cats_won,
                'categories_tied': tied_cats,
                'can_win': days_remaining > 0 or (days_remaining == 0 and not winning),
                'days_remaining': days_remaining,
                'recommendation': recommendation,
                'score_diff': score_diff
            }
            
        except Exception as e:
            logger.error(f"Error analyzing matchup state: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'winning': False,
                'categories_ahead': 0,
                'categories_behind': 0,
                'categories_tied': 0,
                'can_win': True,
                'days_remaining': 1,
                'recommendation': 'AGGRESSIVE',
                'score_diff': 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing matchup state: {e}")
            return {
                'winning': False,
                'categories_ahead': 0,
                'categories_behind': 0,
                'can_win': True,
                'days_remaining': 3,
                'recommendation': 'AGGRESSIVE',
                'score_diff': 0
            }
    
    def check_acquisition_budget(self, my_team, current_matchup, league_name: str = None) -> dict:
        """
        Checks remaining acquisitions THIS WEEK
        
        NOTA: ESPN API no expone adds semanales directamente.
        Solución temporal: Configurar manualmente en .env como LIGA_X_WEEKLY_ADDS_USED
        
        **NEW**: Auto-detecta inicio de semana (lunes) y resetea contador a 0
        
        Args:
            league_name: Nombre de la liga para identificar variable correcta
            current_matchup: Matchup object para detectar inicio de periodo
        
        Returns:
            {
                'moves_remaining': int,
                'moves_used': int,
                'weekly_limit': int,
                'can_afford': bool,
                'warning': str
            }
        """
        try:
            # Límite semanal típico de ESPN
            weekly_limit = 7
            
            # Determinar qué variable de entorno leer según la liga
            import os
            
            # Si league_name tiene "10K" o es la primera, usar LIGA_1
            # Si tiene "2k" o es la segunda, usar LIGA_2
            if league_name and ('2k' in league_name.lower() or '2K' in league_name):
                env_var = 'LIGA_2_WEEKLY_ADDS_USED'
            else:
                env_var = 'LIGA_1_WEEKLY_ADDS_USED'
            
            moves_used_str = os.getenv(env_var, '0')
            try:
                moves_used = int(moves_used_str)
            except:
                moves_used = 0
            
            # 🔥 NUEVO: Auto-detectar inicio de semana
            today = datetime.now()
            current_day = today.weekday()  # 0=Monday, 6=Sunday
            
            # Si es LUNES (día 0), la semana acaba de iniciar -> resetear adds
            is_week_start = current_day == 0
            
            # También verificar si el matchup acaba de empezar (scores en 0)
            try:
                if current_matchup:
                    # Si ambos equipos tienen 0 victorias, es inicio de matchup
                    is_matchup_start = (current_matchup.home_wins == 0 and 
                                       current_matchup.away_wins == 0)
                    if is_matchup_start:
                        is_week_start = True
                        logger.info("🆕 Detectado INICIO DE MATCHUP - Resteando adds a 0/7")
            except:
                pass  # Si falla, usar solo detección de lunes
            
            # Si es inicio de semana, resetear a 0 (ignorar .env)
            if is_week_start:
                moves_used = 0
                logger.info(f"🔄 INICIO DE SEMANA DETECTADO - Adds reseteados a 0/{weekly_limit}")
            
            moves_remaining = weekly_limit - moves_used
            
            can_afford = moves_remaining >= 1  # At least 1 move left
            
            warning = ""
            if moves_remaining == 0:
                warning = f"🚫 **SIN ADDS!** Ya usaste {moves_used}/{weekly_limit} esta semana. Espera al lunes."
            elif moves_remaining == 1:
                warning = f"⚠️ **ÚLTIMO ADD!** Solo queda {moves_remaining}/{weekly_limit} esta semana. Úsalo sabiamente."
            elif moves_remaining == 2:
                warning = f"📊 Quedan {moves_remaining}/{weekly_limit} adds esta semana. Planifica bien."
            elif is_week_start and moves_remaining == 7:
                warning = f"🆕 **NUEVA SEMANA!** Tienes {weekly_limit} adds disponibles. ¡Optimiza tu roster!"
            
            return {
                'moves_remaining': moves_remaining,
                'moves_used': moves_used,
                'weekly_limit': weekly_limit,
                'can_afford': can_afford,
                'warning': warning,
                'is_week_start': is_week_start  # NEW: Para mensajes estratégicos
            }
            
        except Exception as e:
            logger.debug(f"Could not check acquisitions: {e}")
            return {
                'moves_remaining': 1,
                'moves_used': 6,  # Conservative estimate
                'weekly_limit': 7,
                'can_afford': True,
                'warning': "⚠️ Configura LIGA_X_WEEKLY_ADDS_USED en .env para tracking preciso",
                'is_week_start': False
            }
    
    def analyze_todays_matchup(self, my_team, opponent, today_games: list) -> dict:
        """
        Analyzes who has advantage TODAY specifically
        
        Returns:
            {
                'my_players_today': int,
                'opp_players_today': int,
                'advantage': 'ME' | 'OPP' | 'TIED',
                'my_power_today': float,
                'opp_power_today': float
            }
        """
        try:
            my_active = [p for p in my_team.roster if p.lineupSlot != 'IR']
            opp_active = [p for p in opponent.roster if p.lineupSlot != 'IR']
            
            # Count players playing today
            my_playing = sum(1 for p in my_active if p.proTeam in today_games)
            opp_playing = sum(1 for p in opp_active if p.proTeam in today_games)
            
            # Calculate power (score of players playing today)
            my_power = sum(
                self._quick_score(p) for p in my_active 
                if p.proTeam in today_games and p.injuryStatus != 'OUT'
            )
            
            opp_power = sum(
                self._quick_score(p) for p in opp_active 
                if p.proTeam in today_games and p.injuryStatus != 'OUT'
            )
            
            # Determine advantage
            if my_power > opp_power * 1.1:
                advantage = 'ME'
            elif opp_power > my_power * 1.1:
                advantage = 'OPP'
            else:
                advantage = 'TIED'
            
            return {
                'my_players_today': my_playing,
                'opp_players_today': opp_playing,
                'advantage': advantage,
                'my_power_today': round(my_power, 1),
                'opp_power_today': round(opp_power, 1),
                'power_diff': round(my_power - opp_power, 1)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing today's matchup: {e}")
            return {
                'my_players_today': 0,
                'opp_players_today': 0,
                'advantage': 'TIED',
                'my_power_today': 0,
                'opp_power_today': 0,
                'power_diff': 0
            }
    
    def _quick_score(self, player) -> float:
        """Quick score estimation for a player"""
        try:
            stats = player.stats.get('2026_last_7', {}).get('avg', {})
            if not stats:
                stats = player.stats.get('2026_total', {}).get('avg', {})
            
            if stats:
                return (stats.get('PTS', 0) + 
                        stats.get('REB', 0) * 1.2 + 
                        stats.get('AST', 0) * 1.5 + 
                        stats.get('STL', 0) * 2 + 
                        stats.get('BLK', 0) * 2)
            return 0
        except:
            return 0


# Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🧠 Advanced Strategy Analyzer ready!")
