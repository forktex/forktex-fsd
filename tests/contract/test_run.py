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

"""Running bindings: real subprocesses through the platform shell, steps in order."""

from __future__ import annotations

import sys

import pytest
from conftest import FAIL, PASS, echo_args, record, say, shell, toml

from forktex_fsd import Outcome, Standard, UnknownAtomError, UsageError
from forktex_fsd.run import _quote, run


def test_a_passing_command(repo, standard: Standard):
    results = run(standard, repo(f"[assurance]\ntest = {toml(PASS)}\n"), "test")
    assert [(r.atom, r.outcome) for r in results] == [("test", Outcome.PASSED)]


def test_a_failing_command_reports_its_exit_code(repo, standard):
    (result,) = run(standard, repo(f"[assurance]\ntest = {toml(FAIL)}\n"), "test")
    assert (result.outcome, result.detail) == (Outcome.FAILED, "exit code 3")


def test_a_string_runs_through_the_platform_shell(repo, standard):
    # `exit N` means the same in sh and in cmd.
    (ok,) = run(standard, repo('[assurance]\nlint = "exit 0"\n'), "lint")
    (bad,) = run(standard, repo('[assurance]\nlint = "exit 4"\n'), "lint")
    assert ok.outcome is Outcome.PASSED
    assert (bad.outcome, bad.detail) == (Outcome.FAILED, "exit code 4")


def test_a_list_runs_its_steps_in_order(repo, standard, tmp_path):
    log = tmp_path / "log"
    body = f"[delivery]\nbuild = {toml([record(log, 'one'), record(log, 'two'), record(log, 'three')])}\n"
    (result,) = run(standard, repo(body), "build")
    assert result.outcome is Outcome.PASSED
    assert log.read_text().split() == ["one", "two", "three"]


def test_the_first_failing_step_stops_the_atom_and_is_named(repo, standard, tmp_path):
    log = tmp_path / "log"
    body = f"[delivery]\nbuild = {toml([record(log, 'one'), FAIL, record(log, 'three')])}\n"
    (result,) = run(standard, repo(body), "build")
    assert (result.outcome, result.detail) == (Outcome.FAILED, "step 2 of 3, exit code 3")
    assert log.read_text().split() == ["one"]


def test_commands_run_in_the_repository_root(repo, standard, tmp_path):
    probe = shell(sys.executable, "-c", "import pathlib; pathlib.Path('here').write_text('x')")
    run(standard, repo(f"[assurance]\ntest = {toml(probe)}\n"), "test")
    assert (tmp_path / "here").exists()


def test_a_file_atom_passes_only_when_the_file_exists(repo, standard, tmp_path):
    project = repo('[documentation]\nmanual = { file = ["README.md", "AGENTS.md"] }\n')
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    (missing,) = run(standard, project, "manual")
    assert (missing.outcome, missing.detail) == (Outcome.FAILED, "missing: AGENTS.md")
    (tmp_path / "AGENTS.md").write_text("hello", encoding="utf-8")
    (present,) = run(standard, project, "manual")
    assert (present.outcome, present.detail) == (Outcome.PASSED, "README.md, AGENTS.md")


def test_a_declared_not_applicable_atom_is_skipped_with_its_reason(repo, standard):
    (result,) = run(standard, repo('[delivery]\npublish = { na = "internal only" }\n'), "publish")
    assert (result.outcome, result.detail) == (Outcome.SKIPPED, "na: internal only")


def test_an_unbound_must_fails_rather_than_passing_silently(repo, standard):
    (result,) = run(standard, repo(""), "test")
    assert (result.outcome, result.detail) == (Outcome.FAILED, "required here, and not bound")


def test_an_unbound_optional_atom_is_skipped(repo, standard):
    (result,) = run(standard, repo(""), "validate")
    assert (result.outcome, result.detail) == (Outcome.SKIPPED, "not bound")


def test_a_custom_atom_runs_by_name(repo, standard, tmp_path):
    log = tmp_path / "log"
    (result,) = run(standard, repo(f"[operation]\nmigrate = {toml(record(log, 'migrated'))}\n"), "migrate")
    assert (result.atom, result.outcome) == ("migrate", Outcome.PASSED)
    assert log.read_text().split() == ["migrated"]


def test_an_unknown_name_lists_the_custom_atoms_too(repo, standard):
    with pytest.raises(UnknownAtomError) as unknown:
        run(standard, repo(f"[operation]\nmigrate = {toml(PASS)}\n"), "gate")
    assert unknown.value.details == {"atom": "gate"}
    assert "migrate" in str(unknown.value)


def test_a_track_runs_its_standard_then_its_custom_atoms_in_order(repo, standard, tmp_path):
    log = tmp_path / "log"
    body = f"""
[operation]
migrate = {toml(record(log, "migrate"))}
[assurance]
test = {toml(record(log, "test"))}
format = {toml(record(log, "format"))}
lint = {toml(record(log, "lint"))}
license = {{ na = "no source headers in this fixture" }}
contracts = {toml(record(log, "contracts"))}
[security]
audit = {toml(record(log, "audit"))}
secrets = {toml(record(log, "secrets"))}
[delivery]
publish = {toml(record(log, "publish"))}
"""
    results = run(standard, repo(body), "assurance")
    assert log.read_text().split() == ["format", "lint", "test", "contracts"]
    assert [(r.atom, r.outcome) for r in results] == [
        ("format", Outcome.PASSED),
        ("lint", Outcome.PASSED),
        ("validate", Outcome.SKIPPED),
        ("test", Outcome.PASSED),
        ("license", Outcome.SKIPPED),
        ("contracts", Outcome.PASSED),
    ]


