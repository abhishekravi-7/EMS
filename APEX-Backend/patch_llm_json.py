from pathlib import Path
path = Path(r'c:\Users\Afzal\Documents\javaapex_coverage_mcp_agent\coverage_agent\llm.py')
content = path.read_text(encoding='utf-8')
content = content.replace('data = json.loads(text)', 'data = json.loads(text, strict=False)')
path.write_text(content, encoding='utf-8')
print("Patched llm.py successfully.")
