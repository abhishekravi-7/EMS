agent_path = r"C:\Users\Afzal\Documents\Apex\javaapex_coverage_mcp_agent\coverage_agent\agent.py"
with open(agent_path, "r", encoding="utf-8") as f:
    code = f.read()

# Replace the RuntimeError raise with a continue (skip bad files)
old = '''                if not self._is_test_file(target, project):
                    raise RuntimeError(
                        f"Coverage agent refused non-test modification: {target}"
                    )'''

new = '''                if not self._is_test_file(target, project):
                    import logging as _log
                    _log.getLogger(__name__).warning(
                        "[CoverageAgent] Skipping non-test path: %s", target
                    )
                    continue'''

if old in code:
    code = code.replace(old, new)
    with open(agent_path, "w", encoding="utf-8") as f:
        f.write(code)
    print("SUCCESS: agent.py updated - non-test files now skipped instead of crashing")
else:
    print("ERROR: Could not find the exact block")
    for i, line in enumerate(code.splitlines(), 1):
        if "refused non-test" in line or "_is_test_file" in line:
            print(f"  Line {i}: {line.rstrip()}")

# Clear pycache
import shutil, os
for root_dir, dirs, files in os.walk(os.path.dirname(agent_path)):
    for d in dirs:
        if d == "__pycache__":
            shutil.rmtree(os.path.join(root_dir, d), ignore_errors=True)
print("Cache cleared")
