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

"""Result files read by format: JUnit, Cobertura and SARIF; anything else is an artifact."""

from __future__ import annotations

import json

import pytest

from forktex_fsd import Format
from forktex_fsd.results import read_result


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_junit_testsuites_are_summed(tmp_path):
    write(
        tmp_path,
        "build/junit.xml",
        '<testsuites><testsuite tests="10" failures="1" errors="1" skipped="2"/>'
        '<testsuite tests="5" failures="0" errors="0" skipped="0"/></testsuites>',
    )
    result = read_result(tmp_path, "build/junit.xml")
    assert result.format is Format.JUNIT
    assert result.values == {"tests": 15.0, "failures": 1.0, "errors": 1.0, "skipped": 2.0}
    assert result.summary == "15 tests, 2 failed, 2 skipped"


def test_a_single_junit_testsuite(tmp_path):
    write(tmp_path, "junit.xml", '<testsuite tests="3"/>')
    assert read_result(tmp_path, "junit.xml").summary == "3 tests, 0 failed, 0 skipped"


def test_cobertura_coverage(tmp_path):
    write(tmp_path, "coverage.xml", '<coverage line-rate="0.9876" branch-rate="0.5"></coverage>')
    result = read_result(tmp_path, "coverage.xml")
    assert result.format is Format.COBERTURA
    assert result.values == pytest.approx({"linePercent": 98.76, "branchPercent": 50.0})
    assert result.summary == "98.76% lines"


@pytest.mark.parametrize("name", ["lint.sarif", "lint.sarif.json"])
def test_sarif_findings_are_counted(tmp_path, name):
    sarif = {"runs": [{"results": [{}, {}]}, {"results": []}, {"tool": {}}]}
    write(tmp_path, name, json.dumps(sarif))
    result = read_result(tmp_path, name)
    assert (result.format, result.values, result.summary) == (Format.SARIF, {"findings": 2.0}, "2 findings")


def test_sarif_without_runs_has_no_findings(tmp_path):
    write(tmp_path, "x.sarif", "{}")
    assert read_result(tmp_path, "x.sarif").summary == "0 findings"


@pytest.mark.parametrize(
    ("name", "text"),
    [("report.html", "<html></html>"), ("other.xml", "<project/>"), ("notes.txt", "hello")],
)
def test_anything_else_is_an_artifact(tmp_path, name, text):
    write(tmp_path, name, text)
    result = read_result(tmp_path, name)
    assert (result.format, result.summary) == (Format.ARTIFACT, "")


@pytest.mark.parametrize(
    ("name", "text"),
    [("bad.xml", "<unclosed"), ("bad.sarif", "{not json"), ("shape.sarif", '{"runs": [{"results": 5}]}')],
)
def test_an_unreadable_file_is_an_artifact_that_says_so(tmp_path, name, text):
    write(tmp_path, name, text)
    result = read_result(tmp_path, name)
    assert (result.format, result.summary) == (Format.ARTIFACT, "unreadable as its format")


def test_a_directory_is_not_a_result_file(tmp_path):
    (tmp_path / "junit.xml").mkdir()
    assert read_result(tmp_path, "junit.xml").format is Format.MISSING


def test_a_file_that_was_not_written(tmp_path):
    result = read_result(tmp_path, "build/junit.xml")
    assert (result.format, result.summary) == (Format.MISSING, "not written")


def test_result_files_serialise_as_wire_objects(tmp_path):
    write(tmp_path, "coverage.xml", '<coverage line-rate="1"/>')
    data = read_result(tmp_path, "coverage.xml").model_dump(mode="json")
    assert data == {
        "path": "coverage.xml",
        "format": "cobertura",
        "values": {"linePercent": 100.0, "branchPercent": 0.0},
        "summary": "100.00% lines",
    }


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("coverage.xml", '<coverage line-rate="nan" branch-rate="0"/>'),
        ("coverage.xml", '<coverage line-rate="-0.5" branch-rate="0"/>'),
        ("junit.xml", '<testsuite tests="-5" failures="0"/>'),
        ("junit.xml", '<testsuite tests="2.5" failures="0"/>'),
    ],
)
def test_values_that_are_not_measurements_make_a_file_unreadable(tmp_path, name, body):
    (tmp_path / name).write_text(body, encoding="utf-8")
    result = read_result(tmp_path, name)
    assert (result.format, result.summary) == (Format.ARTIFACT, "unreadable as its format")


def test_a_suffix_in_capitals_is_read_all_the_same(tmp_path):
    (tmp_path / "JUNIT.XML").write_text('<testsuite tests="3" failures="1"/>', encoding="utf-8")
    assert read_result(tmp_path, "JUNIT.XML").values == {"tests": 3, "failures": 1, "errors": 0, "skipped": 0}


def test_a_link_out_of_the_repository_is_not_read(tmp_path):
    outside = tmp_path / "outside.xml"
    outside.write_text('<testsuite tests="3"/>', encoding="utf-8")
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo" / "junit.xml").symlink_to(outside)
    assert read_result(tmp_path / "repo", "junit.xml").format is Format.MISSING
