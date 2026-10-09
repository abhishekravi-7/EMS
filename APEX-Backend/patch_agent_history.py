from pathlib import Path
path = Path(r'c:\Users\Afzal\Documents\javaapex_coverage_mcp_agent\coverage_agent\agent.py')
content = path.read_text(encoding='utf-8')
content = content.replace('history.append(CoverageIteration, CoverageGap(', 'history.append(CoverageIteration(')
path.write_text(content, encoding='utf-8')
print("Patched agent.py successfully.")
