"""Resolve the same live admin authorization for the UI and Cycode runner."""

import json
import os
from pathlib import Path

import dotenv


DEFAULT_QUALITY_CHECKS = {
    'SONARQUBE': {
        'name': 'SonarQube',
        'description': 'Static code analysis to detect bugs, code smells, and security vulnerabilities.',
        'enabled': True,
        'required': False,
        'execution_enabled': True,
        'fields': [
            {'id': 'sonarqube_url', 'name': 'SonarQube URL', 'visible': True, 'required': True, 'defaultValue': 'https://sonarcloud.io'},
            {'id': 'auth_token', 'name': 'Authentication Token', 'visible': True, 'required': True},
            {'id': 'sonar_organization', 'name': 'Sonar Organisation', 'visible': True, 'required': False},
        ],
    },
    'FOSSA': {
        'name': 'FOSSA',
        'description': 'Open source dependency management and license compliance scanning.',
        'enabled': True,
        'required': False,
        'execution_enabled': True,
        'fields': [
            {'id': 'fossa_api_key', 'name': 'FOSSA API Key', 'visible': True, 'required': True},
            {'id': 'fossa_endpoint', 'name': 'FOSSA Endpoint', 'visible': True, 'required': False},
        ],
    },
    'RUN_UNIT_TEST_SUITE': {
        'name': 'Run Unit Test Suite',
        'description': "Execute the project's internal unit test suite during migration.",
        'enabled': True,
        'required': False,
        'execution_enabled': True,
        'fields': [
            {'id': 'test_command', 'name': 'Test Command / Configuration', 'visible': True, 'required': False},
        ],
    },
    'FUNCTIONAL_TESTING': {
        'name': 'Functional Testing',
        'description': 'Generate and execute functional API and UI tests for the migrated application.',
        'enabled': True,
        'required': False,
        'execution_enabled': True,
        'fields': [
            {'id': 'functional_test_command', 'name': 'Test Command / Configuration', 'visible': True, 'required': False},
        ],
    },
    'CYCODE': {
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
    },
}


def quality_checks_config(custom_raw: str | dict | list | None = None) -> dict | list:
    if custom_raw is not None and custom_raw != "":
        value = custom_raw
    else:
        raw = dotenv.dotenv_values(Path('.env').resolve()).get('QUALITY_CHECKS_CONFIG')
        value = raw if raw is not None else os.environ.get('QUALITY_CHECKS_CONFIG', {})

    try:
        for _ in range(2):
            if isinstance(value, str):
                value = json.loads(value)
        if isinstance(value, dict):
            if not value:
                value = dict(DEFAULT_QUALITY_CHECKS)
            else:
                for k, v in DEFAULT_QUALITY_CHECKS.items():
                    value.setdefault(k, v)
        elif isinstance(value, list) and not value:
            value = dict(DEFAULT_QUALITY_CHECKS)
        return value if isinstance(value, (dict, list)) else dict(DEFAULT_QUALITY_CHECKS)
    except (ValueError, TypeError):
        return dict(DEFAULT_QUALITY_CHECKS)


def cycode_authorized(custom_raw: str | dict | list | None = None) -> bool:
    config = quality_checks_config(custom_raw)
    entries = config.values() if isinstance(config, dict) else config
    return any(
        isinstance(entry, dict)
        and entry.get('name') == 'Cycode'
        and entry.get('enabled') is True
        and entry.get('execution_enabled', True) is True
        for entry in entries
    )

