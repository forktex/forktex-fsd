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

"""The `fsd` command line: what each invocation does, prints and exits with."""

from __future__ import annotations

import io
import json
import runpy
import sys
from pathlib import Path

import pytest
from conftest import FAIL, LIBRARY_MUSTS, MANUAL_FILES, say, shell, toml, write_files, write_project

from forktex_fsd import UsageError
from forktex_fsd._cli import Invocation, Verb, main, parse, terminal_style


def row(out: str, atom: str) -> list[str]:
    """The cells of one atom's row in a boxed table, without the frame."""
    line = next(line for line in out.splitlines() if f" {atom} " in line and not line.startswith(("┌", "├")))
    return line.strip("│| ").split()


def compliant_repo(root: Path, body: str = LIBRARY_MUSTS) -> None:
    write_project(root, body)
    write_files(root, *MANUAL_FILES)


# ── parsing ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("argv", "verb", "target", "args"),
    [
        ([], Verb.OVERVIEW, "", ()),
        (["assurance", "security"], Verb.RUN, "assurance", ("security",)),
        (["report"], Verb.REPORT, "", ()),
        (["help"], Verb.HELP, "", ()),
        (["help", "test"], Verb.HELP, "test", ()),
        (["-h"], Verb.HELP, "", ()),
        (["--help"], Verb.HELP, "", ()),
        (["run", "start", "api"], Verb.RUN, "start", ("api",)),
        (["start", "api", "--port", "8000"], Verb.RUN, "start", ("api", "--port", "8000")),
        (["migrate", "-C", "x"], Verb.RUN, "migrate", ("-C", "x")),
    ],
)
def test_parse(argv, verb, target, args):
    invocation = parse(argv)
    assert (invocation.verb, invocation.target, invocation.args) == (verb, target, args)


def test_parse_reads_the_directory_before_the_command(tmp_path):
    assert parse(["-C", str(tmp_path), "test"]) == Invocation(directory=tmp_path, verb=Verb.RUN, target="test")


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["-C"], "-C needs a directory"),
        (["run"], "usage: fsd run <atom>"),
        (["report", "x"], "takes no arguments"),
    ],
)
def test_parse_refuses_malformed_input(argv, message):
    with pytest.raises(UsageError, match=message):
        parse(argv)


# ── bare fsd: the project, or help ───────────────────────────────────────────


def test_bare_fsd_inside_a_repository_shows_it(tmp_path, capsys, monkeypatch):
    compliant_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main([]) == 0
    out = capsys.readouterr().out
    first = out.splitlines()[0]
    assert first.startswith(f"┌─ {tmp_path.name} · library · FSD 1.0.0 ")
    assert first.endswith(" compliant ─┐")
    assert "├─ assurance ─" in out
    assert row(out, "validate") == ["warn", "validate", "standard", "should", "unbound", "—"]


