"""ML Decision Engine - Predicts decision quality based on historical data"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
import numpy as np

# ML imports (optional - graceful fallback)
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("⚠️ scikit-learn not available. ML predictions will use rule-based fallback.")


class MLDecisionEngine:
    """Machine learning engine for predicting decision quality"""
    
    def __init__(self, db_path='data/fantasy_brain.db'):
        self.db_path = db_path
        self.model = None
        self.scaler = None
        self.is_trained = False
        
        if SKLEARN_AVAILABLE:
            self.model = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42)
            self.scaler = StandardScaler()
    
    def extract_features(self, decision_data: Dict) -> List[float]:
        """
        Extract features from decision data for ML
        
        Features:
            - health_score_add
            - health_score_drop
            - trend_score_add
            - trend_score_drop
            - schedule_score_add
            - schedule_score_drop
            - expert_rank_add (if available)
            - expert_rank_drop (if available)
            - ai_confidence
            - matchup_context (winning=1, losing=0)
        
        Returns: Feature vector [f1, f2, ..., f10]
        """
        features = [
            decision_data.get('health_score_add', 50.0),
            decision_data.get('health_score_drop', 50.0),
            decision_data.get('trend_score_add', 0.0) + 100,  # Normalize to 0-200
            decision_data.get('trend_score_drop', 0.0) + 100,
            decision_data.get('schedule_score_add', 50.0),
            decision_data.get('schedule_score_drop', 50.0),
            200 - decision_data.get('expert_rank_add', 200),  # Inverse rank
            200 - decision_data.get('expert_rank_drop', 200),
            decision_data.get('ai_confidence', 50.0),
            1.0 if decision_data.get('matchup_winning', False) else 0.0
        ]
        
        return features
    
    def train_from_history(self, league_id: str, min_samples: int = 10) -> Dict:
        """
        Train ML model from historical decisions
        
        Returns: {
            'trained': bool,
            'samples_used': int,
            'accuracy': float,
            'method': 'ml' or 'rule_based'
        }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get decisions with outcomes
            cursor.execute('''
                SELECT 
                    player_added, player_dropped,
                    ai_confidence,
                    fantasypros_add_rank, fantasypros_drop_rank,
                    was_good_decision
                FROM decisions_enhanced
                WHERE league_id = ?
                  AND was_good_decision IS NOT NULL
                  AND decision_date >= date('now', '-60 days')
            ''', (league_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if len(rows) < min_samples:
                logger.info(f"⚠️ Only {len(rows)} samples - need {min_samples}. Using rule-based fallback.")
                return {
                    'trained': False,
                    'samples_used': len(rows),
                    'accuracy': 0.0,
                    'method': 'rule_based'
                }
            
            if not SKLEARN_AVAILABLE:
                logger.warning("⚠️ scikit-learn not available - using rule-based approach")
                return {
                    'trained': False,
                    'samples_used': len(rows),
                    'accuracy': 0.0,
                    'method': 'rule_based'
                }
            
            # Prepare training data
            X = []
            y = []
            
            for row in rows:
                # Simplified features (would need full player data for real features)
                features = [
                    row[2] if row[2] else 50,  # ai_confidence
                    200 - (row[3] if row[3] else 200),  # expert rank add (inverted)
                    200 - (row[4] if row[4] else 200),  # expert rank drop (inverted)
                ]
                
                X.append(features)
                y.append(1 if row[5] else 0)  # was_good_decision
            
            X = np.array(X)
            y = np.array(y)
            
            # Normalize features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train model
            self.model.fit(X_scaled, y)
            self.is_trained = True
            
            # Calculate training accuracy
            predictions = self.model.predict(X_scaled)
            accuracy = np.mean(predictions == y)
            
            logger.info(f"✅ ML model trained on {len(rows)} samples, accuracy: {accuracy:.2%}")
            
            return {
                'trained': True,
                'samples_used': len(rows),
                'accuracy': accuracy,
                'method': 'ml'
            }
            
        except Exception as e:
            logger.error(f"❌ Error training model: {e}")
            return {
                'trained': False,
                'samples_used': 0,
                'accuracy': 0.0,
                'method': 'error'
            }
    
    def predict_decision_quality(
        self,
        add_analysis: Dict,
        drop_analysis: Dict,
        ai_confidence: int,
        matchup_winning: bool = False
    ) -> Dict:
        """
        Predict if a proposed decision will be good
        
        Args:
            add_analysis: Player analysis for player to add
            drop_analysis: Player analysis for player to drop
            ai_confidence: AI's confidence (0-100)
            matchup_winning: Current matchup status
        
        Returns: {
            'predicted_success': 0.78,
            'confidence': 0.82,
            'reasoning': 'High expert rank + good health',
            'method': 'ml' or 'rule_based'
        }
        """
        # Prepare features
        decision_data = {
            'health_score_add': add_analysis.get('health_score', 50),
            'health_score_drop': drop_analysis.get('health_score', 50),
            'trend_score_add': add_analysis.get('trend_score', 0),
            'trend_score_drop': drop_analysis.get('trend_score', 0),
            'schedule_score_add': add_analysis.get('schedule_score', 50),
            'schedule_score_drop': drop_analysis.get('schedule_score', 50),
            'expert_rank_add': add_analysis.get('expert_score', 50),  # Using score as proxy
            'expert_rank_drop': drop_analysis.get('expert_score', 50),
            'ai_confidence': ai_confidence,
            'matchup_winning': matchup_winning
        }
        
        # Use ML if available and trained
        if SKLEARN_AVAILABLE and self.is_trained:
            return self._ml_predict(add_analysis, drop_analysis, ai_confidence)
        else:
            return self._rule_based_predict(add_analysis, drop_analysis, ai_confidence)
    
    def _ml_predict(self, add_analysis: Dict, drop_analysis: Dict, ai_confidence: int) -> Dict:
        """ML-based prediction"""
        try:
            # Simplified features
            features = np.array([[
                ai_confidence,
                add_analysis.get('expert_score', 50),
                drop_analysis.get('expert_score', 50)
            ]])
            
            features_scaled = self.scaler.transform(features)
            
            # Predict probability
            proba = self.model.predict_proba(features_scaled)[0]
            success_prob = proba[1]  # Probability of success (class 1)
            
            # Model confidence (distance from 0.5)
            confidence = abs(success_prob - 0.5) * 2
            
            reasoning = self._generate_reasoning_ml(add_analysis, drop_analysis, success_prob)
            
            return {
                'predicted_success': round(success_prob, 2),
                'confidence': round(confidence, 2),
                'reasoning': reasoning,
                'method': 'ml'
            }
            
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return self._rule_based_predict(add_analysis, drop_analysis, ai_confidence)
    
    def _rule_based_predict(self, add_analysis: Dict, drop_analysis: Dict, ai_confidence: int) -> Dict:
        """Rule-based prediction fallback"""
        score_diff = add_analysis.get('total_score', 50) - drop_analysis.get('total_score', 50)
        
        # Convert score diff to success probability
        if score_diff > 30:
            predicted_success = 0.85
        elif score_diff > 20:
            predicted_success = 0.75
        elif score_diff > 10:
            predicted_success = 0.65
        elif score_diff > 0:
            predicted_success = 0.55
        else:
            predicted_success = 0.40
        
        # Confidence based on AI confidence and score diff magnitude
        confidence = min(0.95, (ai_confidence / 100 + abs(score_diff) / 50) / 2)
        
        reasoning = self._generate_reasoning_rules(add_analysis, drop_analysis, score_diff)
        
        return {
            'predicted_success': predicted_success,
            'confidence': confidence,
            'reasoning': reasoning,
            'method': 'rule_based'
        }
    
    def _generate_reasoning_ml(self, add_analysis: Dict, drop_analysis: Dict, prob: float) -> str:
        """Generate human-readable reasoning from ML prediction"""
        reasons = []
        
        if prob > 0.7:
            reasons.append("Strong historical pattern match")
        
        if add_analysis.get('expert_score', 50) > 70:
            reasons.append("High expert ranking")
        
        if add_analysis.get('health_score', 50) > drop_analysis.get('health_score', 50):
            reasons.append("Better health")
        
        if not reasons:
            reasons.append("Moderate confidence based on historical data")
        
        return " + ".join(reasons)
    
    def _generate_reasoning_rules(self, add_analysis: Dict, drop_analysis: Dict, score_diff: float) -> str:
        """Generate reasoning from rule-based prediction"""
        reasons = []
        
        if score_diff > 20:
            reasons.append(f"Large score advantage (+{score_diff:.0f})")
        
        health_diff = add_analysis.get('health_score', 50) - drop_analysis.get('health_score', 50)
        if health_diff > 20:
            reasons.append("Much healthier")
        
        if add_analysis.get('expert_score', 0) > 70:
            reasons.append("Expert-backed")
        
        if not reasons:
            reasons.append("Marginal improvement expected")
        
        return " + ".join(reasons)
    
    def get_learning_insights(self, league_id: str) -> Dict:
        """
        Get insights from learning history
        
        Returns: {
            'ai_accuracy': 0.75,
            'total_decisions': 20,
            'best_move_type': 'guard_add',
            'worst_move_type': 'center_drop'
        }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get decision stats
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN was_good_decision THEN 1 ELSE 0 END) as good,
                    SUM(CASE WHEN ai_recommendation = user_choice AND was_good_decision THEN 1 ELSE 0 END) as ai_good,
                    SUM(CASE WHEN ai_recommendation = user_choice THEN 1 ELSE 0 END) as ai_followed
                FROM decisions_enhanced
                WHERE league_id = ?
                  AND was_good_decision IS NOT NULL
                  AND decision_date >= date('now', '-30 days')
            ''', (league_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row or row[0] == 0:
                return {
                    'ai_accuracy': 0.0,
                    'total_decisions': 0,
                    'data_available': False
                }
            
            total, good, ai_good, ai_followed = row
            
            ai_accuracy = ai_good / ai_followed if ai_followed > 0 else 0
            overall_success = good / total if total > 0 else 0
            
            return {
                'ai_accuracy': round(ai_accuracy, 2),
                'overall_success_rate': round(overall_success, 2),
                'total_decisions': total,
                'ai_followed_count': ai_followed,
                'data_available': True
            }
            
        except Exception as e:
            logger.error(f"Error getting learning insights: {e}")
            return {
                'ai_accuracy': 0.0,
                'total_decisions': 0,
                'data_available': False
            }


# Testing
    def calculate_matchup_probability(
        self, 
        current_stats_me: Dict, 
        current_stats_opp: Dict,
        remaining_games_me: Dict[str, int], # {player_name: games_count}
        remaining_games_opp: Dict[str, int], 
        my_roster: List, 
        opp_roster: List,
        categories: List[str] = ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PTM', 'FG%', 'FT%', 'TO']
    ) -> Dict:
        """
        Predicts matchup outcome based on current stats + remaining projections
        
        Returns: {
            'win_probability': 0.75,
            'predicted_score': '5-4-0',
            'key_factors': ['Leading in 6 categories', 'More games remaining'],
            'category_probs': {'PTS': 0.8, 'REB': 0.4...}
        }
        """
        try:
            # 1. Calculate projected totals
            proj_me = current_stats_me.copy()
            proj_opp = current_stats_opp.copy()
            
            # Helper to get avg stats
            def get_avg(player, cat):
                # Try 2026 stats first, fallback to basic
                stats = player.stats.get('2026_avg', {}) or player.stats.get('avg', {})
                return stats.get(cat, 0)
            
            # Add projections for remaining games
            for player in my_roster:
                games = remaining_games_me.get(player.name, 0)
                if games > 0:
                    for cat in categories:
                        avg = get_avg(player, cat)
                        if cat in ['FG%', 'FT%']:
                            # Weighted average approximation (complex, simplified here)
                            # Assuming avg volume
                            continue 
                        proj_me[cat] = proj_me.get(cat, 0) + (avg * games)
            
            for player in opp_roster:
                games = remaining_games_opp.get(player.name, 0)
                if games > 0:
                    for cat in categories:
                        avg = get_avg(player, cat)
                        if cat in ['FG%', 'FT%']:
                            continue
                        proj_opp[cat] = proj_opp.get(cat, 0) + (avg * games)
            
            # 2. Determine category winners
            wins, losses, ties = 0, 0, 0
            cat_probs = {}
            factors = []
            
            for cat in categories:
                m_val = proj_me.get(cat, 0)
                o_val = proj_opp.get(cat, 0)
                
                # Special handling for Percentages (simplified projection)
                if cat in ['FG%', 'FT%']:
                    # Use current as base
                    m_val = current_stats_me.get(cat, 0)
                    o_val = current_stats_opp.get(cat, 0)
                
                diff = m_val - o_val
                if cat == 'TO': diff = -diff # TO: Lower is better
                
                # Simple logic: Margin of safety
                # If leading by > 5% of total, high confidence
                threshold = abs(m_val) * 0.05 if m_val != 0 else 5
                
                if diff > threshold:
                    wins += 1
                    cat_probs[cat] = 0.8  # Strong win
                elif diff > 0:
                    wins += 1
                    cat_probs[cat] = 0.6  # Narrow win
                elif diff < -threshold:
                    losses += 1
                    cat_probs[cat] = 0.2  # Strong loss
                elif diff < 0:
                    losses += 1
                    cat_probs[cat] = 0.4  # Narrow loss
                else:
                    ties += 1
                    cat_probs[cat] = 0.5
            
            # 3. Calculate Win Probability
            # If we win > 4.5 cats (in 9 cat), we win matchup
            # Probability is roughly sigmoid of (wins - 4.5)
            
            win_margin = wins - losses
            
            # Base probability
            if wins > (len(categories) / 2):
                prob = 0.60 + (win_margin * 0.05) # 0.65, 0.70...
                matchup_result = "WIN"
            elif losses > (len(categories) / 2):
                prob = 0.40 - (abs(win_margin) * 0.05)
                matchup_result = "LOSS"
            else:
                prob = 0.50
                matchup_result = "TIE"
            
            # Adjust based on 'games remaining' (volume categories)
            total_games_me = sum(remaining_games_me.values())
            total_games_opp = sum(remaining_games_opp.values())
            
            if total_games_me > total_games_opp + 2:
                prob += 0.05
                factors.append(f"More games remaining (+{total_games_me - total_games_opp})")
            elif total_games_opp > total_games_me + 2:
                prob -= 0.05
                factors.append(f"Opponent has more games (+{total_games_opp - total_games_me})")
                
            prob = max(0.05, min(0.95, prob))
            
            # Key factors text
            if prob > 0.6:
                factors.append(f"Projected to win {wins}-{losses}-{ties}")
            elif prob < 0.4:
                factors.append(f"Trailing {wins}-{losses}-{ties}")
            
            return {
                'win_probability': round(prob, 2),
                'predicted_score': f"{wins}-{losses}-{ties}",
                'key_factors': factors,
                'category_probs': cat_probs,
                'projected_totals_me': proj_me,
                'projected_totals_opp': proj_opp
            }
            
        except Exception as e:
            logger.error(f"Error calculating matchup probability: {e}")
            return {
                'win_probability': 0.5,
                'predicted_score': '0-0-0',
                'key_factors': ['Error calculating projection'],
                'category_probs': {}
            }

if __name__ == "__main__":
    # Test block
    print("Testing ML Engine...")
    
    engine = MLDecisionEngine()
    
    # Test feature extraction
    print("1. Testing feature extraction...")
    decision_data = {
        'health_score_add': 100,
        'health_score_drop': 50,
        'ai_confidence': 85
    }
    features = engine.extract_features(decision_data)
    print(f"   ✅ Extracted {len(features)} features")
    
    # Test prediction (rule-based fallback)
    print("\n2. Testing prediction...")
    add_analysis = {'total_score': 75, 'health_score': 100, 'expert_score': 85}
    drop_analysis = {'total_score': 45, 'health_score': 50, 'expert_score': 40}
    
    prediction = engine.predict_decision_quality(add_analysis, drop_analysis, 85)
    print(f"   ✅ Prediction: {prediction['predicted_success']:.0%} success")
    print(f"   Confidence: {prediction['confidence']:.0%}")
    print(f"   Method: {prediction['method']}")
    print(f"   Reasoning: {prediction['reasoning']}")
    
    print("\n✅ ML Decision Engine ready!")
    
    if not SKLEARN_AVAILABLE:
        print("\n⚠️ Note: Install scikit-learn for ML predictions:")
        print("   pip install scikit-learn")
