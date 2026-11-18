# Copyright (C) 2026 FORKTEX S.R.L.
#
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ForkTex-Commercial
#
# This file is part of ForkTex FSD.
#
# For commercial licensing -- including use in proprietary products, SaaS
# deployments, or any context where AGPL obligations cannot be met -- you
# MUST obtain a commercial license from FORKTEX S.R.L. (info@forktex.com).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Measurements read from the result files a command writes, by format, not by tool.

Three formats cover most ecosystems: JUnit XML for tests, Cobertura XML for
coverage, SARIF for static-analysis findings. Any other file is linked as an
artifact. The files are the repository's own output, read from its own tree.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ElementTree
from enum import StrEnum
from pathlib import Path

from forktex.types import BaseWireValueObject
from pydantic import Field, ValidationError

from forktex_fsd.paths import within


class Format(StrEnum):
    """How a result file was read."""

    JUNIT = "junit"
    COBERTURA = "cobertura"
    SARIF = "sarif"
    ARTIFACT = "artifact"
    MISSING = "missing"


class ResultFile(BaseWireValueObject):
    """One result file a command wrote, read by its format."""

    path: str
    format: Format
    values: dict[str, int | float] = Field(default_factory=dict)
    summary: str = ""


def _measure(text: str | None) -> float:
    value = float(text or "0")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{text!r} is not a measurement")
    return value


def _count(text: str | None) -> int:
    value = _measure(text)
    if not value.is_integer():
        raise ValueError(f"{text!r} is not a count")
    return int(value)


def _junit(root: ElementTree.Element) -> tuple[dict[str, int | float], str]:
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    totals = {key: sum(_count(s.get(key)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    failed = totals["failures"] + totals["errors"]
    return dict(totals), f"{totals['tests']} tests, {failed} failed, {totals['skipped']} skipped"


def _cobertura(root: ElementTree.Element) -> tuple[dict[str, int | float], str]:
    lines = _measure(root.get("line-rate")) * 100
    branches = _measure(root.get("branch-rate")) * 100
    return {"linePercent": lines, "branchPercent": branches}, f"{lines:.2f}% lines"


class _SarifRun(BaseWireValueObject):
    results: list[object] = Field(default_factory=list)


class _Sarif(BaseWireValueObject):
    runs: list[_SarifRun] = Field(default_factory=list)


def _sarif(text: str) -> tuple[dict[str, int | float], str]:
    findings = sum(len(run.results) for run in _Sarif.model_validate_json(text).runs)
    return {"findings": findings}, f"{findings} findings"


def _read_xml(path: Path, relative: str) -> ResultFile:
    root = ElementTree.parse(path).getroot()
    if root.tag in ("testsuites", "testsuite"):
        values, summary = _junit(root)
        return ResultFile(path=relative, format=Format.JUNIT, values=values, summary=summary)
    if root.tag == "coverage":
        values, summary = _cobertura(root)
        return ResultFile(path=relative, format=Format.COBERTURA, values=values, summary=summary)
    return ResultFile(path=relative, format=Format.ARTIFACT)


def read_result(root: Path, relative: str) -> ResultFile:
    path = within(root, relative)
    if not path.is_file():
        return ResultFile(path=relative, format=Format.MISSING, summary="not written")
    name = path.name.lower()
    try:
        if name.endswith(".xml"):
            return _read_xml(path, relative)
        if name.endswith((".sarif", ".sarif.json")):
            values, summary = _sarif(path.read_text(encoding="utf-8"))
            return ResultFile(path=relative, format=Format.SARIF, values=values, summary=summary)
    except ElementTree.ParseError, ValidationError, ValueError, OSError:
        return ResultFile(path=relative, format=Format.ARTIFACT, summary="unreadable as its format")
    return ResultFile(path=relative, format=Format.ARTIFACT)


__all__ = ["Format", "ResultFile", "read_result"]
