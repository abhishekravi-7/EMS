agent_path = r"C:\Users\Afzal\Documents\Apex\javaapex_coverage_mcp_agent\coverage_agent\agent.py"
with open(agent_path, "r", encoding="utf-8") as f:
    code = f.read()

# Fix 1: Wrap the final report parsing in try/except
old_final = """        final_parsed = self.parser.parse(report_path)
        final_coverage = self._metric(final_parsed, request.coverage_metric)
        remaining = self.parser.gaps(
            report_path,
            source_root=(project.source_roots[0] if project.source_roots else None),
        )[:20]"""

new_final = """        if Path(report_path).exists():
            final_parsed = self.parser.parse(report_path)
            final_coverage = self._metric(final_parsed, request.coverage_metric)
            remaining = self.parser.gaps(
                report_path,
                source_root=(project.source_roots[0] if project.source_roots else None),
            )[:20]
        else:
            final_coverage = best_coverage
            remaining = []"""

if old_final in code:
    code = code.replace(old_final, new_final)
    print("Fixed final report parsing")
else:
    print("WARNING: Could not find final_parsed block")

# Fix 2: Also wrap the initial baseline report parsing  
old_initial = """        if not Path(report_path).exists():
            return CoverageAgentResult(
                success=True,
                target_coverage=request.target_coverage,
                initial_coverage=initial_coverage,
                final_coverage=initial_coverage,"""

# Check if this block exists
if old_initial in code:
    print("Initial baseline check already exists")
else:
    print("Initial baseline block not found (may have different format)")

with open(agent_path, "w", encoding="utf-8") as f:
    f.write(code)
print("agent.py saved")

# Clear pycache
import shutil, os
cache_dir = os.path.join(os.path.dirname(agent_path), "__pycache__")
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir, ignore_errors=True)
    print("Cache cleared")
