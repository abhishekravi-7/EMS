"""Coordinates optional Quality Gate scans."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.infrastructure.quality_gates.cycode_runner import CycodeRunner
from app.infrastructure.quality_gates.dependency_check_runner import (
    DependencyCheckRunner,
    FossaScanResult,
)
from app.infrastructure.quality_gates.static_analysis_runner import (
    SonarScanResult,
    StaticAnalysisRunner,
)


import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QualityGateResult:
    sonar: SonarScanResult | None = None
    fossa: FossaScanResult | None = None
    cycode: dict | None = None
    runner_logs: list[str] = field(default_factory=list)

    @property
    def log_lines(self) -> list[str]:
        lines: list[str] = list(self.runner_logs)
        if self.sonar:
            lines.extend(self.sonar.log_lines)
        if self.fossa:
            lines.extend(self.fossa.log_lines)
        if self.cycode:
            lines.append(f"[CYCODE] {self.cycode['gate_status']} (advisory)")
        return lines


class QualityGateRunner:
    def __init__(
        self,
        sonar_runner: StaticAnalysisRunner | None = None,
        fossa_runner: DependencyCheckRunner | None = None,
        cycode_runner: CycodeRunner | None = None,
    ) -> None:
        self._sonar_runner = sonar_runner or StaticAnalysisRunner()
        self._fossa_runner = fossa_runner or DependencyCheckRunner()
        self._cycode_runner = cycode_runner or CycodeRunner()

    def run(
        self,
        project_dir: Path,
        *,
        job_id: str,
        project_name: str | None = None,
        run_sonar: bool = False,
        run_fossa: bool = False,
        run_cycode: bool = False,
        quality_checks_values: dict | None = None,
    ) -> QualityGateResult:
        logger.info("[QUALITY GATE] SonarQube selected: %s", str(run_sonar).lower())
        logger.info("[QUALITY GATE] FOSSA selected: %s", str(run_fossa).lower())

        runner_logs: list[str] = [
            f"[QUALITY GATE] SonarQube selected: {str(run_sonar).lower()}",
            f"[QUALITY GATE] FOSSA selected: {str(run_fossa).lower()}",
        ]

        if run_sonar:
            logger.info("[SONARQUBE] Starting scan...")
            runner_logs.append("[SONARQUBE] Starting scan...")
            sonar = self._sonar_runner.run(
                project_dir,
                job_id=job_id,
                project_name=project_name,
                quality_checks_values=quality_checks_values,
            )
        else:
            logger.info("[SONARQUBE] Skipping scan: not selected for this migration")
            runner_logs.append("[SONARQUBE] Skipping scan: not selected for this migration")
            sonar = None

        if run_fossa:
            logger.info("[FOSSA] Starting scan...")
            runner_logs.append("[FOSSA] Starting scan...")
            fossa = self._fossa_runner.run(
                project_dir,
                job_id=job_id,
                project_name=project_name,
                quality_checks_values=quality_checks_values,
            )
        else:
            logger.info("[FOSSA] Skipping scan: not selected for this migration")
            runner_logs.append("[FOSSA] Skipping scan: not selected for this migration")
            fossa = None

        cycode = self._cycode_runner.run(
            project_dir, job_id=job_id, quality_checks_values=quality_checks_values,
        ) if run_cycode else None

        return QualityGateResult(sonar=sonar, fossa=fossa, cycode=cycode, runner_logs=runner_logs)
