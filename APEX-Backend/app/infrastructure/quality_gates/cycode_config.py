"""Resolve the same live admin authorization for the UI and Cycode runner."""

import json
import os
from pathlib import Path

import dotenv


def quality_checks_config() -> dict | list:
    raw = dotenv.dotenv_values(Path('.env').resolve()).get('QUALITY_CHECKS_CONFIG')
    value = raw if raw is not None else os.environ.get('QUALITY_CHECKS_CONFIG', '{}')
    try:
        for _ in range(2):
            if isinstance(value, str):
                value = json.loads(value)
        if isinstance(value, dict):
            # Older deployments predate Cycode and have no entry in their
            # persisted QUALITY_CHECKS_CONFIG. Keep those deployments
            # compatible while exposing the new optional gate immediately.
            value.setdefault('CYCODE', {
                'name': 'Cycode',
                'description': 'Secrets and application security scans of migrated code.',
                'enabled': True,
                'required': False,
                'execution_enabled': True,
                'fields': [
                    {'id': 'cycode_api_url', 'name': 'Cycode API / Tenant URL', 'visible': True, 'required': True, 'defaultValue': 'https://api.cycode.com'},
                    {'id': 'cycode_tenant', 'name': 'Cycode Account / Tenant', 'visible': True, 'required': True},
                    {'id': 'cycode_api_token', 'name': 'Cycode API Token', 'visible': True, 'required': True},
                    {'id': 'cycode_scopes', 'name': 'Cycode API Scopes', 'visible': True, 'required': True, 'defaultValue': 'secrets,sast'},
                ],
            })
        elif isinstance(value, list) and not any(
            isinstance(entry, dict) and entry.get('name') == 'Cycode' for entry in value
        ):
            value.append({
                'name': 'Cycode', 'description': 'Secrets and application security scans of migrated code.',
                'enabled': True, 'required': False, 'execution_enabled': True,
                'fields': [
                    {'id': 'cycode_api_url', 'name': 'Cycode API / Tenant URL', 'visible': True, 'required': True, 'defaultValue': 'https://api.cycode.com'},
                    {'id': 'cycode_tenant', 'name': 'Cycode Account / Tenant', 'visible': True, 'required': True},
                    {'id': 'cycode_api_token', 'name': 'Cycode API Token', 'visible': True, 'required': True},
                    {'id': 'cycode_scopes', 'name': 'Cycode API Scopes', 'visible': True, 'required': True, 'defaultValue': 'secrets,sast'},
                ],
            })
        return value if isinstance(value, (dict, list)) else {}
    except (ValueError, TypeError):
        return {}


def cycode_authorized() -> bool:
    config = quality_checks_config()
    entries = config.values() if isinstance(config, dict) else config
    return any(
        isinstance(entry, dict)
        and entry.get('name') == 'Cycode'
        and entry.get('enabled') is True
        and entry.get('execution_enabled', True) is True
        for entry in entries
    )
