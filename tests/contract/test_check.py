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

"""Compliance per track: what fails a track, what only warns, and what executes nothing."""

from __future__ import annotations

import sys

from collections.abc import Callable
from pathlib import Path

from conftest import LIBRARY_MUSTS, MANUAL_FILES, PASS, shell, toml, write_files

from forktex_fsd import Bindings, Standard, Status, Strength
from forktex_fsd.check import check


def by_atom(report):
    return {a.atom: a for t in report.tracks for a in t.atoms}


def track(report, name):
    return next(t for t in report.tracks if t.track == name)


def test_every_library_must_bound_is_compliant(repo: Callable[..., Bindings], standard: Standard, tmp_path: Path):
    write_files(tmp_path, *MANUAL_FILES)
    report = check(standard, repo(LIBRARY_MUSTS))
    assert report.compliant
    atoms = by_atom(report)
    assert atoms["manual"].status is Status.PRESENT
    assert atoms["deploy"].status is Status.NOT_APPLICABLE
    # The `should` atoms are left unbound: warnings, never failures.
    assert {a.atom for a in track(report, "assurance").warnings} == {"validate", "license"}


def test_an_unbound_must_fails_only_its_own_track(repo, standard, tmp_path):
    write_files(tmp_path, *MANUAL_FILES)
    report = check(standard, repo(LIBRARY_MUSTS.replace("audit = ", "# audit = ")))
    security = track(report, "security")
    assert not security.compliant
    assert [a.atom for a in security.failures] == ["audit"]
    assert by_atom(report)["audit"].status is Status.UNBOUND
    assert not report.compliant
    assert all(t.compliant for t in report.tracks if t.track != "security")


def test_a_bound_file_that_does_not_exist_fails(repo, standard):
    report = check(standard, repo(LIBRARY_MUSTS))
    manual = by_atom(report)["manual"]
    assert manual.status is Status.MISSING_FILE
    assert manual.detail == "README.md, AGENTS.md"
    assert not track(report, "documentation").compliant


def test_a_must_declared_not_applicable_is_compliant_and_keeps_its_reason(repo, standard, tmp_path):
    write_files(tmp_path, *MANUAL_FILES)
    body = LIBRARY_MUSTS.replace(f"publish = {toml(PASS)}", 'publish = { na = "internal only" }')
    report = check(standard, repo(body))
    publish = by_atom(report)["publish"]
    assert publish.status is Status.DECLARED_NA
    assert publish.detail == "internal only"
    assert not publish.is_gap


def test_a_service_needs_start_stop_and_deploy(repo, standard):
    report = check(standard, repo("", profile="service"))
    atoms = by_atom(report)
    for name in ("start", "stop", "status", "deploy"):
        assert atoms[name].strength is Strength.MUST
        assert atoms[name].status is Status.UNBOUND
    assert atoms["rollback"].strength is Strength.SHOULD
    assert atoms["publish"].strength is Strength.SHOULD


def test_an_atom_bound_beyond_its_profile_is_reported_as_bound(repo, standard):
    report = check(standard, repo('[operation]\nstart = "serve"\n'))
    start = by_atom(report)["start"]
    assert start.status is Status.BOUND
    assert start.strength is Strength.NOT_APPLICABLE
    assert start.detail == "serve"


def test_custom_atoms_are_listed_under_their_track_and_never_counted(repo, standard):
    report = check(standard, repo('[assurance]\ncontracts = ["schemathesis run", "report"]\n'))
    contracts = by_atom(report)["contracts"]
    assert (contracts.custom, contracts.strength, contracts.status) == (True, None, Status.BOUND)
    assert contracts.detail == "schemathesis run ; report"
    assert track(report, "assurance").atoms[-1].atom == "contracts"
    assert not contracts.is_gap


def test_check_executes_nothing(repo, standard, tmp_path):
    marker = tmp_path / "ran"
    touch = shell(sys.executable, "-c", f"open({str(marker)!r}, 'w')")
    body = f"[assurance]\ntest = {toml(touch)}\nlint = {toml([touch, touch])}\n"
    report = check(standard, repo(body))
    assert by_atom(report)["lint"].detail == f"{touch} ; {touch}"
    assert not marker.exists()


def test_report_serialises_per_track(repo, standard):
    data = check(standard, repo("")).model_dump(mode="json")
    assert data["standard"] == standard.version
    assert data["profile"] == "library"
    assert data["compliant"] is False
    assert [t["track"] for t in data["tracks"]] == [t.name for t in standard.tracks]
    first = data["tracks"][0]["atoms"][0]
    assert first == {"atom": "setup", "strength": "must", "status": "unbound", "detail": "", "custom": False}
