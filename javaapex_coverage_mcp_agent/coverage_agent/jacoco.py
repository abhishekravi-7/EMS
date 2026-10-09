from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from .models import CoverageGap


class JaCoCoParser:
    def parse(self, report_path: str, source_root: str | None = None) -> dict:
        root = ET.parse(report_path).getroot()

        counters = {}
        for counter in root.findall("counter"):
            counters[counter.attrib["type"]] = self._counter(counter)

        classes = []
        for package in root.findall(".//package"):
            package_name = package.attrib.get("name", "").replace("/", ".")
            for cls in package.findall("class"):
                classes.append(self._parse_class(package_name, cls, source_root))

        line = counters.get("LINE", {"covered": 0, "missed": 0})
        branch = counters.get("BRANCH", {"covered": 0, "missed": 0})

        return {
            "line_coverage": self._pct(line),
            "branch_coverage": self._pct(branch),
            "counters": counters,
            "classes": classes,
        }

    def _parse_class(self, package_name, cls, source_root):
        line_total = {"covered": 0, "missed": 0}
        branch_total = {"covered": 0, "missed": 0}
        uncovered = []

        for c in cls.findall("counter"):
            data = self._counter(c)
            if c.attrib["type"] == "LINE":
                line_total = data
            elif c.attrib["type"] == "BRANCH":
                branch_total = data

        for line in cls.findall("./lines/line"):
            if int(line.attrib.get("ci", 0)) == 0:
                uncovered.append(int(line.attrib["nr"]))

        methods = []
        for method in cls.findall("./method"):
            counter = next(
                (c for c in method.findall("counter") if c.attrib["type"] == "LINE"),
                None,
            )
            if counter is not None and int(counter.attrib.get("ci", 0)) == 0:
                methods.append(method.attrib.get("name", ""))

        class_name = cls.attrib.get("name", "").replace("/", ".")
        source_file = cls.attrib.get("sourcefilename")

        return {
            "package": package_name,
            "class_name": class_name,
            "source_file": str(Path(source_root) / source_file)
                if source_root and source_file else source_file,
            "line_coverage": self._pct(line_total),
            "branch_coverage": self._pct(branch_total),
            "uncovered_lines": uncovered,
            "uncovered_branches": branch_total["missed"],
            "uncovered_methods": methods,
        }

    def gaps(self, report_path: str, source_root: str | None = None,
             min_class_coverage: float = 100.0) -> list[CoverageGap]:
        report = self.parse(report_path, source_root)
        gaps = []
        for c in report["classes"]:
            if c["line_coverage"] >= min_class_coverage and not c["uncovered_methods"]:
                continue

            priority = (
                len(c["uncovered_lines"])
                + c["uncovered_branches"] * 2
                + len(c["uncovered_methods"]) * 3
            )

            gaps.append(CoverageGap(
                package=c["package"],
                class_name=c["class_name"],
                source_file=c["source_file"],
                line_coverage=c["line_coverage"],
                branch_coverage=c["branch_coverage"],
                uncovered_lines=c["uncovered_lines"],
                uncovered_branches=c["uncovered_branches"],
                uncovered_methods=c["uncovered_methods"],
                priority=float(priority),
            ))

        return sorted(gaps, key=lambda x: x.priority, reverse=True)

    @staticmethod
    def _counter(node):
        return {
            "missed": int(node.attrib["missed"]),
            "covered": int(node.attrib["covered"]),
        }

    @staticmethod
    def _pct(counter):
        total = counter["covered"] + counter["missed"]
        return round((counter["covered"] / total) * 100, 2) if total else 100.0
