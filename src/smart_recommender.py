"""Smart Recommender - Coordinates all AI components for intelligent recommendations"""
from src.advanced_strategy import AdvancedStrategyAnalyzer
from src.lineup_optimizer import LineupOptimizer
from src.intelligence_engine import PlayerAnalyzer, RosterOptimizer
from src.data_scrapers import InjuryReportScraper, NewsScrapperScraper, ScheduleAnalyzer
from src.expert_scrapers import ExpertScrapers
from src.historical_analyzer import HistoricalAnalyzer
from src.ml_engine import MLDecisionEngine
from loguru import logger
from datetime import datetime
from typing import Dict, List
import os
import logging

logger = logging.getLogger(__name__)

class SmartRecommender:
    """Main recommendation system - NOW WITH: Playoff focus, acquisition management, timing, lineup optimization"""
    
    def __init__(self, league, config):
        self.league = league
        self.config = config
        db_path = 'data/fantasy_brain.db'
        
        self.player_analyzer = PlayerAnalyzer(db_path)
        self.optimizer = RosterOptimizer(self.player_analyzer)
        self.strategy_analyzer = AdvancedStrategyAnalyzer(self.league)
        self.lineup_optimizer = LineupOptimizer()
        self.lineup_optimizer = LineupOptimizer()
        
        # Scrapers
        self.injury_scraper = InjuryReportScraper()
        self.news_scraper = NewsScrapperScraper()
        self.schedule_analyzer = ScheduleAnalyzer()
        
        # NEW: Learning components
        self.expert_scrapers = ExpertScrapers(db_path)
        self.historical_analyzer = HistoricalAnalyzer(db_path)
        self.ml_engine = MLDecisionEngine(db_path)
        
        # Check if expert data is enabled
        self.expert_data_enabled = os.getenv('ENABLE_EXPERT_DATA', 'true').lower() == 'true'
        
        logger.info("✅ SmartRecommender initialized with LEARNING SYSTEM (expert data + ML)")
    
    
    def get_daily_recommendations(self, my_team, opponent, matchup, sos_map, today_games) -> dict:
        """
        Generate STRATEGIC recommendations for today
        NOW INCLUDES: Playoff context, matchup state, acquisition budget, timing
        
        Returns:
            {
                'context': {...},  # Strategic context
                'recommendations': [...],  # List of recommendations
                'strategic_message': str  # Overall strategy guidance
            }
        """
        try:
            logger.info("🔍 Starting ADVANCED daily analysis...")
            
            # 1. STRATEGIC CONTEXT
            playoff_ctx = self.strategy_analyzer.get_playoff_context()
            matchup_state = self.strategy_analyzer.analyze_matchup_state(my_team, matchup)
            
            # Pass league name for correct adds tracking
            league_name = self.league.settings.name if hasattr(self.league.settings, 'name') else None
            acq_budget = self.strategy_analyzer.check_acquisition_budget(my_team, matchup, league_name)
            
            today_analysis = self.strategy_analyzer.analyze_todays_matchup(my_team, opponent, today_games)
            
            logger.info(f"📊 Strategy: {playoff_ctx['strategy']} | Matchup: {matchup_state['recommendation']}")
            logger.info(f"💰 Adds remaining: {acq_budget['moves_remaining']} | Today advantage: {today_analysis['advantage']}")
            
            # 2. STRATEGIC DECISION
            should_make_moves = self._should_make_moves_now(matchup_state, acq_budget, today_analysis)
            
            if not should_make_moves['proceed']:
                return {
                    'context': {
                        'playoff': playoff_ctx,
                        'matchup': matchup_state,
                        'acquisitions': acq_budget,
                        'today': today_analysis
                    },
                    'recommendations': [],
                    'strategic_message': should_make_moves['reason']
                }
            
            
            # 3. COLLECT DATA (si debemos proceder)
            logger.info("📊 Collecting injury reports...")
            injuries = self.injury_scraper.get_injury_report()
            
            logger.info("📅 Analyzing schedules...")
            schedule_info = self._analyze_all_schedules(sos_map)
            
            # NEW: Get expert rankings (cached 24h)
            expert_data = {}
            if self.expert_data_enabled:
                logger.info("📊 Loading expert rankings...")
                try:
                    # Update if cache is old
                    self.expert_scrapers.update_all_expert_data()
                    
                    # Get today's rankings
                    expert_data = self.expert_scrapers.scrape_fantasypros_rankings(limit=200)
                    logger.info(f"✅ Loaded expert data for {len(expert_data)} players")
                except Exception as e:
                    logger.warning(f"⚠️ Expert data unavailable: {e}")
            
            # 4. Get roster and available players
            my_roster = my_team.roster
            available_players = self.league.free_agents(size=150)
            
            logger.info(f"👥 Analyzing {len(my_roster)} roster + {len(available_players)} FA")
            
            # 5. Find best moves WITH CONTEXT + EXPERT DATA + TODAY PROTECTION
            recommendations = self.optimizer.find_best_moves(
                my_roster=my_roster,
                available_players=available_players,
                injuries=injuries,
                schedule_info=schedule_info,
                categories=self.config['categorias'],
                expert_data=expert_data,
                today_games=list(today_games),  # NEW: Pass today's teams
                is_week_start=acq_budget.get('is_week_start', False),  # NEW: Week start flag
                league=self.league,  # NEW: Pass league for waiver checking
                top_n=5
            )
            
            # 6. FILTER by strategic context
            strategic_recs = self._filter_by_strategy(
                recommendations, 
                playoff_ctx, 
                matchup_state, 
                today_analysis
            )
            
            # 🔥 NEW: Filter by user history
            filtered_recs = self._filter_by_user_history(strategic_recs)
            
            logger.info(f"✅ Generated {len(filtered_recs)} STRATEGIC recommendations (after all filters)")
            
            # 7. LINEUP OPTIMIZATION (check bench/IR)
            lineup_recs = self.lineup_optimizer.get_lineup_recommendations(
                roster=my_roster,
                injuries=injuries,
                today_games=list(today_games),
                categories=self.config['categorias']
            )
            logger.info(f"🔄 Generated {len(lineup_recs)} lineup change suggestions")
            
            # 8. Generate strategic message
            strategic_msg = self._generate_strategic_message(
                playoff_ctx, matchup_state, acq_budget, today_analysis
            )
            
            return {
                'context': {
                    'playoff': playoff_ctx,
                    'matchup': matchup_state,
                    'acquisitions': acq_budget,
                    'today': today_analysis
                },
                'recommendations': filtered_recs,
                'lineup_changes': lineup_recs,  # NUEVO
                'strategic_message': strategic_msg
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating recommendations: {e}")
            return {
                'context': {},
                'recommendations': [],
                'strategic_message': f"Error: {e}"
            }
    
    def _analyze_all_schedules(self, sos_map) -> Dict:
        """Analyze schedules for all teams"""
        schedule_info = {}
        
        # Get unique teams from sos_map
        teams = list(sos_map.keys())
        
        for team in teams[:10]:  # Limit to avoid rate limiting
            try:
                games_count = self.schedule_analyzer.get_games_next_7_days(team)
                favorable = self.schedule_analyzer.get_favorable_matchups(team, sos_map)
                
                schedule_info[team] = {
                    'games_count': games_count,
                    'favorable_matchups': len(favorable)
                }
                
            except Exception as e:
                logger.debug(f"Could not analyze schedule for {team}: {e}")
                schedule_info[team] = {
                    'games_count': 0,
                    'favorable_matchups': 0
                }
        
        return schedule_info
    
    def _should_make_moves_now(self, matchup_state, acq_budget, today_analysis) -> dict:
        """Decide if we should make moves NOW or wait"""
        
        # Si NO quedan acquisitions, NO sugerir add/drops
        if acq_budget['moves_remaining'] == 0:
            return {
                'proceed': False,
                'reason': f"🚫 **Sin adds disponibles** (7/7 usados). Solo optimiza lineup sin gastar acquisitions."
            }
        
        # Si no quedan acquisitions suficientes
        if not acq_budget['can_afford']:
            return {
                'proceed': False,
                'reason': f"⚠️ Solo quedan {acq_budget['moves_remaining']} acquisiciones. Reserva para emergencias."
            }
        
        # Si ya ganamos cómodamente y quedan pocos días
        if matchup_state['winning'] and matchup_state['score_diff'] >= 4 and matchup_state['days_remaining'] <= 1:
            return {
                'proceed': False,
                'reason': f"✅ Ya ganaste {matchup_state['score_diff']} categorías. Ahorra acquisiciones para próxima semana."
            }
        
        # Si es último día y ya perdimos
        if matchup_state['days_remaining'] == 0 and not matchup_state['winning']:
            return {
                'proceed': True,
                'reason': "🎯 Último día. Optimizando para PRÓXIMA SEMANA con jugadores que jugarán lunes."
            }
        
        # Caso normal: hacer moves
        return {'proceed': True, 'reason': ''}
    
    def _filter_by_strategy(self, recommendations, playoff_ctx, matchup_state, today_analysis):
        """Filter recommendations by strategic context"""
        
        # Si es último día, priorizar jugadores que juegan al inicio de próxima semana
        if matchup_state['days_remaining'] == 0:
            # Aquí se podría filtrar por schedule de próxima semana
            return recommendations[:3]  # Solo top 3
        
        # Si estamos ganando, solo cambios de muy alto impacto
        if matchup_state['winning'] and matchup_state['score_diff'] >= 2:
            return [r for r in recommendations if r['projected_impact'] > 20]
        
        # Si estamos en playoffs, priorizar consistencia sobre upside
        if playoff_ctx['strategy'] == 'PLAYOFFS':
            # Filtrar jugadores muy inconsistentes
            filtered = [
                r for r in recommendations 
                if r['add_analysis']['consistency_score'] > 60
            ]
            return filtered if filtered else recommendations[:3]
        
        return recommendations
    
    def _filter_by_user_history(self, recommendations: list) -> list:
        """
        Filtra recomendaciones basándose en feedback pasado del usuario
        
        Evita mostrar:
        - Combinaciones exactas que el usuario rechazó antes
        - Jugadores que el usuario rechazó soltar múltiples veces
        
        Args:
            recommendations: Lista de recomendaciones
        
        Returns:
            Lista filtrada de recomendaciones
        """
        try:
            from src.user_feedback_tracker import UserFeedbackTracker
            tracker = UserFeedbackTracker()
            
            filtered = []
            for rec in recommendations:
                # Verificar si usuario rechazó algo similar antes
                if tracker.should_show_recommendation(rec):
                    filtered.append(rec)
                else:
                    logger.info(f"🚫 Skipping {rec['add_name']} for {rec['drop_name']} - user rejected similar before")
            
            return filtered
            
        except Exception as e:
            logger.warning(f"⚠️ Could not filter by user history: {e}")
            return recommendations  # Si falla, devolver todas
    
    def _generate_strategic_message(self, playoff_ctx, matchup_state, acq_budget, today_analysis):
        """Generate strategic guidance message"""
        
        msg = f"### 📊 Contexto Estratégico\n\n"
        
        # 🔥 NUEVO: Mensaje especial para inicio de semana
        is_week_start = acq_budget.get('is_week_start', False)
        if is_week_start:
            msg += f"🆕 **¡NUEVA SEMANA!** Matchup fresco con {acq_budget['weekly_limit']} adds disponibles\n\n"
            msg += f"💡 **Estrategia HOY:** Agresiva - Maximiza jugadores que juegan hoy (inicio de semana)\n\n"
        
        # Playoff context
        if playoff_ctx['strategy'] == 'PLAYOFFS':
            msg += f"🏆 **PLAYOFFS** | Prioriza consistencia y salud\n\n"
        elif playoff_ctx['strategy'] == 'BUILD_PLAYOFF':
            msg += f"🎯 **Preparando Playoffs** ({playoff_ctx['weeks_to_playoffs']} semanas) | Balance win now + futuro\n\n"
        else:
            msg += f"⚔️ **Modo Competitivo** | Enfócate en ganar esta semana\n\n"
        
        # Matchup state CON SCORES REALES
        cats_me = matchup_state['categories_ahead']
        cats_opp = matchup_state['categories_behind']
        cats_tied = matchup_state.get('categories_tied', 0)
        
        if matchup_state['winning']:
            msg += f"✅ **Ganando** {cats_me}-{cats_opp}"
            if cats_tied > 0:
                msg += f"-{cats_tied} (empatadas)"
            msg += " | "
            if matchup_state['days_remaining'] > 1:
                msg += "Mantén ventaja con moves inteligentes\n\n"
            elif matchup_state['days_remaining'] == 1:
                msg += "ÚLTIMO DÍA - asegura la victoria\n\n"
            else:
                msg += "Matchup terminó - prepara próxima semana\n\n"
        else:
            msg += f"⚠️ **Perdiendo** {cats_me}-{cats_opp}"
            if cats_tied > 0:
                msg += f"-{cats_tied}"
            msg += f" | Quedan {matchup_state['days_remaining']} días"
            
            if matchup_state['days_remaining'] == 0:
                msg += " - **OPTIMIZA PARA PRÓXIMA SEMANA**\n\n"
            else:
                msg += " - modo AGRESIVO 🔥\n\n"
        
        # Today's matchup
        if today_analysis['advantage'] == 'ME':
            msg += f"🔥 **HOY tienes ventaja**: {today_analysis['my_players_today']} jugadores vs {today_analysis['opp_players_today']}\n\n"
        elif today_analysis['advantage'] == 'OPP':
            msg += f"⚡ **Rival tiene ventaja HOY**: {today_analysis['opp_players_today']} vs {today_analysis['my_players_today']} tuyos\n\n"
        
        # Acquisition budget
        if acq_budget['warning']:
            msg += f"{acq_budget['warning']}\n\n"
        
        # Special message when NO adds remain (pero NO es inicio de semana)
        if acq_budget['moves_remaining'] == 0 and not is_week_start:
            msg += f"ℹ️ **Sin adds disponibles** - Solo mostrando cambios de lineup (bench/IR) que no cuestan acquisitions\n\n"
        
        return msg
    
    def explain_recommendation(self, rec: dict) -> str:
        """Generate detailed Spanish explanation"""
        
        priority_emoji = {
            'HIGH': '🔴',
            'MEDIUM': '🟡',
            'LOW': '🟢'
        }
        
        drop_analysis = rec['drop_analysis']
        add_analysis = rec['add_analysis']
        
        explanation = f"""
### {priority_emoji[rec['priority']]} Recomendación {rec['priority']}

#### ❌ **CORTA: {rec['drop_name']}**
- 💚 Salud: {drop_analysis['health_score']}/100
- 📈 Tendencia: {drop_analysis['trend_score']:+.0f}
- 📅 Schedule: {drop_analysis['schedule_score']}/100
- 📊 Score Total: **{drop_analysis['total_score']}/100**

**Problemas detectados:**
"""
        
        for issue in drop_analysis['issues']:
            explanation += f"\n- ⚠️ {issue}"
        
        if not drop_analysis['issues']:
            explanation += "\n- Sin problemas críticos"
        
        explanation += f"""

#### ✅ **FICHA: {rec['add_name']}**
"""
        
        # NEW: Check if injury replacement and add timeline warning
        is_injury_repl = add_analysis.get('is_injury_replacement', False)
        replacement_info = add_analysis.get('replacement_info', {})
        
        # Add badge to name if injury replacement  
        if is_injury_repl:
            explanation = explanation.replace(f"FICHA: {rec['add_name']}", f"FICHA: 🩺 {rec['add_name']}")
            
            # Add timeline warning after name
            if replacement_info.get('timeline_message'):
                explanation += f"""
> **⏰ OPORTUNIDAD TEMPORAL**  
> {replacement_info['timeline_message']}  
> **Relevancia estimada:** {replacement_info.get('estimated_return', 'Revisa actualizaciones')}  
> **Recomendación:** Úsalo esta semana, prepara reemplazo

"""
        
        explanation += f"""- 💚 Salud: {add_analysis['health_score']}/100
- 📈 Tendencia: {add_analysis['trend_score']:+.0f}
- 📅 Schedule: {add_analysis['schedule_score']}/100
- 📊 Score Total: **{add_analysis['total_score']}/100**

**Oportunidades:**
"""
        
        for opp in add_analysis['opportunities']:
            explanation += f"\n- 🎯 {opp}"
        
        if not add_analysis['opportunities']:
            explanation += "\n- Jugador consistente"
        
        explanation += f"""

#### 💡 **Impacto Proyectado**
- Mejora de score: **+{rec['projected_impact']} puntos**
- Confianza: **{rec['confidence']}%**

---
"""
        
        return explanation


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🧠 SmartRecommender module ready!")
