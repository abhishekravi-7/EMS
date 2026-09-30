"""Cycode contract, isolation and failure-path tests; no remote scans."""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from app.infrastructure.quality_gates.cycode_runner import CycodeRunner
from app.infrastructure.quality_gates.quality_gate_runner import QualityGateRunner

MODULE = 'app.infrastructure.quality_gates.cycode_runner'
CREDENTIALS = {
    'cycode_api_url': 'https://api.cycode.com', 'cycode_tenant': 'test-tenant',
    'cycode_scopes': 'secrets,sast', 'cycode_api_token': 'private-token',
}


def payload(detections=None, **extra):
    return json.dumps({'scan_ids': ['scan-1'], 'detections': detections or [], 'errors': [], **extra})


@pytest.mark.parametrize('code, output', [
    (2, '{}'), (1, payload()), (0, '{}'), (0, 'invalid'),
    (0, payload(errors=[{'message': 'private-token'}])),
    (0, payload(scan_ids=[])), (0, payload(detections=['invalid'])),
])
def test_incomplete_results_never_pass(code, output):
    result = CycodeRunner._parse(output, code, 'secret', ('test-client', 'private-token'))
    assert result['gate_status'] == 'UNAVAILABLE'
    assert 'private-token' not in json.dumps(result)


def test_finding_metadata_does_not_expose_secret_content():
    detection = {'severity': 'HIGH', 'detection_rule_id': 'rule-1', 'message': 'secret contents',
                 'detection_details': {'file_path': 'private-token/config', 'value': 'secret contents'}}
    result = CycodeRunner._parse(payload([detection]), 1, 'secret', ('test-client', 'private-token'))
    assert result['gate_status'] == 'FAILED'
    assert result['finding_count'] == 1
    assert result['findings'][0]['file'] == '[REDACTED]/config'
    assert 'secret contents' not in json.dumps(result)


def test_admin_disabled_prevents_execution(tmp_path):
    with patch(f'{MODULE}.cycode_authorized', return_value=False), patch(f'{MODULE}.subprocess.run') as run:
        report = CycodeRunner().run(tmp_path, job_id='job-1', quality_checks_values=CREDENTIALS)
    run.assert_not_called()
    assert report['gate_status'] == 'UNAVAILABLE'


def test_missing_credentials_prevents_execution(tmp_path):
    with patch(f'{MODULE}.cycode_authorized', return_value=True), patch(f'{MODULE}.subprocess.run') as run:
        report = CycodeRunner().run(tmp_path, job_id='job-1')
    run.assert_not_called()
    assert report['gate_status'] == 'UNAVAILABLE'


def test_timeout_does_not_skip_second_scan_or_leak_output(tmp_path):
    with patch(f'{MODULE}.cycode_authorized', return_value=True), \
         patch(f'{MODULE}.shutil.which', return_value='cycode'), \
         patch(f'{MODULE}.subprocess.run', side_effect=[
             subprocess.TimeoutExpired('cycode', 10, output='private-token'),
             subprocess.CompletedProcess([], 0, payload(), ''),
         ]) as run:
        report = CycodeRunner().run(tmp_path, job_id='job-1', quality_checks_values=CREDENTIALS)
    assert run.call_count == 2
    assert report['gate_status'] == 'UNAVAILABLE'
    assert report['scans'][1]['gate_status'] == 'PASSED'
    assert 'private-token' not in json.dumps(report)
    kwargs = run.call_args.kwargs
    assert kwargs['env']['CYCODE_API_TOKEN'] == 'private-token'
    assert 'private-token' not in run.call_args.args[0]


def test_clean_scans_pass(tmp_path):
    with patch(f'{MODULE}.cycode_authorized', return_value=True), \
         patch(f'{MODULE}.shutil.which', return_value='cycode'), \
         patch(f'{MODULE}.subprocess.run', return_value=subprocess.CompletedProcess([], 0, payload(), '')):
        report = CycodeRunner().run(tmp_path, job_id='job-1', quality_checks_values=CREDENTIALS)
    assert report['execution_status'] == 'COMPLETED'
    assert report['gate_status'] == 'PASSED'


def test_quality_runner_keeps_cycode_opt_in(tmp_path):
    cycode = Mock()
    runner = QualityGateRunner(sonar_runner=Mock(), fossa_runner=Mock(), cycode_runner=cycode)
    assert runner.run(tmp_path, job_id='job-1').cycode is None
    cycode.run.assert_not_called()
    cycode.run.return_value = {'gate_status': 'FAILED'}
    result = runner.run(tmp_path, job_id='job-1', run_cycode=True, quality_checks_values=CREDENTIALS)
    assert result.cycode['gate_status'] == 'FAILED'
    assert result.log_lines == ['[CYCODE] FAILED (advisory)']
    cycode.run.assert_called_once_with(tmp_path, job_id='job-1', quality_checks_values=CREDENTIALS)


@pytest.mark.parametrize('entry, expected', [
    ({'name': 'Cycode', 'enabled': True}, True),
    ({'name': 'Cycode', 'enabled': False}, False),
    ({'name': 'Cycode', 'enabled': True, 'execution_enabled': False}, False),
    ({'name': 'Cycode', 'enabled': 'false'}, False),
])
def test_live_admin_authorization(entry, expected):
    from app.infrastructure.quality_gates.cycode_config import cycode_authorized
    with patch('app.infrastructure.quality_gates.cycode_config.dotenv.dotenv_values',
               return_value={'QUALITY_CHECKS_CONFIG': json.dumps({'CYCODE': entry})}):
        assert cycode_authorized() is expected
