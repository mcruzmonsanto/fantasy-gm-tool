import os

log_file = "logs/fantasy_gm_2026-01-21.log"

if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        print(f"Total lines: {len(lines)}")
        print("Last 200 lines relating to filtering:")
        for line in lines[-500:]:
            if any(x in line for x in ["Skipping", "Protected", "UNDROPPABLE", "Filter", "Generated", "Candidates"]):
                print(line.strip())
else:
    print("Log file not found")