def test_a_track_stops_at_the_first_failure(repo, standard, tmp_path):
    log = tmp_path / "log"
    body = f"""
[assurance]
format = {toml(record(log, "format"))}
lint = {toml(FAIL)}
test = {toml(record(log, "test"))}
"""
    results = run(standard, repo(body), "assurance")
    assert [r.atom for r in results] == ["format", "lint"]
    assert results[-1].outcome is Outcome.FAILED
    assert log.read_text().split() == ["format"]


def test_a_track_fails_on_an_unbound_must_atom(repo, standard):
    results = run(standard, repo(""), "security")
    assert [(r.atom, r.outcome) for r in results] == [("audit", Outcome.FAILED)]


def test_the_documentation_track_checks_its_files(repo, standard, tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    results = run(standard, repo('[documentation]\nmanual = { file = "README.md" }\n'), "documentation")
    assert [(r.atom, r.outcome) for r in results] == [("manual", Outcome.PASSED)]


@pytest.mark.parametrize("track", ["operation", "delivery"])
def test_a_track_that_acts_does_not_run_as_a_whole(repo, standard, track):
    with pytest.raises(UsageError) as refused:
        run(standard, repo(""), track)
    assert refused.value.details == {"track": track}


def test_an_external_atom_runs_when_named_on_its_own(repo, standard, tmp_path):
    log = tmp_path / "log"
    run(standard, repo(f"[delivery]\npublish = {toml(record(log, 'publish'))}\n"), "publish")
    assert log.read_text().split() == ["publish"]


def test_a_command_that_cannot_start_fails_its_atom(repo, standard):
    (result,) = run(standard, repo(f"[assurance]\ntest = {toml('true ' + 'x' * 3_000_000)}\n"), "test")
    assert result.outcome is Outcome.FAILED
    assert result.detail.startswith("could not start: ")


def test_arguments_follow_a_single_command(repo, standard, tmp_path):
    out = tmp_path / "out"
    body = f"[operation]\nstart = {toml(echo_args(out))}\n"
    (result,) = run(standard, repo(body, profile="service"), "start", ("api", "--port", "8000"))
    assert result.outcome is Outcome.PASSED
    assert out.read_text().split("\n") == ["api", "--port", "8000"]


def test_arguments_to_several_commands_without_a_placeholder_are_refused(repo, standard, tmp_path):
    log = tmp_path / "log"
    body = f"[assurance]\nlint = {toml([record(log, 'first'), record(log, 'second')])}\n"
    with pytest.raises(UsageError) as refused:
        run(standard, repo(body), "lint", ("src/x",))
    assert refused.value.details == {"atom": "lint"}
    assert not log.exists()


def test_every_command_that_says_args_gets_them_and_the_others_none(repo, standard, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    steps = [echo_args(first) + " {args}", echo_args(second)]
    run(standard, repo(f"[assurance]\ntest = {toml(steps)}\n"), "test", ("-k", "two words"))
    assert first.read_text().split("\n") == ["-k", "two words"]
    assert second.read_text() == ""


def test_several_commands_without_a_placeholder_run_plainly_without_arguments(repo, standard, tmp_path):
    log = tmp_path / "log"
    body = f"[assurance]\nlint = {toml([record(log, 'first'), record(log, 'second')])}\n"
    (result,) = run(standard, repo(body), "lint")
    assert result.outcome is Outcome.PASSED
    assert log.read_text().split() == ["first", "second"]


def test_arguments_land_at_the_placeholder_quoted(repo, standard, tmp_path):
    out = tmp_path / "out"
    step = echo_args(out) + " {args} --last"
    run(standard, repo(f"[operation]\nstart = {toml(step)}\n", profile="service"), "start", ("two words",))
    assert out.read_text().split("\n") == ["two words", "--last"]


def test_a_placeholder_without_arguments_empties(repo, standard, tmp_path):
    out = tmp_path / "out"
    step = echo_args(out) + " {args}"
    run(standard, repo(f"[operation]\nstart = {toml(step)}\n", profile="service"), "start")
    assert out.read_text() == ""


def test_custom_atoms_take_arguments_too(repo, standard, tmp_path):
    out = tmp_path / "out"
    run(standard, repo(f"[operation]\nmigrate = {toml(echo_args(out))}\n"), "migrate", ("head",))
    assert out.read_text() == "head"


def test_a_track_takes_no_arguments(repo, standard):
    with pytest.raises(UsageError) as refused:
        run(standard, repo(""), "assurance", ("x",))
    assert refused.value.details == {"track": "assurance"}


def test_arguments_to_an_atom_that_is_not_a_command_are_refused(repo, standard):
    with pytest.raises(UsageError, match="not bound to a command here"):
        run(standard, repo('[delivery]\npublish = { na = "internal only" }\n'), "publish", ("x",))


def test_arguments_are_quoted_for_cmd_on_windows():
    assert _quote(("two words", "a&b", 'say "hi"'), "win32") == '"two words" "a&b" "say ""hi"""'


def test_a_trailing_backslash_does_not_escape_the_closing_quote_on_windows():
    assert _quote(("C:\\dir\\",), "win32") == '"C:\\dir\\\\"'


def test_arguments_are_quoted_for_sh_elsewhere():
    assert _quote(("two words", "a&b"), "linux") == "'two words' 'a&b'"


def test_output_goes_to_the_callback_when_one_is_given(repo, standard, capfd):
    seen: list[str] = []
    results = run(standard, repo(f"[operation]\nmigrate = {toml(say('moved'))}\n"), "migrate", on_output=seen.append)
    assert [r.outcome for r in results] == [Outcome.PASSED]
    assert [line.strip() for line in seen] == ["moved"]
    assert "moved" not in capfd.readouterr().out
