"""Intelligence Engine - Analyzes players and generates recommendations"""
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging
import numpy as np
from src.injury_timeline_estimator import InjuryTimelineEstimator

logger = logging.getLogger(__name__)

class PlayerAnalyzer:
    """Analyzes individual player performance, health, and value"""
    
    def __init__(self, db_path='data/fantasy_brain.db'):
        self.db_path = db_path
        self.injury_estimator = InjuryTimelineEstimator()
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database with enhanced historical tracking"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Original table: player stats history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS player_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER,
                    player_name TEXT,
                    date DATE,
                    pts REAL,
                    reb REAL,
                    ast REAL,
                    stl REAL,
                    blk REAL,
                    threepm REAL,
                    fg_pct REAL,
                    ft_pct REAL,
                    turnovers REAL,
                    games_played INTEGER,
                    injury_status TEXT,
                    UNIQUE(player_name, date)
                )
            ''')
            
            # NEW: Matchup history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS matchup_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    league_id TEXT,
                    league_name TEXT,
                    week_number INTEGER,
                    season_year INTEGER,
                    my_team_name TEXT,
                    opponent_team_name TEXT,
                    
                    -- Final scores (category wins)
                    final_score_me INTEGER,
                    final_score_opp INTEGER,
                    tied_cats INTEGER,
                    
                    -- Aggregated stats
                    my_total_pts REAL,
                    my_total_reb REAL,
                    my_total_ast REAL,
                    my_total_stl REAL,
                    my_total_blk REAL,
                    my_total_3ptm REAL,
                    my_fg_pct REAL,
                    my_ft_pct REAL,
                    my_to REAL,
                    
                    opp_total_pts REAL,
                    opp_total_reb REAL,
                    opp_total_ast REAL,
                    opp_total_stl REAL,
                    opp_total_blk REAL,
                    opp_total_3ptm REAL,
                    opp_fg_pct REAL,
                    opp_ft_pct REAL,
                    opp_to REAL,
                    
                    -- Result
                    won BOOLEAN,
                    strategy_used TEXT,  -- 'AGGRESSIVE', 'CONSERVATIVE', 'PUNT'
                    date_completed DATE,
                    
                    UNIQUE(league_id, week_number, season_year)
                )
            ''')
            
            # NEW: Enhanced decisions tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS decisions_enhanced (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_date DATE,
                    league_id TEXT,
                    matchup_id INTEGER,
                    
                    -- Decision details
                    action_type TEXT,
                    player_dropped TEXT,
                    player_added TEXT,
                    
                    -- AI context
                    ai_recommendation TEXT,
                    user_choice TEXT,
                    ai_confidence INTEGER,
                    ai_reasoning TEXT,
                    
                    -- Expert data (populated if available)
                    fantasypros_add_rank INTEGER,
                    fantasypros_drop_rank INTEGER,
                    rotowire_projection_add REAL,
                    rotowire_projection_drop REAL,
                    twitter_sentiment TEXT,
                    
                    -- Impact tracking (updated 7 days later)
                    player_added_avg_7d REAL,
                    player_dropped_avg_7d REAL,
                    impact_score REAL,
                    was_good_decision BOOLEAN,
                    
                    user_feedback TEXT,
                    
                    FOREIGN KEY (matchup_id) REFERENCES matchup_history(id)
                )
            ''')
            
            # NEW: Expert rankings cache
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expert_rankings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT,
                    source TEXT,
                    ranking_date DATE,
                    
                    overall_rank INTEGER,
                    position_rank INTEGER,
                    
                    -- Category-specific ranks (JSON)
                    category_ranks TEXT,
                    
                    -- Projected stats (JSON)
                    projected_stats TEXT,
                    
                    -- Start/Sit recommendation
                    start_sit_rating TEXT,
                    expert_notes TEXT,
                    
                    UNIQUE(player_name, source, ranking_date)
                )
            ''')
            
            # Original decisions table (keep for backwards compatibility)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE,
                    action TEXT,
                    player_dropped TEXT,
                    player_added TEXT,
                    reason TEXT,
                    projected_impact REAL,
                    actual_impact REAL,
                    was_successful BOOLEAN,
                    user_feedback TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("✅ Database initialized with historical learning tables")
            
        except Exception as e:
            logger.error(f"❌ Error initializing database: {e}")
    
    def analyze_player(self, player, injuries: dict, schedule_info: dict, categories: list, expert_data: dict = None) -> dict:
        """
        Comprehensive player analysis WITH EXPERT DATA INTEGRATION
        
        Args:
            expert_data: Optional dict from ExpertScrapers with rankings
        
        Returns:
            {
                'health_score': 0-100,
                'trend_score': -100 to +100,
                'schedule_score': 0-100,
                'consistency_score': 0-100,
                'expert_score': 0-100,  # NEW
                'total_score': 0-100,
                'issues': ['DTD - Ankle'],
                'opportunities': ['4 games next week', 'Expert rank #45']
            }
        """
        player_name = player.name
        
        # Calculate individual scores
        health_score = self._calculate_health_score(player, injuries)
        trend_score = self._calculate_trend_score(player, categories)
        schedule_score = self._calculate_schedule_score(player, schedule_info)
        consistency_score = self._calculate_consistency_score(player)
        
        # NEW: Expert score
        expert_score = self._calculate_expert_score(player_name, expert_data)
        
        # NEW: Detect injury replacement status
        injury_replacement = self._detect_injury_replacement(player, injuries, expert_data, schedule_score)
        
        # Weighted total score WITH EXPERT DATA
        total_score = (
            health_score * 0.30 +  # Health still critical
            (trend_score + 100) / 2 * 0.25 +  # Normalize trend to 0-100
            schedule_score * 0.20 +
            consistency_score * 0.10 +
            expert_score * 0.15  # NEW: Expert data factor
        )
        
        # Identify issues and opportunities  
        issues = []
        opportunities = []
        
        if health_score < 70:
            issues.append(f"Health concern: {health_score:.0f}/100")
        
        if trend_score < -20:
            issues.append(f"Declining performance: {trend_score:+.0f}%")
        
        if schedule_score > 70:
            opportunities.append(f"Great schedule: {schedule_score:.0f}/100")
        
        if consistency_score < 50:
            issues.append(f"Inconsistent: {consistency_score:.0f}/100")
        
        # NEW: Expert insights
        if expert_score > 70:
            if expert_data and player_name in expert_data:
                rank = expert_data[player_name].get('fantasypros_rank', 999)
                if rank <= 100:
                    opportunities.append(f"📊 Expert rank #{rank} (Top 100)")
        
        # NEW: Injury replacement opportunity (only if we know who)
        if injury_replacement['is_replacement'] and injury_replacement.get('replacing'):
            opportunities.append(f"🩺 Injury replacement for {injury_replacement['replacing']}")
        
        return {
            'player_name': player_name,
            'health_score': round(health_score, 1),
            'trend_score': round(trend_score, 1),
            'schedule_score': round(schedule_score, 1),
            'consistency_score': round(consistency_score, 1),
            'expert_score': round(expert_score, 1),  # NEW
            'total_score': round(total_score, 1),
            'issues': issues,
            'opportunities': opportunities,
            'is_injury_replacement': injury_replacement['is_replacement'],  # NEW
            'replacement_info': injury_replacement  # NEW
        }
    
    def _calculate_expert_score(self, player_name: str, expert_data: dict = None) -> float:
        """
        Calculate score based on expert rankings
        
        Returns: 0-100 (higher = better expert consensus)
        """
        if not expert_data or player_name not in expert_data:
            return 50.0  # Neutral if no data
        
        player_expert = expert_data[player_name]
        rank = player_expert.get('fantasypros_rank', 999)
        
        # Convert rank to score (lower rank = higher score)
        if rank <= 50:
            return 100.0
        elif rank <= 100:
            return 85.0
        elif rank <= 150:
            return 70.0
        elif rank <= 200:
            return 55.0
        else:
            return 40.0
    
    def _calculate_health_score(self, player, injuries: dict) -> float:
        """
        Analyzes injury status INCLUDING SUSPENSIONS
        
        Returns: 0-100 (100 = perfectly healthy, 0 = OUT or SUSPENDED)
        """
        player_name = player.name
        
        if player_name in injuries:
            status = injuries[player_name]['status'].upper()
            
            if status == 'OUT':
                return 0.0
            elif status == 'SUSPENSION' or 'SUSPEND' in status or status == 'SSPD':
                logger.info(f"⚠️ SUSPENDED DETECTED via scraper: {player_name}")
                return 0.0  # Suspensiones son peor - no juega
            elif status == 'DOUBTFUL':
                return 20.0
            elif status == 'QUESTIONABLE':
                return 50.0
            elif status == 'PROBABLE':
                return 75.0
        
        # Check if player has DTD or suspended status from ESPN
        if hasattr(player, 'injuryStatus'):
            status = str(player.injuryStatus).upper()
            
            if status == 'OUT':
                return 0.0
            # Explicit checks for suspension variants
            elif status == 'SUSPENSION' or status == 'SUSPENDED' or 'SUSPEND' in status or status == 'SSPD':
                logger.info(f"⚠️ SUSPENDED DETECTED via ESPN: {player_name} (status={status})")
                return 0.0  # Suspended - definitivamente no juega
            elif status == 'DAY_TO_DAY':
                return 60.0
        
        return 100.0
    
    def _calculate_trend_score(self, player, categories: list) -> float:
        """
        Analyzes performance trend (improving/declining)
        NOW WITH: Efficiency per minute + Starter bonus
        
        Returns: -100 to +100 (negative = declining, positive = improving)
        """
        try:
            # Get last 7 and last 15 games stats
            stats_7 = player.stats.get('2026_last_7', {}).get('avg', {})
            stats_15 = player.stats.get('2026_last_15', {}).get('avg', {})
            
            if not stats_7 or not stats_15:
                return 0.0  # Not enough data
            
            # Calculate change in key stats
            changes = []
            
            for cat in categories:
                val_7 = stats_7.get(cat, 0)
                val_15 = stats_15.get(cat, 0)
                
                if val_15 > 0:
                    # Percentage change
                    if cat == 'TO':
                        # For turnovers, negative change is good
                        change = -((val_7 - val_15) / val_15) * 100
                    else:
                        change = ((val_7 - val_15) / val_15) * 100
                    
                    changes.append(change)
            
            # NUEVO: Efficiency per minute analysis
            mpg_7 = stats_7.get('MIN', 0)
            mpg_15 = stats_15.get('MIN', 0)
            
            efficiency_bonus = 0
            if mpg_7 > 0 and mpg_15 > 0:
                # Points per minute efficiency
                pts_7 = stats_7.get('PTS', 0)
                pts_15 = stats_15.get('PTS', 0)
                
                eff_7 = pts_7 / mpg_7 if mpg_7 > 0 else 0
                eff_15 = pts_15 / mpg_15 if mpg_15 > 0 else 0
                
                # Bonus si produce más en menos minutos (eficiencia)
                if eff_7 > eff_15 and mpg_7 < mpg_15:
                    efficiency_bonus = 15  # Gran bonus por mayor eficiencia
                elif eff_7 > eff_15:
                    efficiency_bonus = 10
                
                # NUEVO: Estabilidad de minutos (menos variación = mejor)
                min_stability = 100 - abs(mpg_7 - mpg_15) * 2
                if min_stability > 80:  # Minutos estables
                    efficiency_bonus += 5
            
            # Average change + efficiency bonuses
            if changes:
                avg_change = np.mean(changes)
                final_score = avg_change + efficiency_bonus
                
                # Clamp to -100 to +100
                return max(-100, min(100, final_score))
            
        except Exception as e:
            logger.debug(f"Could not calculate trend for {player.name}: {e}")
        
        return 0.0
    
    def _calculate_schedule_score(self, player, schedule_info: dict) -> float:
        """
        Analyzes upcoming schedule
        
        Returns: 0-100 (100 = best schedule)
        """
        try:
            team = player.proTeam
            
            # Number of games in next 7 days
            games_next_7 = schedule_info.get(team, {}).get('games_count', 0)
            
            # Favorable matchups
            favorable_count = schedule_info.get(team, {}).get('favorable_matchups', 0)
            
            # Score based on games (max 4+ games = 100)
            games_score = min(100, (games_next_7 / 4) * 100)
            
            # Bonus for favorable matchups
            favorable_bonus = favorable_count * 10
            
            total_score = min(100, games_score + favorable_bonus)
            
            return total_score
            
        except Exception as e:
            logger.debug(f"Could not calculate schedule for {player.name}: {e}")
            return 50.0  # Average
    
    def _calculate_consistency_score(self, player) -> float:
        """
        Analyzes consistency of performance
        
        Returns: 0-100 (100 = very consistent)
        """
        try:
            # Get last 15 games
            stats_15 = player.stats.get('2026_last_15', {}).get('avg', {})
            
            if not stats_15:
                return 50.0
            
            # Simple heuristic: players with higher stats are usually more consistent
            pts = stats_15.get('PTS', 0)
            
            if pts > 20:
                return 80.0
            elif pts > 15:
                return 70.0
            elif pts > 10:
                return 60.0
            else:
                return 50.0
                
        except Exception as e:
            logger.debug(f"Could not calculate consistency for {player.name}: {e}")
            return 50.0
    
    def _detect_injury_replacement(self, player, injuries: dict, expert_data: dict = None, schedule_score: float = 0) -> dict:
        """
        Detects if a player is an 'injury replacement' (temporary opportunity)
        
        Returns:
            {
                'is_replacement': bool,
                'replacing': str | None,
                'injury_type': str,
                'estimated_return': str,
                'timeline_message': str
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
            has_schedule_spike = schedule_score > 80
            logger.info(f"🔍 Checking {player_name}: schedule={schedule_score}, spike={has_schedule_spike}")
            
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
                team = str(player.proTeam).upper() if hasattr(player, 'proTeam') else None
                logger.info(f"🔍 {player_name} passed criteria, team={team}, checking injuries...")
                
                # DEBUG: Special logging for Nnaji
                if 'nnaji' in player_name.lower():
                    logger.info(f"🚨 NNAJI DEBUG: team={team}, injuries has {len(injuries)} players")
                    if 'Nikola Jokic' in injuries:
                        jokic_data = injuries['Nikola Jokic']
                        logger.info(f"🚨 JOKIC FOUND: team={jokic_data.get('team')}, status={jokic_data.get('status')}")
                    else:
                        logger.info(f"🚨 JOKIC NOT IN INJURIES DICT. Keys: {list(injuries.keys())[:10]}")
                
                if team and injuries:
                    logger.info(f"🔍 Injuries dict has {len(injuries)} players")
                    # Look for injured teammates (need to normalize team comparison)
                    for injured_name, injury_data in injuries.items():
                        injured_team = str(injury_data.get('team', '')).upper()
                        injured_status = injury_data.get('status', '').upper()
                        
                        # Match teams (handle abbreviations: DEN, Denver, etc.)
                        teams_match = (
                            injured_team == team or 
                            team in injured_team or 
                            injured_team in team
                        )
                        
                        if teams_match:
                            logger.info(f"🔍 Found teammate {injured_name}: status={injured_status}, team={injured_team}")
                        
                        if teams_match and injured_status == 'OUT':
                            injury_type = injury_data.get('type', 'injury')
                            
                            timeline = self.injury_estimator.estimate_return('OUT', injury_type)
                            
                            result = {
                                'is_replacement': True,
                                'replacing': injured_name,
                                'injury_type': injury_type,
                                'estimated_return': timeline['description'],
                                'timeline_message': self.injury_estimator.get_timeline_message('OUT', injury_type, injured_name)
                            }
                            
                            logger.info(f"🩺 {player_name} identified as injury replacement for {injured_name} ({team})")
                            break
                
                # If we detected spike but couldn't identify who, still mark as temp opportunity
                if not result['is_replacement'] and has_minutes_spike:
                    result['is_replacement'] = True
                    result['timeline_message'] = f"⚠️ {player_name} tiene minutos elevados recientes - posible oportunidad temporal"
            
        except Exception as e:
            logger.debug(f"Error detecting injury replacement for {player.name}: {e}")
        
        return result

    def compare_rosters_expert_strength(self, roster_a: list, roster_b: list, expert_data: dict) -> dict:
        """
        Compares two rosters based on expert rankings
        """
        empty_stats = {'top50': 0, 'top100': 0, 'avg_rank': 200}
        
        if not expert_data:
            return {
                'advantage': 'UNKNOWN', 
                'details': 'No expert data available', 
                'my_stats': empty_stats, 
                'opp_stats': empty_stats,
                'score_diff': 0
            }
            
        def get_roster_stats(roster):
            top50 = 0
            top100 = 0
            total_rank = 0
            count = 0
            
            for p in roster:
                # Handle both Player object and dictionary if needed, mostly Player object
                name = p.name if hasattr(p, 'name') else str(p)
                
                if name in expert_data:
                    rank = expert_data[name].get('fantasypros_rank', 200)
                    if rank <= 50: top50 += 1
                    if rank <= 100: top100 += 1
                    total_rank += rank
                    count += 1
                else:
                    # Penalty for unknown players (likely waiver wire level)
                    total_rank += 200
                    count += 1
            
            avg_rank = total_rank / count if count > 0 else 200
            return {'top50': top50, 'top100': top100, 'avg_rank': avg_rank}

        stats_a = get_roster_stats(roster_a)
        stats_b = get_roster_stats(roster_b)
        
        # Determine advantage
        # Algorithm: Top 50 worth 3x, Top 100 worth 1x
        score_a = (stats_a['top50'] * 3) + stats_a['top100']
        score_b = (stats_b['top50'] * 3) + stats_b['top100']
        
        if score_a > score_b + 1:
            adv = 'ME'
        elif score_b > score_a + 1:
            adv = 'OPP'
        elif stats_a['avg_rank'] < stats_b['avg_rank'] - 10:
            adv = 'ME'
        elif stats_b['avg_rank'] < stats_a['avg_rank'] - 10:
            adv = 'OPP'
        else:
            adv = 'TIED'
            
        return {
            'advantage': adv,
            'my_stats': stats_a,
            'opp_stats': stats_b,
            'score_diff': score_a - score_b
        }


class RosterOptimizer:
    """Finds optimal add/drop combinations"""
    
    def __init__(self, analyzer: PlayerAnalyzer):
        self.analyzer = analyzer
    
    def find_best_moves(
        self,
        my_roster: list,
        available_players: list,
        injuries: dict,
        schedule_info: dict,
        categories: list,
        expert_data: dict = None,
        top_n: int = 5,
        today_games: list = None,  # NEW: Teams playing today
        is_week_start: bool = False  # NEW: Week start flag
    ) -> List[dict]:
        """
        Finds the best add/drop moves WITH EXPERT DATA + TODAY PROTECTION
        
        NEW: Filters waiver players and protects players playing today
        
        Returns:
            List of recommendations sorted by projected impact
        """
        recommendations = []
        
        # Analyze all roster players WITH EXPERT DATA
        roster_scores = {}
        for player in my_roster:
            if player.lineupSlot != 'IR':  # Don't analyze IR players
                analysis = self.analyzer.analyze_player(
                    player, injuries, schedule_info, categories, expert_data  # NEW
                )
                roster_scores[player.name] = analysis
        
        # Analyze available players WITH EXPERT DATA
        # 🔥 NEW: Filter out WAIVER players (not available immediately)
        available_scores = {}
        waiver_skipped = 0
        
        for player in available_players[:100]:  # Top 100 available
            # Skip players on WAIVER (only Free Agents)
            if hasattr(player, 'onTeamId'):
                if player.onTeamId != 0:
                    waiver_skipped += 1
                    logger.debug(f"⏭️ Skipping {player.name} - on waiver (onTeamId={player.onTeamId})")
                    continue
            
            analysis = self.analyzer.analyze_player(
                player, injuries, schedule_info, categories, expert_data
            )
            available_scores[player.name] = analysis
        
        if waiver_skipped > 0:
            logger.info(f"⏭️ Filtered {waiver_skipped} waiver players - only showing Free Agents")
        
        # Find drop candidates (lowest scores)
        # 🔥 NEW: PROTECT players playing TODAY (especially at week start)
        all_roster_sorted = sorted(
            roster_scores.items(),
            key=lambda x: x[1]['total_score']
        )
        
        drop_candidates = []
        protected_count = 0
        
        for player_name, analysis in all_roster_sorted:
            if len(drop_candidates) >= 10:
                break
                
            # Find player object
            player_obj = next((p for p in my_roster if p.name == player_name), None)
            if not player_obj:
                continue
            
            # CRITICAL: Protect players playing TODAY
            if today_games and hasattr(player_obj, 'proTeam'):
                # Normalize team name
                team = str(player_obj.proTeam).upper()
                
                # Check if team plays today (need to normalize comparison)
                plays_today = any(team in str(t).upper() or str(t).upper() in team 
                                 for t in today_games)
                
                if plays_today:
                    if is_week_start:
                        # Week start: NEVER drop players playing today
                        logger.info(f"🛡️ Protecting {player_name} - plays TODAY at week start")
                        protected_count += 1
                        continue
                    elif analysis['total_score'] >= 20:
                        # Mid-week: Only drop if score is really bad
                        logger.info(f"🛡️ Protecting {player_name} - plays TODAY (score {analysis['total_score']:.1f})")
                        protected_count += 1
                        continue
            
            drop_candidates.append((player_name, analysis))
        
        if protected_count > 0:
            logger.info(f"🛡️ Protected {protected_count} players who play today from being dropped")
        
        # Find add candidates (highest scores)
        add_candidates = sorted(
            available_scores.items(),
            key=lambda x: x[1]['total_score'],
            reverse=True
        )[:20]  # Best 20 available
        
        # Generate recommendations
        for drop_name, drop_analysis in drop_candidates:
            for add_name, add_analysis in add_candidates:
                
                # Calculate impact
                impact = add_analysis['total_score'] - drop_analysis['total_score']
                
                # Only recommend if significant improvement
                if impact > 10:
                    
                    # Find player objects
                    drop_player = next((p for p in my_roster if p.name == drop_name), None)
                    add_player = next((p for p in available_players if p.name == add_name), None)
                    
                    if drop_player and add_player:
                        recommendations.append({
                            'priority': self._get_priority(impact),
                            'action': 'ADD_DROP',
                            'drop_player': drop_player,
                            'drop_name': drop_name,
                            'drop_analysis': drop_analysis,
                            'add_player': add_player,
                            'add_name': add_name,
                            'add_analysis': add_analysis,
                            'projected_impact': round(impact, 1),
                            'confidence': self._calculate_confidence(drop_analysis, add_analysis)
                        })
        
        # Sort by impact and return top N
        recommendations.sort(key=lambda x: x['projected_impact'], reverse=True)
        
        return recommendations[:top_n]
    
    def _get_priority(self, impact: float) -> str:
        """Determine priority level"""
        if impact > 30:
            return 'HIGH'
        elif impact > 15:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _calculate_confidence(self, drop_analysis: dict, add_analysis: dict) -> int:
        """Calculate confidence level 0-100"""
        # Higher confidence if:
        # - Drop player has health issues
        # - Add player has great schedule
        # - Add player trending up
        
        confidence = 50  # Base confidence
        
        # Drop player health issues
        if drop_analysis['health_score'] < 50:
            confidence += 20
        
        # Add player good schedule
        if add_analysis['schedule_score'] > 70:
            confidence += 15
        
        # Add player trending up
        if add_analysis['trend_score'] > 10:
            confidence += 15
        
        return min(100, confidence)


# Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🧠 Testing Intelligence Engine...")
    
    analyzer = PlayerAnalyzer()
    print("✅ PlayerAnalyzer initialized")
    
    optimizer = RosterOptimizer(analyzer)
    print("✅ RosterOptimizer initialized")
    
    print("\n✅ Intelligence engine ready!")
