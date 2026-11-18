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

from __future__ import annotations

import re
import shlex
import subprocess
import sys
import threading
from collections import deque
from collections.abc import Callable, Iterable
from enum import StrEnum
from pathlib import Path

from forktex.log import get_logger
from forktex.types import BaseValueObject, BaseWireValueObject

from forktex_fsd.binding import Bindings, Command, CustomAtom, FileBinding, NotApplicable
from forktex_fsd.errors import UnknownAtomError, UsageError
from forktex_fsd.standard import Atom, Standard, Strength, Track

log = get_logger(__name__)

_ARGS = "{args}"
_TAIL_LINES = 60
# The exit code a shell gives a command it found but could not run.
_CANNOT_START = 126
# How long output already written may take to arrive once a step has exited. A step that leaves
# a process behind holding its output (a service started in the background) is not waited for.
_GRACE_SECONDS = 1.0

type OnOutput = Callable[[str], object]


class Outcome(StrEnum):
    """How running an atom ended."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunResult(BaseWireValueObject):
    """The outcome of running one atom."""

    atom: str
    outcome: Outcome
    detail: str = ""


class Execution(BaseValueObject):
    """How a sequence of steps ended, and the last lines of its output when captured."""

    code: int
    total: int
    failed_step: int | None = None
    output: tuple[str, ...] = ()
    error: str = ""

    @property
    def passed(self) -> bool:
        return self.code == 0

    def describe(self) -> str:
        where = f"step {self.failed_step} of {self.total}, " if self.total > 1 else ""
        return f"{where}could not start: {self.error}" if self.error else f"{where}exit code {self.code}"


def _quote_for_cmd(arg: str) -> str:
    # Inside double quotes cmd treats & | < > ^ as text; only " needs doubling.
    # A % still expands environment variables — cmd offers no escape for it in a quoted argument.
    # Trailing backslashes are doubled, or the program would read the closing quote as escaped.
    return '"' + re.sub(r"(\\+)$", r"\1\1", arg.replace('"', '""')) + '"'


def _quote(args: Iterable[str], platform: str = sys.platform) -> str:
    if platform == "win32":
        return " ".join(_quote_for_cmd(arg) for arg in args)
    return shlex.join(args)


def with_args(steps: tuple[str, ...], args: tuple[str, ...]) -> tuple[str, ...]:
    # Arguments land where a step says `{args}`; a single command with no placeholder
    # takes them at its end, as npm passes them on. A placeholder with no arguments empties.
    quoted = _quote(args)
    if any(_ARGS in step for step in steps):
        return tuple(step.replace(_ARGS, quoted).rstrip() for step in steps)
    if not args:
        return steps
    return (*steps[:-1], f"{steps[-1]} {quoted}")


def _run_inherited(line: str, cwd: Path) -> int:
    return subprocess.run(line, shell=True, cwd=cwd, check=False).returncode


def _steps(steps: tuple[str, ...], run_one: Callable[[str], int]) -> Execution:
    for index, line in enumerate(steps, start=1):
        log.debug("fsd.step", extra={"command": line})
        try:
            code = run_one(line)
        except OSError as exc:
            return Execution(code=_CANNOT_START, total=len(steps), failed_step=index, error=exc.strerror or str(exc))
        if code != 0:
            return Execution(code=code, total=len(steps), failed_step=index)
    return Execution(code=0, total=len(steps))


def execute(steps: tuple[str, ...], cwd: Path) -> Execution:
    """Run steps in order through the platform shell, output going straight to the terminal."""
    return _steps(steps, lambda line: _run_inherited(line, cwd))


class _Capture:
    """The output of a step, read on its own thread so that a process left behind cannot hold the step open."""

    def __init__(self, on_output: OnOutput | None) -> None:
        self.on_output = on_output
        self.tail: deque[str] = deque(maxlen=_TAIL_LINES)
        self.failure: Exception | None = None
        self.lock = threading.Lock()

    def drain(self, stream: Iterable[str]) -> None:
        for output in stream:
            with self.lock:
                self.tail.append(output.rstrip("\n"))
            if self.on_output is not None and self.failure is None:
                try:
                    self.on_output(output)
                except Exception as exc:
                    self.failure = exc

    def lines(self) -> tuple[str, ...]:
        with self.lock:
            return tuple(self.tail)


def execute_captured(steps: tuple[str, ...], cwd: Path, on_output: OnOutput | None = None) -> Execution:
    """Run steps as `execute` does, keeping the last lines of output; `on_output` sees every line as it comes."""
    capture = _Capture(on_output)

    def run_one(line: str) -> int:
        process = subprocess.Popen(
            line,
            shell=True,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        reader = threading.Thread(target=capture.drain, args=(process.stdout,), daemon=True)
        reader.start()
        code = process.wait()
        reader.join(timeout=_GRACE_SECONDS)
        if not reader.is_alive() and process.stdout is not None:
            process.stdout.close()
        if capture.failure is not None:
            raise capture.failure
        return code

    return _steps(steps, run_one).model_copy(update={"output": capture.lines()})


def resolve(atom: Atom, bindings: Bindings) -> RunResult | Command:
    """What an atom's binding amounts to without running anything: an outcome already, or a command to run."""
    binding = bindings.binding(atom.name)
    match binding:
        case None if atom.strength_for(bindings.profile) is Strength.MUST:
            return RunResult(atom=atom.name, outcome=Outcome.FAILED, detail="required here, and not bound")
        case None:
            return RunResult(atom=atom.name, outcome=Outcome.SKIPPED, detail="not bound")
        case NotApplicable(na=reason):
            return RunResult(atom=atom.name, outcome=Outcome.SKIPPED, detail=f"na: {reason}")
        case FileBinding() as files:
            missing = files.missing(bindings.root)
            if missing:
                return RunResult(atom=atom.name, outcome=Outcome.FAILED, detail=f"missing: {', '.join(missing)}")
            return RunResult(atom=atom.name, outcome=Outcome.PASSED, detail=", ".join(files.file))
        case _:
            return binding


