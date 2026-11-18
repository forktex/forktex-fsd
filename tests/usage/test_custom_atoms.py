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


"""A repository's own atoms: run by name, given arguments, and part of the gate under assurance."""

from __future__ import annotations

import pytest
from conftest import PASS, echo_args, record, toml, write_project

from forktex_fsd import BindingError, Outcome, Project, UnknownAtomError, UsageError


def test_a_custom_atom_runs_by_name_with_arguments(tmp_path):
    out = tmp_path / "out"
    write_project(tmp_path, f"[operation]\nmigrate = {toml(echo_args(out) + ' {args} --to')}\n")
    [result] = Project.load(tmp_path).run("migrate", "head", "two words")
    assert result.outcome is Outcome.PASSED
    assert out.read_text().split("\n") == ["head", "two words", "--to"]


def test_a_custom_assurance_atom_runs_with_its_track(tmp_path):
    log = tmp_path / "log"
    write_project(tmp_path, f"[assurance]\ncontracts = {toml(record(log, 'contracts'))}\n")
    project = Project.load(tmp_path)
    assert [c.name for c in project.custom] == ["contracts"]
    assert not project.check().compliant
    write_project(
        tmp_path,
        f"""
[operation]
setup = {toml(PASS)}
[assurance]
format = {toml(PASS)}
lint = {toml(PASS)}
test = {toml(PASS)}
contracts = {toml(record(log, "contracts"))}
[security]
audit = {toml(PASS)}
[delivery]
build = {toml(PASS)}
publish = {toml(PASS)}
[documentation]
manual = {{ na = "an example" }}
""",
    )
    results = Project.load(tmp_path).run("assurance")
    assert [r.atom for r in results] == ["format", "lint", "validate", "test", "license", "contracts"]
    assert log.read_text().split() == ["contracts"]


def test_an_unknown_name_is_refused(tmp_path):
    write_project(tmp_path)
    with pytest.raises(UnknownAtomError):
        Project.load(tmp_path).run("deploy-everything")


def test_a_track_takes_no_arguments(tmp_path):
    write_project(tmp_path)
    with pytest.raises(UsageError):
        Project.load(tmp_path).run("assurance", "--fast")


def test_a_custom_atom_may_not_take_a_tracks_name(tmp_path):
    write_project(tmp_path, '[operation]\nsecurity = "scan"\n')
    with pytest.raises(BindingError):
        Project.load(tmp_path)
