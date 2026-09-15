import json
import os

log_file = 'APEX-Backend/logs/llm_usage.jsonl'
if not os.path.exists(log_file):
    print(f"Log file not found at {log_file}")
else:
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get('provider') == 'huggingface' and data.get('error'):
                    print(line.strip())
            except:
                pass
