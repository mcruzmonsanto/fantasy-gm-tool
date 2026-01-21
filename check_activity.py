"""Script to check recent activity for waiver detection"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.conectar import obtener_liga

sys.stdout = open("activity_check.txt", "w", encoding="utf-8")

# Load config
try:
    from src.config_manager import ConfigManager
    config_mgr = ConfigManager()
    LIGAS = config_mgr.get_ligas()
except:
    from config.credenciales import LIGAS

# Connect
liga_nombre = list(LIGAS.keys())[0]
liga = obtener_liga(liga_nombre, LIGAS)

if not liga: exit(1)

print(f"✅ Connected to {liga.settings.name}")

# Check recent activity
try:
    activity = liga.recent_activity(size=50)
    print(f"Retrieved {len(activity)} actions")
    
    print("\n--- RECENT PROCESSED ACTIVITY ---")
    for act in activity:
        # Each action has 'actions': list of (team, action, player_name, bid)
        # We look for DROPPED
        if hasattr(act, 'actions'):
            for team, action_type, player_name, bid in act.actions:
                if 'Simons' in str(player_name):
                    print(f"!!! FOUND SIMONS: {action_type} by {team} at {act.date}")
                
        print(f"Activity: {act.actions}")
        
except Exception as e:
    print(f"Error checking activity: {e}")

print("\nDone.")