def test_bare_fsd_marks_failures_and_exits_one(tmp_path, capsys):
    write_project(tmp_path, "")
    assert main(["-C", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert out.splitlines()[0].endswith(" not compliant ─┐")
    assert row(out, "setup")[:2] == ["FAIL", "setup"]


def test_bare_fsd_outside_a_repository_prints_help(tmp_path, capsys):
    assert main(["-C", str(tmp_path)]) == 0
    assert capsys.readouterr().out.startswith("fsd — the ForkTex Standard of Delivery 1.0.0")


def test_fsd_finds_the_repository_from_a_subdirectory(tmp_path, capsys):
    compliant_repo(tmp_path)
    (tmp_path / "src").mkdir()
    assert main(["-C", str(tmp_path / "src")]) == 0
    assert capsys.readouterr().out.startswith(f"┌─ {tmp_path.name} · library")


# ── help ─────────────────────────────────────────────────────────────────────


def test_help_lists_usage_and_every_atom(capsys):
    assert main(["help"]) == 0
    out = capsys.readouterr().out
    assert row(out, "install")[:5] == ["install", "host", "na", "must", "na"]


def test_help_json_is_the_standard_as_data(capsys):
    assert main(["help", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["version"] == "1.0.0"
    assert [a["name"] for a in data["atoms"]][-1] == "manual"


def test_help_on_an_atom_shows_its_contract_and_this_repositorys_binding(tmp_path, capsys):
    compliant_repo(tmp_path)
    assert main(["-C", str(tmp_path), "help", "manual"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("manual — documentation")
    assert "strength   library must, application must, service must" in out
    assert "bound here README.md, AGENTS.md" in out


def test_help_on_a_track_shows_its_summary_and_atoms(tmp_path, capsys):
    assert main(["-C", str(tmp_path), "help", "security"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("What the software depends on")
    assert row(out, "audit")[:2] == ["audit", "read-only"]
    assert "format" not in out


def test_help_on_a_track_as_json(tmp_path, capsys):
    assert main(["-C", str(tmp_path), "help", "documentation", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "kind": "track",
        "name": "documentation",
        "summary": "A newcomer, a person or an agent, can start from the repository alone.",
        "checks": True,
        "atoms": ["manual"],
    }


def test_help_on_an_unbound_atom_says_so(tmp_path, capsys):
    write_project(tmp_path, "")
    main(["-C", str(tmp_path), "help", "test"])
    assert "bound here —" in capsys.readouterr().out


def test_help_on_an_atom_as_json(capsys):
    assert main(["help", "install", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["effect"] == "host"


# ── running ──────────────────────────────────────────────────────────────────


def test_an_atom_runs_by_name_with_its_arguments(tmp_path, capsys):
    out = tmp_path / "out"
    command = shell(sys.executable, "-c", f"import sys; open({str(out)!r}, 'w').write(' '.join(sys.argv[1:]))")
    write_project(tmp_path, f"[operation]\nmigrate = {toml(command)}\n")
    assert main(["-C", str(tmp_path), "migrate", "head", "--sql"]) == 0
    assert out.read_text() == "head --sql"
    assert "fsd: migrate passed" in capsys.readouterr().err


def test_run_reports_a_failing_step(tmp_path, capsys):
    write_project(tmp_path, f"[assurance]\nlint = {toml(FAIL)}\n")
    assert main(["-C", str(tmp_path), "run", "lint"]) == 1
    assert "fsd: lint failed (exit code 3)" in capsys.readouterr().err


def test_an_unknown_atom_exits_two(tmp_path, capsys):
    write_project(tmp_path, "")
    assert main(["-C", str(tmp_path), "gate"]) == 2
    assert "no atom 'gate'" in capsys.readouterr().err


def test_each_checks_track_runs_on_its_own(tmp_path, capsys):
    compliant_repo(tmp_path)
    assert [main(["-C", str(tmp_path), track]) for track in ("assurance", "security", "documentation")] == [0, 0, 0]
    err = capsys.readouterr().err.splitlines()
    assert err[0] == "fsd: format passed"
    assert err[-2:] == ["fsd: audit passed", "fsd: manual passed (README.md, AGENTS.md)"]


@pytest.mark.parametrize("command", [["assurance"], ["run", "assurance"]])
def test_a_track_that_is_not_compliant_runs_nothing(tmp_path, capsys, command):
    write_project(tmp_path, f"[assurance]\nformat = {toml(say('ran'))}\n")
    assert main(["-C", str(tmp_path), *command]) == 1
    captured = capsys.readouterr()
    assert "ran" not in captured.out
    assert captured.err.startswith("fsd: assurance failed (not compliant")


def test_a_track_takes_no_arguments_not_even_other_tracks(tmp_path, capsys):
    compliant_repo(tmp_path)
    assert main(["-C", str(tmp_path), "assurance", "security"]) == 2
    assert main(["-C", str(tmp_path), "operation"]) == 2


def test_invalid_input_exits_two_with_the_reason(tmp_path, capsys):
    assert main(["-C", str(tmp_path), "assurance"]) == 2
    assert "no fsd.toml in" in capsys.readouterr().err


def test_dunder_main_runs_the_cli_in_process(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["fsd", "help"])
    with pytest.raises(SystemExit) as exit_:
        runpy.run_module("forktex_fsd", run_name="__main__")
    assert exit_.value.code == 0
    assert capsys.readouterr().out.startswith("fsd — the ForkTex Standard of Delivery")


class _Stream:
    def __init__(self, encoding: str | None, tty: bool) -> None:
        self.encoding = encoding
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_terminal_style_follows_the_terminal(monkeypatch):
    monkeypatch.setattr(sys, "stdout", _Stream("utf-8", True))
    assert (terminal_style().colour, terminal_style().unicode) == (True, True)
    monkeypatch.setattr(sys, "stdout", _Stream("ascii", False))
    assert (terminal_style().colour, terminal_style().unicode) == (False, False)
    monkeypatch.setattr(sys, "stdout", _Stream(None, False))
    assert terminal_style().unicode is False


def test_a_broken_fsd_toml_is_reported_not_hidden_behind_help(tmp_path, capsys):
    write_project(tmp_path, profile="libary")
    assert main(["-C", str(tmp_path)]) == 2
    assert capsys.readouterr().err.startswith("fsd: ")
    assert main(["-C", str(tmp_path), "help", "test"]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("test — assurance")
    assert captured.err.endswith("showing the standard alone\n")


@pytest.mark.parametrize(
    ("argv", "kind"),
    [(["help", "--json"], "standard"), (["help", "test", "--json"], "atom"), (["help", "migrate", "--json"], "custom")],
)
def test_every_help_json_names_its_kind(tmp_path, capsys, argv, kind):
    write_project(tmp_path, '[operation]\nmigrate = "alembic upgrade head"\n[assurance]\ntest = "pytest"\n')
    assert main(["-C", str(tmp_path), *argv]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["kind"] == kind
    if kind == "atom":
        assert data["binding"] == "pytest"


def test_version_names_the_package_and_the_standard(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.split() == ["fsd", "1.0.0", "1.0.0"]


@pytest.mark.parametrize("target", ["missing", "fsd.toml"])
def test_dash_c_must_name_a_directory(tmp_path, capsys, target):
    write_project(tmp_path)
    assert main(["-C", str(tmp_path / target)]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_a_report_that_cannot_be_written_exits_two(tmp_path, capsys, monkeypatch):
    write_project(tmp_path)
    monkeypatch.setattr("forktex_fsd._cli.REPORT_JSON", "no-such-dir/fsd-report.json")
    assert main(["-C", str(tmp_path), "report"]) == 2
    assert "No such file or directory" in capsys.readouterr().err


def test_help_on_a_custom_atom_shows_its_command(tmp_path, capsys):
    write_project(tmp_path, '[operation]\nmigrate = "alembic upgrade head"\n')
    assert main(["-C", str(tmp_path), "help", "migrate"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("migrate — operation")
    assert "alembic upgrade head" in out


def test_help_on_a_custom_atom_as_json(tmp_path, capsys):
    write_project(tmp_path, '[operation]\nmigrate = "alembic upgrade head"\n')
    assert main(["-C", str(tmp_path), "help", "migrate", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["track"] == "operation"


def test_a_console_that_cannot_encode_gets_replacements_not_a_traceback(tmp_path, monkeypatch):
    write_project(tmp_path, '[operation]\nmigrate = "echo ✓ done"\n')
    console = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
    monkeypatch.setattr(sys, "stdout", console)
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert main(["-C", str(tmp_path), "help", "migrate"]) == 0
    console.flush()
    text = console.buffer.getvalue().decode("ascii")
    assert text.startswith("migrate - operation")
    assert "echo ? done" in text


def test_help_on_an_atom_outside_a_project_has_no_binding_line(tmp_path, capsys):
    assert main(["-C", str(tmp_path), "help", "test"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("test — assurance")
    assert "bound here" not in out
