import os, sys, json, re, time
sys.path.insert(0, '.')
from pathlib import Path
import xml.etree.ElementTree as ET
import pymongo
from app.core.config import settings

job_id = 'job_f19f83658fe2'
job_dir = Path('storage/migration-jobs') / job_id
mig_repo = job_dir / 'migrated-repo'
test_dir = mig_repo / 'src' / 'test' / 'java'
surefire_dir = mig_repo / 'target' / 'surefire-reports'
jacoco_exec = mig_repo / 'target' / 'jacoco.exec'
jacoco_xml = mig_repo / 'target' / 'site' / 'jacoco' / 'jacoco.xml'
jacoco_html = mig_repo / 'target' / 'site' / 'jacoco' / 'index.html'

from app.infrastructure.analyzers.junit_analyzer import JavaASTAnalyzer

analyzer = JavaASTAnalyzer()
print('=== 1. TEST FILES ON DISK ===')
test_files = list(test_dir.rglob('*.java'))
print(f'Total test files on disk: {len(test_files)}')
file_details = []
for tf in test_files:
    code = tf.read_text(encoding='utf-8', errors='ignore')
    parsed = analyzer.analyze_test_file(code, filename=tf.name)
    methods = parsed.get('test_methods', [])
    is_existing = (tf.name == 'ProjectApplicationTests.java')
    ttype = 'EXISTING' if is_existing else 'GENERATED'
    file_details.append({
        'path': str(tf.relative_to(test_dir)).replace('\\', '/'),
        'class': tf.stem,
        'type': ttype,
        'methods_count': len(methods),
        'methods': methods
    })
    print(f'  [{ttype:9}] {tf.stem} -> {len(methods)} @Test methods ({tf.relative_to(test_dir)})')

gen_files = [f for f in file_details if f['type'] == 'GENERATED']
exist_files = [f for f in file_details if f['type'] == 'EXISTING']
print(f'\nExisting Test Files: {len(exist_files)}, Existing Test Cases: {sum(f["methods_count"] for f in exist_files)}')
print(f'Generated Test Files: {len(gen_files)}, Generated Test Cases: {sum(f["methods_count"] for f in gen_files)}')
print(f'Total Test Files: {len(file_details)}, Total Test Cases: {sum(f["methods_count"] for f in file_details)}')

print('\n=== 2. SUREFIRE REPORTS ON DISK ===')
surefire_xmls = list(surefire_dir.glob('TEST-*.xml')) if surefire_dir.exists() else []
print(f'Total Surefire XML files: {len(surefire_xmls)}')
sf_by_class = {}
total_exec = 0
total_passed = 0
total_failed = 0
total_errors = 0
total_skipped = 0

for sfx in surefire_xmls:
    tree = ET.parse(sfx)
    root = tree.getroot()
    cname = root.attrib.get('name', '')
    short_cname = cname.split('.')[-1]
    t_cnt = int(root.attrib.get('tests', 0))
    f_cnt = int(root.attrib.get('failures', 0))
    e_cnt = int(root.attrib.get('errors', 0))
    s_cnt = int(root.attrib.get('skipped', 0))
    time_taken = float(root.attrib.get('time', 0.0))
    p_cnt = t_cnt - f_cnt - e_cnt - s_cnt
    
    total_exec += t_cnt
    total_passed += p_cnt
    total_failed += f_cnt
    total_errors += e_cnt
    total_skipped += s_cnt
    
    sf_by_class[short_cname] = {
        'full_name': cname,
        'tests': t_cnt,
        'passed': p_cnt,
        'failures': f_cnt,
        'errors': e_cnt,
        'skipped': s_cnt,
        'time': time_taken
    }

print(f'Surefire summary: Executed={total_exec}, Passed={total_passed}, Failed={total_failed}, Errors={total_errors}, Skipped={total_skipped}')

print('\n=== 3. GENERATED TEST CLASS vs SUREFIRE TABLE ===')
print(f'{"Generated Test Class":<40} | {"@Test":<5} | {"Surefire":<8} | {"Exec":<5} | {"Pass":<5} | {"Fail":<5} | {"Skip":<5}')
print('-'*82)
for gf in file_details:
    cname = gf['class']
    m_cnt = gf['methods_count']
    if cname in sf_by_class:
        sf = sf_by_class[cname]
        print(f'{cname:<40} | {m_cnt:<5} | {"FOUND":<8} | {sf["tests"]:<5} | {sf["passed"]:<5} | {sf["failures"]:<5} | {sf["skipped"]:<5}')
    else:
        print(f'{cname:<40} | {m_cnt:<5} | {"MISSING":<8} | {"0":<5} | {"0":<5} | {"0":<5} | {"0":<5}')

print('\n=== 4. JACOCO FILES ON DISK ===')
print('jacoco.exec exists:', jacoco_exec.exists(), f'({jacoco_exec.stat().st_size} bytes, mtime={time.ctime(jacoco_exec.stat().st_mtime)})' if jacoco_exec.exists() else '')
print('jacoco.xml exists:', jacoco_xml.exists(), f'({jacoco_xml.stat().st_size} bytes, mtime={time.ctime(jacoco_xml.stat().st_mtime)})' if jacoco_xml.exists() else '')
print('index.html exists:', jacoco_html.exists(), f'({jacoco_html.stat().st_size} bytes, mtime={time.ctime(jacoco_html.stat().st_mtime)})' if jacoco_html.exists() else '')

if jacoco_xml.exists():
    from app.infrastructure.quality_gates.jacoco_service import JaCoCoService
    parsed_cov = JaCoCoService.parse_jacoco_xml(jacoco_xml)
    print('JaCoCo parsed metrics:', parsed_cov)
