import shutil
import os

SOURCE_DIR = r"C:\Users\Afzal\Documents\Apex\javaapex_coverage_mcp_agent\coverage_agent"
TARGET_DIR = r"C:\Users\Afzal\Documents\javaapex_coverage_mcp_agent\coverage_agent"

# Copy all 3 fixed files to the requested MCP directory
for fname in ["build.py", "agent.py", "llm.py"]:
    src = os.path.join(SOURCE_DIR, fname)
    dst = os.path.join(TARGET_DIR, fname)
    try:
        shutil.copy2(src, dst)
        print(f"Copied {fname} -> {dst}")
    except Exception as e:
        print(f"Failed to copy {fname}: {e}")

# Clear pycache at target directory
for root_dir, dirs, files in os.walk(TARGET_DIR):
    for d in dirs:
        if d == "__pycache__":
            full = os.path.join(root_dir, d)
            shutil.rmtree(full, ignore_errors=True)
            print(f"Cleared cache: {full}")

print("Fixes successfully synchronized to C:\\Users\\Afzal\\Documents\\javaapex_coverage_mcp_agent")
