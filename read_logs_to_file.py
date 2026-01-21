import os

log_file = "logs/fantasy_gm_2026-01-21.log"
out_file = "filtered_logs.txt"

if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
    with open(out_file, 'w', encoding='utf-8') as f_out:
        f_out.write(f"Total lines: {len(lines)}\n")
        f_out.write("Last 500 lines relating to filtering:\n")
        for line in lines[-1000:]:
            if any(x in line for x in ["Skipping", "Protected", "UNDROPPABLE", "Filter", "Generated", "Candidates", "DEBUG CHECK"]):
                f_out.write(line)
    print("Logs written to filtered_logs.txt")
else:
    print("Log file not found")
