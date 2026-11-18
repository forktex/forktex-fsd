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


"""A service: brought up, looked at and taken down again inside a report."""

from __future__ import annotations

import json

from conftest import record, toml, write_project

from forktex_fsd import Outcome, Project


def test_a_report_brackets_the_running_service(tmp_path):
    log = tmp_path / "log"
    write_project(
        tmp_path,
        f"""
[operation]
start = {toml(record(log, "start"))}
status = {toml(record(log, "status"))}
stop = {toml(record(log, "stop"))}
""",
        profile="service",
    )

    report = Project.load(tmp_path).report()

    assert log.read_text().split() == ["start", "status", "stop"]
    operation = [(e.atom, e.outcome) for e in report.evidence if e.track == "operation"]
    assert operation[1:] == [("start", Outcome.PASSED), ("status", Outcome.PASSED), ("stop", Outcome.PASSED)]
    assert not report.passed


def test_a_service_must_be_deployable_and_operable(tmp_path):
    write_project(tmp_path, profile="service")
    failures = {t.track: [a.atom for a in t.failures] for t in Project.load(tmp_path).check().tracks}
    assert {"start", "stop", "status"} <= set(failures["operation"])
    assert "deploy" in failures["delivery"]


def test_the_report_is_json_a_dashboard_can_read(tmp_path):
    write_project(tmp_path, profile="service")
    data = json.loads(Project.load(tmp_path).report().model_dump_json())
    assert {"project", "generatedAt", "compliance", "evidence", "passed"} <= set(data)
    assert data["compliance"]["profile"] == "service"
