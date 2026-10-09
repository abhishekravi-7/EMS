p = r"C:\Users\Afzal\Documents\Jacoco\EMS-Migrated20261008131222\src\test\java\com\employee\system\service\PerformanceGoalServiceTest.java"
with open(p, "r", encoding="utf-8") as f:
    content = f.read()

print("Before:", "setPriority(1)" in content)
content = content.replace("setPriority(1)", 'setPriority("1")')
content = content.replace("setPriority(2)", 'setPriority("2")')
content = content.replace("setPriority(3)", 'setPriority("3")')
print("After:", "setPriority(1)" in content)

with open(p, "w", encoding="utf-8") as f:
    f.write(content)
print("File written successfully")
