"""Injury Timeline Estimator - Estimates recovery times for NBA injuries"""
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# NBA injury recovery timelines (days)
INJURY_TIMELINES = {
    # Bone/Joint injuries
    'bone bruise': {'min': 7, 'max': 14, 'desc': '1-2 semanas'},
    'bone contusion': {'min': 7, 'max': 14, 'desc': '1-2 semanas'},
    'fracture': {'min': 21, 'max': 60, 'desc': '3-8 semanas'},
    
    # Ankle injuries
    'ankle': {'min': 7, 'max': 21, 'desc': '1-3 semanas'},
    'ankle sprain': {'min': 7, 'max': 21, 'desc': '1-3 semanas'},
    'high ankle sprain': {'min': 14, 'max': 42, 'desc': '2-6 semanas'},
    
    # Knee injuries
    'knee': {'min': 14, 'max': 42, 'desc': '2-6 semanas'},
    'knee soreness': {'min': 3, 'max': 10, 'desc': '3-10 días'},
    'mcl': {'min': 21, 'max': 42, 'desc': '3-6 semanas'},
    'acl': {'min': 180, 'max': 365, 'desc': 'Temporada (6-12 meses)'},
    'meniscus': {'min': 28, 'max': 84, 'desc': '4-12 semanas'},
    'patellar tendinitis': {'min': 14, 'max': 42, 'desc': '2-6 semanas'},
    
    # Muscle injuries
    'hamstring': {'min': 14, 'max': 28, 'desc': '2-4 semanas'},
    'quad': {'min': 14, 'max': 28, 'desc': '2-4 semanas'},
    'calf': {'min': 10, 'max': 21, 'desc': '10 días - 3 semanas'},
    'groin': {'min': 14, 'max': 28, 'desc': '2-4 semanas'},
    'strain': {'min': 7, 'max': 21, 'desc': '1-3 semanas'},
    
    # Back/Shoulder
    'back': {'min': 7, 'max': 28, 'desc': '1-4 semanas'},
    'shoulder': {'min': 14, 'max': 42, 'desc': '2-6 semanas'},
    
    # Hand/Wrist/Finger
    'hand': {'min': 7, 'max': 21, 'desc': '1-3 semanas'},
    'wrist': {'min': 14, 'max': 42, 'desc': '2-6 semanas'},
    'finger': {'min': 7, 'max': 21, 'desc': '1-3 semanas'},
    'thumb': {'min': 21, 'max': 42, 'desc': '3-6 semanas'},
    
    # Foot/Toe
    'foot': {'min': 14, 'max': 42, 'desc': '2-6 semanas'},
    'plantar fasciitis': {'min': 14, 'max': 90, 'desc': '2 semanas - 3 meses'},
    'toe': {'min': 7, 'max': 21, 'desc': '1-3 semanas'},
    
    # Other
    'concussion': {'min': 7, 'max': 21, 'desc': '1-3 semanas'},
    'illness': {'min': 3, 'max': 7, 'desc': '3-7 días'},
    'covid': {'min': 7, 'max': 14, 'desc': '1-2 semanas'},
    'rest': {'min': 1, 'max': 7, 'desc': '1-7 días'},
    'suspension': {'min': 1, 'max': 7, 'desc': '1-7 días'},  # Usually known
}

# Status severity weights
STATUS_SEVERITY = {
    'OUT': 1.0,          # Definitivamente fuera
    'DOUBTFUL': 0.8,     # Probablemente fuera
    'QUESTIONABLE': 0.5,  # 50/50
    'DAY_TO_DAY': 0.3,   # Probablemente juega pronto
    'PROBABLE': 0.1      # Casi seguro que juega
}


class InjuryTimelineEstimator:
    """Estimates recovery timelines for injured NBA players"""
    
    def __init__(self):
        self.timelines = INJURY_TIMELINES
    
    def estimate_return(self, injury_status: str, injury_details: str = "") -> Dict:
        """
        Estimate when an injured player will return
        
        Args:
            injury_status: Player's injury status (OUT, DOUBTFUL, etc.)
            injury_details: Description of injury (e.g., "ankle sprain", "bone bruise")
        
        Returns:
            {
                'min_days': int,
                'max_days': int,
                'description': str,  # "1-2 semanas"
                'confidence': str,   # 'high', 'medium', 'low'
                'severity': float    # 0-1
            }
        """
        # Default fallback
        result = {
            'min_days': 7,
            'max_days': 14,
            'description': '1-2 semanas',
            'confidence': 'low',
            'severity': 0.5
        }
        
        if not injury_status:
            return result
        
        # Get severity from status
        severity = STATUS_SEVERITY.get(injury_status, 0.5)
        result['severity'] = severity
        
        # Try to match injury type from details
        if injury_details:
            injury_lower = injury_details.lower()
            
            # Try exact match first
            for injury_key, timeline in self.timelines.items():
                if injury_key in injury_lower:
                    result.update({
                        'min_days': timeline['min'],
                        'max_days': timeline['max'],
                        'description': timeline['desc'],
                        'confidence': 'high'
                    })
                    logger.info(f"Matched injury '{injury_details}' to '{injury_key}': {timeline['desc']}")
                    break
        
        # Adjust based on status severity
        if injury_status == 'DAY_TO_DAY' and result['max_days'] > 14:
            # Day-to-day usually means short-term
            result['max_days'] = 14
            result['description'] = f"{result['min_days']}-14 días"
            result['confidence'] = 'medium'
        
        elif injury_status == 'OUT' and result['confidence'] == 'low':
            # If OUT but no injury details, assume minimum 1 week
            result['min_days'] = 7
            result['description'] = '1+ semanas'
        
        return result
    
    def is_long_term(self, injury_status: str, injury_details: str = "") -> bool:
        """
        Determine if injury is long-term (>4 weeks)
        
        Returns:
            True if injury expected to last more than 4 weeks
        """
        estimate = self.estimate_return(injury_status, injury_details)
        return estimate['min_days'] > 28
    
    def get_timeline_message(self, injury_status: str, injury_details: str = "", player_name: str = "") -> str:
        """
        Generate human-readable timeline message
        
        Returns:
            Spanish message like "Jokic volverá en 1-2 semanas (bone bruise)"
        """
        estimate = self.estimate_return(injury_status, injury_details)
        
        confidence_emoji = {
            'high': '✅',
            'medium': '⚠️',
            'low': '❓'
        }
        
        emoji = confidence_emoji.get(estimate['confidence'], '❓')
        
        if player_name:
            message = f"{emoji} {player_name} volverá en {estimate['description']}"
        else:
            message = f"{emoji} Regreso estimado: {estimate['description']}"
        
        if injury_details:
            message += f" ({injury_details})"
        
        return message


# Quick test
if __name__ == "__main__":
    estimator = InjuryTimelineEstimator()
    
    # Test cases
    tests = [
        ("Jokic", "OUT", "bone bruise"),
        ("Curry", "OUT", "ankle sprain"),
        ("LeBron", "DAY_TO_DAY", "rest"),
        ("Durant", "OUT", "calf strain"),
    ]
    
    print("🏥 Injury Timeline Estimator Tests:\n")
    for player, status, injury in tests:
        result = estimator.estimate_return(status, injury)
        message = estimator.get_timeline_message(status, injury, player)
        print(f"{message}")
        print(f"   → {result['min_days']}-{result['max_days']} días (confidence: {result['confidence']})\n")
