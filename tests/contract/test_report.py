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

"""The report: what it runs, what it keeps, and what it writes."""

from __future__ import annotations

import json
import sys
import time

import pytest
from conftest import FAIL, PASS, echo_args, record, say, shell, toml

from forktex_fsd import Outcome
from forktex_fsd._cli import main
from forktex_fsd.report import Bracket, build_report, plan


def names(steps) -> list[str]:
    return ["bracket" if isinstance(s, Bracket) else s.name for s in steps]


def test_a_library_plan_is_every_routine_atom_but_clean(repo, standard):
    body = f'[operation]\ntidy = "rewrite"\n[assurance]\ncontracts = {toml(PASS)}\n[security]\nsecrets = {toml(PASS)}\n'
    steps = names(plan(standard, repo(body)))
    assert steps == [
        "setup",
        "format",
        "lint",
        "validate",
        "test",
        "license",
        "contracts",
        "audit",
        "secrets",
        "build",
        "manual",
    ]


def test_the_report_expands_args_to_nothing(repo, standard, tmp_path):
    out = tmp_path / "out"
    body = f"[assurance]\ntest = {toml(echo_args(out) + ' {args}')}\n"
    test = next(e for e in build_report(standard, repo(body)).evidence if e.atom == "test")
    assert test.outcome is Outcome.PASSED and out.read_text() == ""
    assert "{args}" not in test.steps[0]


def test_a_service_left_running_in_the_background_does_not_hold_the_report(repo, standard, tmp_path):
    detach = shell(
        sys.executable,
        "-c",
        "import subprocess, sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(8)'])",
    )
    body = f"[operation]\nstart = {toml(detach)}\nstatus = {toml(PASS)}\nstop = {toml(PASS)}\n"
    started = time.monotonic()
    report = build_report(standard, repo(body, profile="service"))
    assert time.monotonic() - started < 6
    assert [e.outcome for e in report.evidence if e.atom in ("start", "status", "stop")] == [Outcome.PASSED] * 3


def test_the_report_has_no_gate_row(repo, standard):
    report = build_report(standard, repo(f"[delivery]\nbuild = {toml(PASS)}\n"))
    assert [e.atom for e in report.evidence if e.track == "delivery"] == ["build"]


def test_a_service_plan_brackets_start_status_stop(repo, standard):
    steps = plan(standard, repo("", profile="service"))
    assert names(steps)[:2] == ["setup", "bracket"]


def test_the_report_runs_everything_and_keeps_going_after_a_failure(repo, standard, tmp_path):
    log = tmp_path / "log"
    body = f"""
[operation]
setup = {toml(record(log, "setup"))}
clean = {toml(record(log, "clean"))}
[assurance]
format = {toml(FAIL)}
lint = {toml(record(log, "lint"))}
test = {toml(record(log, "test"))}
[security]
audit = {toml(record(log, "audit"))}
[delivery]
build = {toml(record(log, "build"))}
publish = {toml(record(log, "publish"))}
[documentation]
manual = {{ file = "README.md" }}
"""
    result = build_report(standard, repo(body))
    assert log.read_text().split() == ["setup", "lint", "test", "audit", "build"]
    outcome = {e.atom: e.outcome for e in result.evidence}
    assert outcome["format"] is Outcome.FAILED
    assert outcome["validate"] is Outcome.SKIPPED
    assert outcome["manual"] is Outcome.FAILED
    assert not result.passed


def test_evidence_carries_timing_output_and_results(repo, standard, tmp_path):
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "junit.xml").write_text('<testsuite tests="4" failures="0"/>', encoding="utf-8")
    seen: list[str] = []
    body = f'[assurance]\ntest = {{ run = {toml([say("first"), say("second")])}, results = ["build/junit.xml", "htmlcov/index.html"] }}\n'
    result = build_report(standard, repo(body), on_output=seen.append)
    test = next(e for e in result.evidence if e.atom == "test")
    assert test.outcome is Outcome.PASSED
    assert test.output_tail == ("first", "second")
    assert [line.strip() for line in seen] == ["first", "second"]
    assert test.exit_code == 0
    assert test.started_at is not None and test.started_at.tzinfo is not None
    assert test.duration_seconds >= 0
    assert [r.summary for r in test.results] == ["4 tests, 0 failed, 0 skipped", "not written"]


def test_a_failing_step_is_named_in_the_evidence(repo, standard):
    result = build_report(standard, repo(f"[assurance]\nlint = {toml([PASS, FAIL])}\n"))
    lint = next(e for e in result.evidence if e.atom == "lint")
    assert (lint.outcome, lint.detail, lint.exit_code) == (Outcome.FAILED, "step 2 of 2, exit code 3", 3)


