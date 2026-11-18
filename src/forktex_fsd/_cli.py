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

"""The `fsd` command: parses arguments, calls `Project`, renders, maps outcomes to exit codes."""

from __future__ import annotations

import io
import json
import sys
from enum import StrEnum
from pathlib import Path

from forktex.types import BaseValueObject

from forktex_fsd import (
    BindingError,
    FsdError,
    Outcome,
    Project,
    ProjectNotFoundError,
    RunResult,
    Standard,
    UsageError,
    __version__,
)
from forktex_fsd._render import (
    REPORT_JSON,
    REPORT_MARKDOWN,
    Style,
    render_atom,
    render_custom,
    render_help,
    render_project,
    render_report,
    render_result,
)

EXIT_OK = 0
EXIT_NOT_MET = 1
EXIT_INVALID = 2


class Verb(StrEnum):
    """What the command line was asked to do."""

    OVERVIEW = "overview"
    HELP = "help"
    REPORT = "report"
    RUN = "run"
    VERSION = "version"


class Invocation(BaseValueObject):
    """What the command line was asked to do, and where."""

    directory: Path
    verb: Verb
    target: str = ""
    args: tuple[str, ...] = ()
    as_json: bool = False


def parse(argv: list[str]) -> Invocation:
    # fsd's own options come before the command; everything after an atom's name
    # belongs to that atom, so `fsd start api --watch` needs no `--`.
    directory = Path.cwd()
    rest = list(argv)
    while rest and rest[0] in ("-C", "-h", "--help", "--version"):
        option = rest.pop(0)
        if option == "--version":
            return Invocation(directory=directory, verb=Verb.VERSION)
        if option != "-C":
            return Invocation(directory=directory, verb=Verb.HELP)
        if not rest:
            raise UsageError("-C needs a directory")
        directory = Path(rest.pop(0))
    if not rest:
        return Invocation(directory=directory, verb=Verb.OVERVIEW)
    word, *tail = rest
    if word == Verb.HELP:
        names = [t for t in tail if t != "--json"]
        return Invocation(
            directory=directory, verb=Verb.HELP, target=names[0] if names else "", as_json="--json" in tail
        )
    if word == Verb.RUN:
        if not tail:
            raise UsageError("usage: fsd run <atom> [args...]")
        word, *tail = tail
    if word == Verb.REPORT:
        if tail:
            raise UsageError("`report` runs every routine atom, so it takes no arguments")
        return Invocation(directory=directory, verb=Verb.REPORT)
    return Invocation(directory=directory, verb=Verb.RUN, target=word, args=tuple(tail))


def terminal_style() -> Style:
    encoding = sys.stdout.encoding or "ascii"
    try:
        "┌─┐—…·".encode(encoding)
    except UnicodeEncodeError:
        return Style(colour=sys.stdout.isatty(), unicode=False)
    return Style(colour=sys.stdout.isatty(), unicode=True)


def _find(invocation: Invocation) -> Project:
    if not invocation.directory.is_dir():
        raise UsageError(f"-C {invocation.directory}: not a directory")
    return Project.find(invocation.directory)


def _find_if_any(invocation: Invocation) -> Project | None:
    try:
        return _find(invocation)
    except ProjectNotFoundError:
        return None


def _exit_for(results: tuple[RunResult, ...]) -> int:
    for result in results:
        print(render_result(result), file=sys.stderr)
    return EXIT_NOT_MET if any(r.outcome is Outcome.FAILED for r in results) else EXIT_OK


def _overview(invocation: Invocation) -> int:
    project = _find_if_any(invocation)
    if project is None:
        print(render_help(Standard.load(), terminal_style()))
        return EXIT_OK
    compliance = project.check()
    print(render_project(compliance, project.root.name, terminal_style()))
    return EXIT_OK if compliance.compliant else EXIT_NOT_MET


def _project_for_help(invocation: Invocation) -> Project | None:
    # Help is what someone reaches for when fsd.toml is broken, so a broken file
    # is reported and the standard shown alone.
    try:
        return _find_if_any(invocation)
    except BindingError as exc:
        print(f"fsd: {exc}; showing the standard alone", file=sys.stderr)
        return None


def _print_json(kind: str, body: dict[str, object]) -> int:
    print(json.dumps({"kind": kind, **body}, indent=2))
    return EXIT_OK


def _help(invocation: Invocation) -> int:
    project = _project_for_help(invocation)
    standard = project.standard if project else Standard.load()
    style = terminal_style()
    if not invocation.target:
        if invocation.as_json:
            return _print_json("standard", standard.model_dump(mode="json"))
        print(render_help(standard, style))
        return EXIT_OK
    track = standard.track(invocation.target)
    if track is not None:
        if invocation.as_json:
            atoms = [a.name for a in standard.in_track(track.name)]
            return _print_json("track", {**track.model_dump(mode="json"), "atoms": atoms})
        print(render_help(standard, style, only=track.name))
        return EXIT_OK
    custom = project.bindings.custom_atom(invocation.target) if project else None
    if custom is not None:
        if invocation.as_json:
            return _print_json("custom", custom.model_dump(mode="json"))
        print(render_custom(custom, style))
        return EXIT_OK
    atom = standard.atom(invocation.target)
    bound = None
    if project is not None:
        compliance = project.check()
        bound = next(a.detail for t in compliance.tracks for a in t.atoms if a.atom == atom.name)
    if invocation.as_json:
        return _print_json("atom", {**atom.model_dump(mode="json"), "binding": bound})
    print(render_atom(atom, bound, style))
    return EXIT_OK


def _version(invocation: Invocation) -> int:
    print(f"fsd {__version__} {Standard.load().version}")
    return EXIT_OK


def _report(invocation: Invocation) -> int:
    project = _find(invocation)
    report = project.report(on_output=sys.stdout.write)
    (project.root / REPORT_JSON).write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (project.root / REPORT_MARKDOWN).write_text(report.to_markdown(), encoding="utf-8")
    style = terminal_style()
    print(render_project(report.compliance, project.root.name, style))
    print(render_report(report, style))
    print(f"fsd: wrote {REPORT_JSON} and {REPORT_MARKDOWN}", file=sys.stderr)
    return EXIT_OK if report.passed else EXIT_NOT_MET


def _run(invocation: Invocation) -> int:
    return _exit_for(_find(invocation).run(invocation.target, *invocation.args))


_HANDLERS = {
    Verb.OVERVIEW: _overview,
    Verb.HELP: _help,
    Verb.REPORT: _report,
    Verb.RUN: _run,
    Verb.VERSION: _version,
}


def _tolerate_unencodable_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")


def main(argv: list[str] | None = None) -> int:
    _tolerate_unencodable_output()
    try:
        invocation = parse(sys.argv[1:] if argv is None else argv)
        return _HANDLERS[invocation.verb](invocation)
    except (FsdError, OSError) as exc:
        print(f"fsd: {exc}", file=sys.stderr)
        return EXIT_INVALID


__all__ = ["main"]
