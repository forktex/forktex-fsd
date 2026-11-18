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


"""A library: bind it, see where it stands, run its atoms, gate it."""

from __future__ import annotations

import pytest
from conftest import FAIL, MANUAL_FILES, PASS, say, toml, write_files, write_project

from forktex_fsd import Command, FileBinding, Outcome, Profile, Project, ProjectNotFoundError, Status

LIBRARY = f"""
[operation]
setup = {toml(PASS)}

[assurance]
format = {toml(PASS)}
lint = {toml([PASS, PASS])}
test = {toml(say("3 passed"))}

[security]
audit = {toml(PASS)}

[delivery]
build = {toml(PASS)}
publish = {toml(PASS)}

[documentation]
manual = {{ file = ["README.md", "AGENTS.md"] }}
"""


@pytest.fixture
def library(tmp_path):
    write_project(tmp_path, LIBRARY)
    write_files(tmp_path, *MANUAL_FILES)
    return tmp_path


def test_the_readme_example(library, monkeypatch):
    monkeypatch.chdir(library)

    project = Project.find()
    compliance = project.check()
    gaps = {track.track: [a.atom for a in track.failures] for track in compliance.tracks}

    tested = project.run("test", on_output=lambda line: None)
    report = project.report(on_output=lambda line: None)

    assert project.profile is Profile.LIBRARY
    assert compliance.compliant and all(not atoms for atoms in gaps.values())
    assert [r.outcome for r in tested] == [Outcome.PASSED]
    assert report.passed and report.to_markdown().startswith("# FSD report")


def test_a_binding_reads_as_written(library):
    project = Project.load(library)
    assert project.binding("lint") == Command(steps=(PASS, PASS))
    assert project.binding("manual") == FileBinding(file=MANUAL_FILES)
    assert project.binding("validate") is None


def test_a_project_is_found_from_anywhere_inside_it(library):
    (library / "src" / "pkg").mkdir(parents=True)
    assert Project.find(library / "src" / "pkg").root == library
    assert Project.load(library).root == library


def test_a_relative_root_is_resolved(library, monkeypatch):
    monkeypatch.chdir(library)
    assert Project.load(".").root == library
    assert Project.load(".").report(on_output=lambda line: None).project == library.name


def test_there_is_no_project_outside_one(tmp_path):
    with pytest.raises(ProjectNotFoundError):
        Project.find(tmp_path)


def test_a_gap_is_named_on_its_track(tmp_path):
    write_project(tmp_path, f"[assurance]\nformat = {toml(PASS)}\n")
    assurance = next(t for t in Project.load(tmp_path).check().tracks if t.track == "assurance")
    assert not assurance.compliant
    assert {a.atom: a.status for a in assurance.failures} == {"lint": Status.UNBOUND, "test": Status.UNBOUND}


def test_the_gate_is_the_checks_tracks_run_in_order(library):
    project = Project.load(library)
    results = [
        r
        for track in ("assurance", "security", "documentation")
        for r in project.run(track, on_output=lambda line: None)
    ]
    assert [(r.atom, r.outcome) for r in results] == [
        ("format", Outcome.PASSED),
        ("lint", Outcome.PASSED),
        ("validate", Outcome.SKIPPED),
        ("test", Outcome.PASSED),
        ("license", Outcome.SKIPPED),
        ("audit", Outcome.PASSED),
        ("manual", Outcome.PASSED),
    ]


def test_a_track_stops_at_the_first_failure(library):
    write_project(library, LIBRARY.replace(f"format = {toml(PASS)}", f"format = {toml(FAIL)}"))
    results = Project.load(library).run("assurance")
    assert [(r.atom, r.outcome) for r in results] == [("format", Outcome.FAILED)]


def test_a_track_that_is_not_compliant_runs_nothing(tmp_path):
    write_project(tmp_path, f"[assurance]\nformat = {toml(say('ran'))}\n")
    seen: list[str] = []
    [result] = Project.load(tmp_path).run("assurance", on_output=seen.append)
    assert (result.atom, result.outcome, result.detail) == ("assurance", Outcome.FAILED, "not compliant — lint, test")
    assert seen == []


def test_a_track_is_compliant_on_its_own(tmp_path):
    write_project(tmp_path, f"[security]\naudit = {toml(PASS)}\n")
    project = Project.load(tmp_path)
    assert not project.check().compliant
    assert [(r.atom, r.outcome) for r in project.run("security")] == [("audit", Outcome.PASSED)]
