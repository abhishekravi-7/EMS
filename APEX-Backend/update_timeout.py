import re

file_path = r'c:\Users\Afzal\Documents\Apex\JavaAPEX\APEX-Backend\app\core\config.py'
with open(file_path, 'r') as f:
    content = f.read()

content = re.sub(r'llm_timeout_seconds: int = Field\(300,', r'llm_timeout_seconds: int = Field(900,', content)
content = re.sub(r'llm_timeout_seconds: int = 300', r'llm_timeout_seconds: int = 900', content)

with open(file_path, 'w') as f:
    f.write(content)

print("Updated config.py timeouts to 900s")
