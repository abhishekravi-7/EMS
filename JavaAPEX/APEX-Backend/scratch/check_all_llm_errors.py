import json
import os

log_file = 'APEX-Backend/logs/llm_usage.jsonl'
if not os.path.exists(log_file):
    print(f"Log file not found at {log_file}")
else:
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"Total lines: {len(lines)}")
        error_count = 0
        for line in lines:
            try:
                data = json.loads(line)
                if data.get('error'):
                    print(line.strip())
                    error_count += 1
            except:
                pass
        print(f"Total errors: {error_count}")
