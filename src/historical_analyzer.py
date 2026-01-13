"""Historical Analyzer - Learns from past decisions and matchup results"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
import numpy as np


class HistoricalAnalyzer:
    """Analyzes past decisions and matchup performance to improve future recommendations"""
    
    def __init__(self, db_path='data/fantasy_brain.db'):
        self.db_path = db_path
    
    def save_matchup_result(self, liga, my_team, matchup, strategy_used: str):
        """
        Save completed matchup results for historical analysis
        
        Args:
            liga: ESPN League object
            my_team: Team object
            matchup: H2HCategoryBoxScore object
            strategy_used: 'AGGRESSIVE', 'CONSERVATIVE', 'PUNT'
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Determine if we won
            is_home = matchup.home_team.team_id == my_team.team_id
            if is_home:
                my_wins = matchup.home_wins
                opp_wins = matchup.away_wins
                ties = matchup.home_ties
            else:
                my_wins = matchup.away_wins
                opp_wins = matchup.home_wins
                ties = matchup.away_ties
            
            won = my_wins > opp_wins
            
            # Get opponent name
            opponent = matchup.away_team if is_home else matchup.home_team
            
            # Extract stats (simplified - would need full matchup data)
            cursor.execute('''
                INSERT OR REPLACE INTO matchup_history (
                    league_id, league_name, week_number, season_year,
                    my_team_name, opponent_team_name,
                    final_score_me, final_score_opp, tied_cats,
                    won, strategy_used, date_completed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(liga.league_id),
                liga.settings.name,
                matchup.scoring_period,
                liga.year,
                my_team.team_name,
                opponent.team_name,
                my_wins,
                opp_wins,
                ties,
                won,
                strategy_used,
                datetime.now().date()
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Saved matchup result: Week {matchup.scoring_period}, {'WON' if won else 'LOST'} {my_wins}-{opp_wins}")
            
        except Exception as e:
            logger.error(f"❌ Error saving matchup result: {e}")
    
    def save_decision(
        self,
        league_id: str,
        action_type: str,
        player_dropped: Optional[str],
        player_added: Optional[str],
        ai_recommendation: str,
        user_choice: str,
        ai_confidence: int,
        reasoning: str = ""
    ):
        """
        Save user decision for future learning
        
        Args:
            action_type: 'ADD_DROP', 'START_SIT', 'WAIVER'
            ai_recommendation: What AI suggested
            user_choice: What user actually did
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get current matchup_id if available
            cursor.execute('''
                SELECT id FROM matchup_history 
                WHERE league_id = ? AND season_year = ?
                ORDER BY week_number DESC LIMIT 1
            ''', (league_id, datetime.now().year))
            
            matchup_row = cursor.fetchone()
            matchup_id = matchup_row[0] if matchup_row else None
            
            cursor.execute('''
                INSERT INTO decisions_enhanced (
                    decision_date, league_id, matchup_id,
                    action_type, player_dropped, player_added,
                    ai_recommendation, user_choice, ai_confidence, ai_reasoning
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().date(),
                league_id,
                matchup_id,
                action_type,
                player_dropped,
                player_added,
                ai_recommendation,
                user_choice,
                ai_confidence,
                reasoning
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Saved decision: {action_type} - {player_dropped} → {player_added}")
            
        except Exception as e:
            logger.error(f"❌ Error saving decision: {e}")
    
    def analyze_past_decisions(self, league_id: str, lookback_weeks: int = 4) -> Dict:
        """
        Analyze decision history and calculate AI accuracy
        
        Returns:
            {
                'ai_accuracy': 0.75,
                'user_override_success': 0.60,
                'total_decisions': 20,
                'ai_followed': 15,
                'user_overrode': 5
            }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(weeks=lookback_weeks)).date()
            
            cursor.execute('''
                SELECT 
                    ai_recommendation, user_choice, was_good_decision,
                    COUNT(*) as count
                FROM decisions_enhanced
                WHERE league_id = ? AND decision_date >= ?
                  AND was_good_decision IS NOT NULL
                GROUP BY ai_recommendation, user_choice, was_good_decision
            ''', (league_id, cutoff_date))
            
            rows = cursor.fetchall()
            conn.close()
            
            ai_followed_good = 0
            ai_followed_total = 0
            user_override_good = 0
            user_override_total = 0
            
            for ai_rec, user_choice, was_good, count in rows:
                if ai_rec == user_choice:
                    # User followed AI
                    ai_followed_total += count
                    if was_good:
                        ai_followed_good += count
                else:
                    # User overrode AI
                    user_override_total += count
                    if was_good:
                        user_override_good += count
            
            total = ai_followed_total + user_override_total
            
            return {
                'ai_accuracy': ai_followed_good / ai_followed_total if ai_followed_total > 0 else 0,
                'user_override_success': user_override_good / user_override_total if user_override_total > 0 else 0,
                'total_decisions': total,
                'ai_followed': ai_followed_total,
                'user_overrode': user_override_total
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing decisions: {e}")
            return {
                'ai_accuracy': 0,
                'user_override_success': 0,
                'total_decisions': 0,
                'ai_followed': 0,
                'user_overrode': 0
            }
    
    def get_similar_matchups(self, league_id: str, opponent_name: str, limit: int = 3) -> List[Dict]:
        """
        Find historical matchups against same opponent
        
        Returns: List of similar past matchups with outcomes
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    week_number, season_year, final_score_me, final_score_opp,
                    won, strategy_used, date_completed
                FROM matchup_history
                WHERE league_id = ? AND opponent_team_name = ?
                ORDER BY date_completed DESC
                LIMIT ?
            ''', (league_id, opponent_name, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            similar = []
            for row in rows:
                similar.append({
                    'week': row[0],
                    'season': row[1],
                    'score': f"{row[2]}-{row[3]}",
                    'won': row[4],
                    'strategy': row[5],
                    'date': row[6]
                })
            
            return similar
            
        except Exception as e:
            logger.error(f"❌ Error finding similar matchups: {e}")
            return []
    
    def get_performance_summary(self, league_id: str, weeks: int = 4) -> Dict:
        """
        Get overall performance summary for last N weeks
        
        Returns:
            {
                'wins': 3,
                'losses': 1,
                'win_rate': 0.75,
                'avg_score_diff': +2.5,
                'best_week': {'week': 14, 'score': '7-2'},
                'worst_week': {'week': 12, 'score': '3-6'}
            }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(weeks=weeks)).date()
            
            cursor.execute('''
                SELECT 
                    week_number, final_score_me, final_score_opp, won
                FROM matchup_history
                WHERE league_id = ? AND date_completed >= ?
                ORDER BY week_number DESC
            ''', (league_id, cutoff_date))
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return {
                    'wins': 0,
                    'losses': 0,
                    'win_rate': 0,
                    'weeks_tracked': 0
                }
            
            wins = sum(1 for r in rows if r[3])
            losses = len(rows) - wins
            score_diffs = [r[1] - r[2] for r in rows]
            
            best_week = max(rows, key=lambda r: r[1] - r[2])
            worst_week = min(rows, key=lambda r: r[1] - r[2])
            
            return {
                'wins': wins,
                'losses': losses,
                'win_rate': wins / len(rows),
                'avg_score_diff': np.mean(score_diffs),
                'best_week': {
                    'week': best_week[0],
                    'score': f"{best_week[1]}-{best_week[2]}"
                },
                'worst_week': {
                    'week': worst_week[0],
                    'score': f"{worst_week[1]}-{worst_week[2]}"
                },
                'weeks_tracked': len(rows)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting performance summary: {e}")
            return {
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'weeks_tracked': 0
            }


# Testing
if __name__ == "__main__":
    from loguru import logger
    import sys
    
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    print("🧠 Testing Historical Analyzer...")
    
    analyzer = HistoricalAnalyzer()
    print("✅ HistoricalAnalyzer initialized")
    
    # Test getting performance
    perf = analyzer.get_performance_summary("test_league", weeks=4)
    print(f"✅ Performance summary: {perf}")
    
    print("\n✅ Historical Analyzer ready!")
