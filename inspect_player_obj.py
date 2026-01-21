"""Script to inspect Player object structure for debugging"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.conectar import obtener_liga

# Redirect output to file to avoid encoding issues
sys.stdout = open("player_inspection.txt", "w", encoding="utf-8")

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

if not liga:
    print("❌ No connection")
    exit(1)

print(f"✅ Connected to {liga.settings.name}")

# Find my team
my_team = liga.teams[0]
print(f"My Team: {my_team.team_name}")
print(f"Roster size: {len(my_team.roster)}")

if not my_team.roster:
    print("❌ Roster is empty! Trying to fetch again...")
    try:
        liga.fetch_roster()
        print(f"Refreshed roster size: {len(my_team.roster)}")
    except:
        print("Could not refresh roster")

print("\nFull Roster:")
for p in my_team.roster:
    print(f"- {p.name}")

# Inspect first player found (any)
if my_team.roster:
    p = my_team.roster[0]
    print(f"\n{'='*50}")
    print(f"🕵️ INSPECTING FIRST PLAYER: {p.name}")
    print(f"{'='*50}")
    
    # Print dir() excluding private
    attrs = [a for a in dir(p) if not a.startswith('_')]
    print(f"Attributes: {attrs}")
    
    # Check ownership
    if hasattr(p, 'percent_owned'):
        print(f"percent_owned: {p.percent_owned}")
    else:
        print("❌ percent_owned attribute NOT FOUND")
        
    # Check stats structure
    print("\n📊 STATS STRUCTURE:")
    if hasattr(p, 'stats'):
        print(f"Stats keys: {list(p.stats.keys())}")
        if '2026_total' in p.stats:
            total = p.stats['2026_total']
            print(f"2026_total: {total}")
            if 'avg' in total:
                print(f"2026_total['avg']: {total['avg']}")
                print(f"PTS: {total['avg'].get('PTS')}")
    else:
        print("❌ stats attribute NOT FOUND")
                
print("\nDone.")
