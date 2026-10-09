import shutil

CORRECT_DIR = r"C:\Users\Afzal\Documents\Apex\javaapex_coverage_mcp_agent\coverage_agent"
WRONG_DIR = r"C:\Users\Afzal\Documents\javaapex_coverage_mcp_agent\coverage_agent"

# Copy all 3 fixed files from the wrong directory to the correct one
for fname in ["build.py", "agent.py", "llm.py"]:
    src = f"{WRONG_DIR}\\{fname}"
    dst = f"{CORRECT_DIR}\\{fname}"
    try:
        shutil.copy2(src, dst)
        print(f"Copied {fname} -> {dst}")
    except Exception as e:
        print(f"Failed to copy {fname}: {e}")
        # Write directly instead
        with open(src, "r", encoding="utf-8") as f:
            content = f.read()
        with open(dst, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Written directly instead")

# Clear pycache at correct location
import os
for root_dir, dirs, files in os.walk(CORRECT_DIR):
    for d in dirs:
        if d == "__pycache__":
            full = os.path.join(root_dir, d)
            shutil.rmtree(full, ignore_errors=True)
            print(f"Cleared cache: {full}")

print("\nDone! All fixes applied to correct directory.")