def test_a_declared_not_applicable_atom_is_skipped(repo, standard):
    result = build_report(standard, repo('[assurance]\nlicense = { na = "generated code" }\n'))
    license_ = next(e for e in result.evidence if e.atom == "license")
    assert (license_.outcome, license_.detail) == (Outcome.SKIPPED, "na: generated code")


def test_the_bracket_stops_what_it_started(repo, standard, tmp_path):
    log = tmp_path / "log"
    body = f"""
[operation]
start = {toml(record(log, "start"))}
status = {toml(FAIL)}
stop = {toml(record(log, "stop"))}
"""
    result = build_report(standard, repo(body, profile="service"))
    assert log.read_text().split() == ["start", "stop"]
    assert [e.atom for e in result.evidence if e.track == "operation"][1:4] == ["start", "status", "stop"]


def test_the_bracket_stops_what_started_partly(repo, standard, tmp_path):
    log = tmp_path / "log"
    body = f"[operation]\nstart = {toml([record(log, 'start'), FAIL])}\nstop = {toml(record(log, 'stop'))}\n"
    result = build_report(standard, repo(body, profile="service"))
    assert log.read_text().split() == ["start", "stop"]
    assert [e.atom for e in result.evidence if e.track == "operation"][1:] == ["start", "stop"]


def test_the_bracket_does_not_stop_what_was_never_bound_to_start(repo, standard, tmp_path):
    log = tmp_path / "log"
    result = build_report(standard, repo(f"[operation]\nstop = {toml(record(log, 'stop'))}\n", profile="service"))
    assert not log.exists()
    assert "stop" not in [e.atom for e in result.evidence]


def test_a_step_that_waits_for_input_gets_none(repo, standard):
    reads = shell(sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))")
    test = next(
        e for e in build_report(standard, repo(f"[assurance]\ntest = {toml(reads)}\n")).evidence if e.atom == "test"
    )
    assert (test.outcome, test.output_tail) == (Outcome.PASSED, ("''",))


def test_custom_atoms_are_marked(repo, standard):
    result = build_report(standard, repo(f"[assurance]\ncontracts = {toml(PASS)}\n"))
    assert next(e for e in result.evidence if e.atom == "contracts").custom


def test_the_json_is_a_wire_object(repo, standard):
    data = json.loads(build_report(standard, repo(f"[assurance]\ntest = {toml(PASS)}\n")).model_dump_json())
    assert set(data) == {"project", "generatedAt", "compliance", "evidence", "passed"}
    test = next(e for e in data["evidence"] if e["atom"] == "test")
    assert {"exitCode", "startedAt", "durationSeconds", "outputTail"} <= set(test)
    assert data["generatedAt"].endswith("Z") or "+00:00" in data["generatedAt"]


def test_markdown_shows_compliance_evidence_and_failing_output(repo, standard):
    body = f"[assurance]\nlint = {toml(say('bad | thing'))}\ntest = {toml([say('boom'), FAIL])}\n"
    markdown = build_report(standard, repo(body)).to_markdown()
    assert markdown.startswith("# FSD report — ")
    assert "| assurance | **no** | format, validate, license |" in markdown
    assert "| assurance | test | failed |" in markdown
    assert "### test — step 2 of 2, exit code 3" in markdown
    assert "```\nboom\n```" in markdown


def test_fsd_report_writes_json_and_markdown(tmp_path, capsys):
    (tmp_path / "fsd.toml").write_text(
        f'standard = "1.0"\nprofile = "library"\n[assurance]\ntest = {toml(say("hi"))}\n'
    )
    assert main(["-C", str(tmp_path), "report"]) == 1
    captured = capsys.readouterr()
    assert "hi" in captured.out
    assert "· report · " in captured.out
    assert "fsd: wrote fsd-report.json and fsd-report.md" in captured.err
    assert json.loads((tmp_path / "fsd-report.json").read_text())["passed"] is False
    assert (tmp_path / "fsd-report.md").read_text().startswith("# FSD report")


def test_report_takes_no_arguments(tmp_path, capsys):
    assert main(["-C", str(tmp_path), "report", "x"]) == 2
    assert "takes no arguments" in capsys.readouterr().err


def test_the_bracket_stops_the_service_even_when_status_crashes(repo, standard, tmp_path):
    log = tmp_path / "log"
    body = f"""
[operation]
start = {toml(record(log, "start"))}
status = {toml(say("boom"))}
stop = {toml(record(log, "stop"))}
"""

    def explode(line: str) -> None:
        if "boom" in line:
            raise RuntimeError("the caller's output sink failed")

    with pytest.raises(RuntimeError):
        build_report(standard, repo(body, profile="service"), on_output=explode)
    assert log.read_text().split() == ["start", "stop"]
