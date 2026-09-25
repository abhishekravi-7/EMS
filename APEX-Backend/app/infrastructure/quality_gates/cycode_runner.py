"""Advisory secrets and SAST scans using Cycode CLI 3.24.1 JSON output.

Only allowlisted finding metadata is retained; raw output and code snippets
are never included in migration reports or logs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

from app.core.config import settings
from app.infrastructure.quality_gates.cycode_config import cycode_authorized


class CycodeRunner:
    def run(self, project_dir: Path, *, job_id: str, quality_checks_values: dict | None = None) -> dict:
        report = {
            'job_id': job_id, 'execution_status': 'ERROR', 'gate_status': 'UNAVAILABLE',
            'mode': 'advisory', 'scans': [], 'error_message': None,
            'scanned_at': datetime.now(timezone.utc).isoformat(),
        }
        if not cycode_authorized():
            report['error_message'] = 'Cycode execution is not enabled by the Super Admin.'
            return report
        values = quality_checks_values or {}
        api_url = str(values.get('cycode_api_url') or settings.cycode_api_url).strip().rstrip('/')
        tenant = str(values.get('cycode_tenant') or '').strip()
        token = str(values.get('cycode_api_token') or '').strip()
        scopes = {part.strip().lower() for part in str(values.get('cycode_scopes') or '').replace(';', ',').split(',') if part.strip()}
        if not api_url or urlparse(api_url).scheme not in ('http', 'https') or not urlparse(api_url).netloc:
            report['error_message'] = 'Configure a valid Cycode API / tenant URL.'
            return report
        if not tenant:
            report['error_message'] = 'Configure the Cycode account or tenant identifier.'
            return report
        if not {'secrets', 'sast'}.issubset(scopes):
            report['error_message'] = 'Cycode scopes must include secrets and sast.'
            return report
        if token.startswith('****'):
            token = ''
        if not token:
            report['error_message'] = 'Configure the Cycode API Token in User Settings.'
            return report
        cli = shutil.which(settings.cycode_cli_command)
        if not cli:
            report['error_message'] = 'Cycode CLI is not installed on the migration worker.'
            return report
        project_dir = Path(project_dir).resolve()
        if not project_dir.is_dir():
            report['error_message'] = 'The migrated project directory is unavailable.'
            return report
        env = os.environ.copy()
        # Prevent inherited Cycode authentication/configuration crossing users.
        for key in list(env):
            if key.startswith('CYCODE_'):
                env.pop(key)
        env.update(
            # API-token authentication is the only credential exposed by the
            # JavaAPEX UI. Keep the CLI-compatible secret variable as well for
            # Cycode CLI releases that consume tokens through that setting.
            CYCODE_API_TOKEN=token,
            CYCODE_CLIENT_SECRET=token,
            CYCODE_API_URL=api_url,
            CYCODE_APP_URL=str(values.get('cycode_app_url') or settings.cycode_app_url).strip().rstrip('/'),
            CYCODE_TENANT_ID=tenant,
            CYCODE_SCOPES=','.join(sorted(scopes)),
        )
        # Isolate CLI caches, credentials and logs from other migration jobs.
        with TemporaryDirectory(prefix='apex-cycode-') as cli_home:
            env.update(HOME=cli_home, USERPROFILE=cli_home, XDG_CONFIG_HOME=cli_home)
            for scan_type in ('secret', 'sast'):
                command = [cli, '--no-progress-meter', '--no-update-notifier', '-o', 'json',
                           'scan', '-t', scan_type, '--stop-on-error', 'path', str(project_dir)]
                try:
                    completed = subprocess.run(  # nosec B603  # noqa: S603
                        command, cwd=project_dir, env=env, capture_output=True, text=True,
                        encoding='utf-8', errors='replace', timeout=settings.cycode_timeout_seconds,
                        check=False,
                    )
                    scan = self._parse(completed.stdout, completed.returncode, scan_type, (token,))
                except subprocess.TimeoutExpired:
                    scan = self._error(scan_type, 'Scan timed out. Retry or adjust the worker timeout.')
                except OSError:
                    scan = self._error(scan_type, 'Unable to start the Cycode CLI.')
                report['scans'].append(scan)
        if any(scan['execution_status'] != 'COMPLETED' for scan in report['scans']):
            report['error_message'] = 'One or more Cycode scans could not complete. Review scan details.'
        else:
            report['execution_status'] = 'COMPLETED'
            report['gate_status'] = 'FAILED' if any(
                scan['gate_status'] == 'FAILED' for scan in report['scans']
            ) else 'PASSED'
        return report

    @staticmethod
    def _error(scan_type: str, message: str) -> dict:
        return {'scan_type': scan_type, 'execution_status': 'ERROR', 'gate_status': 'UNAVAILABLE',
                'finding_count': None, 'findings': [], 'error_message': message}

    @classmethod
    def _parse(cls, output: str, returncode: int, scan_type: str, credentials: tuple[str, str]) -> dict:
        if returncode not in (0, 1):
            return cls._error(scan_type, 'Cycode execution failed. Check credentials, connectivity and CLI configuration.')
        try:
            data = json.loads(output)
        except (ValueError, TypeError):
            return cls._error(scan_type, 'Cycode returned an unreadable report.')
        if not isinstance(data, dict) or data.get('error') or data.get('errors'):
            return cls._error(scan_type, 'Cycode reported an execution error or incomplete scan.')
        detections = data.get('detections')
        if not isinstance(detections, list) or not isinstance(data.get('scan_ids'), list) or not data['scan_ids']:
            return cls._error(scan_type, 'Cycode did not return a completed scan report.')
        if any(not isinstance(item, dict) for item in detections) or (returncode == 1 and not detections):
            return cls._error(scan_type, 'Cycode returned inconsistent scan results.')

        def safe(value) -> str:
            text = str(value or '')[:500]
            for credential in credentials:
                if credential:
                    text = text.replace(credential, '[REDACTED]')
            return text

        findings = []
        for item in detections[:200]:
            details = item.get('detection_details')
            details = details if isinstance(details, dict) else {}
            severity = str(item.get('severity', 'UNKNOWN')).upper()
            if severity not in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'):
                severity = 'UNKNOWN'
            file_path = str(details.get('file_path') or '')
            if scan_type == 'secret' and details.get('file_name'):
                file_path = str(Path(file_path) / str(details['file_name']))
            # Never expose message/content/value fields, especially for secrets.
            findings.append({
                'severity': severity,
                'file': safe(file_path),
                'rule': safe(item.get('detection_rule_id')),
            })
        return {'scan_type': scan_type, 'execution_status': 'COMPLETED',
                'gate_status': 'FAILED' if detections else 'PASSED',
                'finding_count': len(detections), 'findings': findings,
                'error_message': None}
