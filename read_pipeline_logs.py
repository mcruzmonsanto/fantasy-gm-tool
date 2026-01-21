import os
import datetime

# Log file is likely today's date
today = datetime.datetime.now().strftime('%Y-%m-%d')
log_file = f"logs/fantasy_gm_{today}.log"
out_file = "pipeline_logs.txt"

print(f"Reading {log_file}...")

if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
    with open(out_file, 'w', encoding='utf-8') as f_out:
        f_out.write(f"Total lines: {len(lines)}\n")
        f_out.write("Last 1000 lines matching pipeline keywords:\n")
        
        keywords = [
            "Pipeline Status", 
            "candidates found", 
            "drop candidates", 
            "add candidates", 
            "Generated", 
            "Filtered", 
            "Sanity", 
            "Impact", 
            "Strict", 
            "RELAXED", 
            "DESPERATION",
            "UNDROPPABLE"
        ]
        
        count = 0
        for line in lines[-1500:]:
            if any(x in line for x in keywords):
                f_out.write(line)
                count += 1
                
    print(f"Written {count} lines to {out_file}")
else:
    print(f"Log file {log_file} not found")