def track_atoms(standard: Standard, bindings: Bindings, track: str) -> tuple[Atom | CustomAtom, ...]:
    """A track's atoms in the order they run: the standard's, then the repository's own."""
    return (*standard.in_track(track), *bindings.custom_in((track,)))


def _execute(
    name: str, command: Command, bindings: Bindings, args: tuple[str, ...], on_output: OnOutput | None
) -> RunResult:
    if args and len(command.steps) > 1 and not any(_ARGS in step for step in command.steps):
        raise UsageError(
            f"`{name}` runs {len(command.steps)} commands and none says where arguments go;"
            " write {args} in the ones that take them",
            details={"atom": name},
        )
    steps = with_args(command.steps, args)
    if on_output is None:
        execution = execute(steps, bindings.root)
    else:
        execution = execute_captured(steps, bindings.root, on_output)
    if execution.passed:
        return RunResult(atom=name, outcome=Outcome.PASSED)
    return RunResult(atom=name, outcome=Outcome.FAILED, detail=execution.describe())


def _run_atom(
    atom: Atom | CustomAtom, bindings: Bindings, args: tuple[str, ...], on_output: OnOutput | None
) -> RunResult:
    if isinstance(atom, CustomAtom):
        return _execute(atom.name, atom.command, bindings, args, on_output)
    settled = resolve(atom, bindings)
    if isinstance(settled, Command):
        return _execute(atom.name, settled, bindings, args, on_output)
    if args:
        raise UsageError(f"`{atom.name}` is not bound to a command here, so it takes no arguments")
    return settled


def _run_track(
    track: Track, standard: Standard, bindings: Bindings, args: tuple[str, ...], on_output: OnOutput | None
) -> tuple[RunResult, ...]:
    if not track.checks:
        raise UsageError(
            f"`{track.name}` acts rather than checks, so it does not run as a whole; run its atoms by name",
            details={"track": track.name},
        )
    if args:
        raise UsageError(f"`{track.name}` runs several atoms, so it takes no arguments", details={"track": track.name})
    results: list[RunResult] = []
    for atom in track_atoms(standard, bindings, track.name):
        results.append(_run_atom(atom, bindings, (), on_output))
        if results[-1].outcome is Outcome.FAILED:
            break
    return tuple(results)


def run(
    standard: Standard,
    bindings: Bindings,
    name: str,
    args: tuple[str, ...] = (),
    on_output: OnOutput | None = None,
) -> tuple[RunResult, ...]:
    """Run one atom, or a checks track atom by atom until one fails.

    Output goes to the terminal, or line by line to `on_output` when one is given.
    """
    custom = bindings.custom_atom(name)
    if custom is not None:
        return (_run_atom(custom, bindings, args, on_output),)
    track = standard.track(name)
    if track is not None:
        return _run_track(track, standard, bindings, args, on_output)
    try:
        atom = standard.atom(name)
    except UnknownAtomError as exc:
        names = ", ".join(c.name for c in bindings.custom) or "none"
        tracks = ", ".join(t.name for t in standard.tracks)
        raise UnknownAtomError(f"{exc}; tracks: {tracks}; custom atoms here: {names}", details=exc.details) from exc
    return (_run_atom(atom, bindings, args, on_output),)


__all__ = [
    "Execution",
    "OnOutput",
    "Outcome",
    "RunResult",
    "execute",
    "execute_captured",
    "resolve",
    "run",
    "track_atoms",
    "with_args",
]
