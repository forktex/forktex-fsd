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

"""The report: compliance, then evidence from every routine atom, kept as data.

Unlike a track run, a report does not stop at the first failure — it is the whole
picture. It runs every checks track whole, with its custom atoms, and the
read-only and local atoms of the other tracks in standard order except `clean`,
which would erase what `build` just made. A service's start, status and stop run
as one bracket, so that status is read while the service is up. Custom atoms of
the other tracks are left out: they may rewrite files, and a report must not.
"""

from __future__ import annotations

import time

from forktex.iso import now, to_iso
from forktex.types import BaseValueObject, BaseWireValueObject, UtcDateTime
from pydantic import computed_field

from forktex_fsd.binding import Bindings, Command, CustomAtom
from forktex_fsd.check import Compliance, check
from forktex_fsd.results import ResultFile, read_result
from forktex_fsd.run import OnOutput, Outcome, execute_captured, resolve, track_atoms, with_args
from forktex_fsd.standard import Atom, Standard, Strength

_SKIPPED_BY_REPORT = frozenset({"clean"})
_START, _STATUS, _STOP = "start", "status", "stop"


class Bracket(BaseValueObject):
    """A service's start, status and stop, run as one so that status is read while it is up."""


class AtomEvidence(BaseWireValueObject):
    """What running one atom left behind: its outcome, timing, output and results."""

    atom: str
    track: str
    custom: bool = False
    outcome: Outcome
    detail: str = ""
    steps: tuple[str, ...] = ()
    exit_code: int | None = None
    started_at: UtcDateTime | None = None
    duration_seconds: float | None = None
    output_tail: tuple[str, ...] = ()
    results: tuple[ResultFile, ...] = ()


def result_text(evidence: AtomEvidence) -> str:
    return "; ".join(r.summary or r.path for r in evidence.results) or evidence.detail


def duration_text(evidence: AtomEvidence) -> str:
    return "" if evidence.duration_seconds is None else f"{evidence.duration_seconds:.1f}s"


class Report(BaseWireValueObject):
    """Compliance and the evidence of every routine atom, for one repository at one moment."""

    project: str
    generated_at: UtcDateTime
    compliance: Compliance
    evidence: tuple[AtomEvidence, ...]

    @computed_field
    @property
    def passed(self) -> bool:
        return self.compliance.compliant and all(e.outcome is not Outcome.FAILED for e in self.evidence)

    def to_markdown(self) -> str:
        """The report as a Markdown page, with the output of every failing atom."""
        return _markdown(self)


def _executed(
    name: str, track: str, command: Command, bindings: Bindings, on_output: OnOutput | None, *, custom: bool = False
) -> AtomEvidence:
    started, clock = now(), time.monotonic()
    steps = with_args(command.steps, ())
    execution = execute_captured(steps, bindings.root, on_output)
    return AtomEvidence(
        atom=name,
        track=track,
        custom=custom,
        outcome=Outcome.PASSED if execution.passed else Outcome.FAILED,
        detail="" if execution.passed else execution.describe(),
        steps=steps,
        exit_code=execution.code,
        started_at=started,
        duration_seconds=round(time.monotonic() - clock, 3),
        output_tail=execution.output,
        results=tuple(read_result(bindings.root, path) for path in command.results),
    )


def _evidence(atom: Atom | CustomAtom, bindings: Bindings, on_output: OnOutput | None) -> AtomEvidence:
    if isinstance(atom, CustomAtom):
        return _executed(atom.name, atom.track, atom.command, bindings, on_output, custom=True)
    settled = resolve(atom, bindings)
    if isinstance(settled, Command):
        return _executed(atom.name, atom.track, settled, bindings, on_output)
    return AtomEvidence(atom=atom.name, track=atom.track, outcome=settled.outcome, detail=settled.detail)


def _bracket(standard: Standard, bindings: Bindings, on_output: OnOutput | None) -> list[AtomEvidence]:
    started = _evidence(standard.atom(_START), bindings, on_output)
    if started.exit_code is None:
        return [started]
    evidence = [started]
    try:
        if started.outcome is Outcome.PASSED:
            evidence.append(_evidence(standard.atom(_STATUS), bindings, on_output))
    finally:
        # Whatever `start` brought up, even partly, `stop` tears down, whatever happened in between.
        evidence.append(_evidence(standard.atom(_STOP), bindings, on_output))
    return evidence


def _acting_track(standard: Standard, bindings: Bindings, track: str) -> list[Atom | Bracket]:
    serviced = standard.atom(_START).strength_for(bindings.profile) is not Strength.NOT_APPLICABLE
    steps: list[Atom | Bracket] = []
    for atom in standard.in_track(track):
        if atom.name == _START and serviced:
            steps.append(Bracket())
        elif atom.name not in (_START, _STATUS, _STOP, *_SKIPPED_BY_REPORT) and atom.effect.is_routine:
            steps.append(atom)
    return steps


def plan(standard: Standard, bindings: Bindings) -> tuple[Atom | CustomAtom | Bracket, ...]:
    """What a report runs, in order: every checks track whole, and the routine atoms of the others."""
    steps: list[Atom | CustomAtom | Bracket] = []
    for track in standard.tracks:
        if track.checks:
            steps += track_atoms(standard, bindings, track.name)
        else:
            steps += _acting_track(standard, bindings, track.name)
    return tuple(steps)


def build_report(standard: Standard, bindings: Bindings, *, on_output: OnOutput | None = None) -> Report:
    """Run every routine atom and gather the evidence; `on_output` receives the commands' output as it comes."""
    evidence: list[AtomEvidence] = []
    for step in plan(standard, bindings):
        if isinstance(step, Bracket):
            evidence += _bracket(standard, bindings, on_output)
        else:
            evidence.append(_evidence(step, bindings, on_output))
    return Report(
        project=bindings.root.name,
        generated_at=now(),
        compliance=check(standard, bindings),
        evidence=tuple(evidence),
    )


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _markdown(run: Report) -> str:
    verdict = "passed" if run.passed else "failed"
    lines = [
        f"# FSD report — {run.project}",
        "",
        f"FSD {run.compliance.standard} · profile {run.compliance.profile} · "
        f"generated {to_iso(run.generated_at)} · **{verdict}**",
        "",
        "## Compliance",
        "",
        "| Track | Compliant | Gaps |",
        "|---|---|---|",
    ]
    for track in run.compliance.tracks:
        gaps = ", ".join(a.atom for a in track.failures + track.warnings) or "—"
        lines.append(f"| {track.track} | {'yes' if track.compliant else '**no**'} | {gaps} |")
    lines += ["", "## Evidence", "", "| Track | Atom | Outcome | Duration | Result |", "|---|---|---|---|---|"]
    for e in run.evidence:
        name = f"{e.atom} (custom)" if e.custom else e.atom
        lines.append(
            f"| {e.track} | {name} | {e.outcome.value} | {duration_text(e) or '—'} | {_cell(result_text(e)) or '—'} |"
        )
    for e in run.evidence:
        if e.outcome is Outcome.FAILED and e.output_tail:
            lines += ["", f"### {e.atom} — {e.detail}", "", "```", *e.output_tail, "```"]
    return "\n".join(lines) + "\n"


__all__ = ["AtomEvidence", "Bracket", "Report", "build_report", "duration_text", "plan", "result_text"]
