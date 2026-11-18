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

from enum import StrEnum

from forktex.types import BaseValueObject

from forktex_fsd import Atom, AtomCompliance, Compliance, CustomAtom, Outcome, Profile, Report, RunResult, Standard
from forktex_fsd.report import duration_text, result_text

REPORT_JSON = "fsd-report.json"
REPORT_MARKDOWN = "fsd-report.md"
BINDING_WIDTH = 64
USAGE_HINT = "fsd <atom> [args]   fsd <track>   fsd report   fsd help [name]"


class Colour(StrEnum):
    """An ANSI colour, by its SGR code."""

    RED = "31"
    GREEN = "32"
    YELLOW = "33"
    DIM = "2"
    BOLD = "1"


class Box(BaseValueObject):
    """The characters a box is drawn with."""

    top_left: str
    top_right: str
    bottom_left: str
    bottom_right: str
    left_tee: str
    right_tee: str
    horizontal: str
    vertical: str
    dash: str
    ellipsis: str
    dot: str


UNICODE_BOX = Box(
    top_left="┌",
    top_right="┐",
    bottom_left="└",
    bottom_right="┘",
    left_tee="├",
    right_tee="┤",
    horizontal="─",
    vertical="│",
    dash="—",
    ellipsis="…",
    dot="·",
)
ASCII_BOX = Box(
    top_left="+",
    top_right="+",
    bottom_left="+",
    bottom_right="+",
    left_tee="+",
    right_tee="+",
    horizontal="-",
    vertical="|",
    dash="-",
    ellipsis="...",
    dot="-",
)


class Style(BaseValueObject):
    """How output is drawn: with or without colour, with box-drawing characters or plain ASCII."""

    colour: bool = False
    unicode: bool = True

    @property
    def box(self) -> Box:
        return UNICODE_BOX if self.unicode else ASCII_BOX

    def paint(self, text: str, colour: Colour) -> str:
        return f"\033[{colour}m{text}\033[0m" if self.colour else text


PLAIN = Style()


class Cell(BaseValueObject):
    """One table cell, and the colour it is painted in."""

    text: str
    colour: Colour | None = None


class Align(StrEnum):
    """Where a column's text sits: prose to the left, categories centred, numbers to the right."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class Column(BaseValueObject):
    """A column: its heading, and how its heading and cells are aligned."""

    title: str
    align: Align = Align.LEFT


GAP = "   "


def _place(text: str, width: int, align: Align) -> tuple[str, str]:
    room = width - len(text)
    match align:
        case Align.RIGHT:
            return " " * room, ""
        case Align.CENTER:
            return " " * (room // 2), " " * (room - room // 2)
        case _:
            return "", " " * room


type Section = tuple[str, list[list[Cell]]]


def boxed(title: str, verdict: Cell, header: list[Column], sections: list[Section], style: Style) -> list[str]:
    """A titled box: a header row, then one band per section; as wide as its content."""
    rows = [row for _, section in sections for row in section]
    texts = zip([c.title for c in header], *([c.text for c in row] for row in rows), strict=True)
    widths = [max(len(cell) for cell in column) for column in texts]
    content = sum(widths) + len(GAP) * (len(widths) - 1)
    inner = max(content, len(title) + len(verdict.text) + 4, *(len(name) + 3 for name, _ in sections))
    box = style.box

    def line(cells: list[Cell]) -> str:
        placed = []
        for cell, width, column in zip(cells, widths, header, strict=True):
            before, after = _place(cell.text, width, column.align)
            # Only the text is painted, so escape codes never count towards a width.
            text = style.paint(cell.text, cell.colour) if cell.colour else cell.text
            placed.append(f"{before}{text}{after}")
        return f"{box.vertical} {GAP.join(placed)}{' ' * (inner - content)} {box.vertical}"

    rule = box.horizontal
    fill = inner - len(title) - len(verdict.text) - 4
    verdict_text = style.paint(verdict.text, verdict.colour or Colour.BOLD)
    out = [f"{box.top_left}{rule} {style.paint(title, Colour.BOLD)} {rule * fill} {verdict_text} {rule}{box.top_right}"]
    out.append(line([Cell(text=column.title, colour=Colour.DIM) for column in header]))
    for name, section in sections:
        out.append(f"{box.left_tee}{rule} {name} {rule * (inner - len(name) - 1)}{box.right_tee}")
        out += [line(row) for row in section]
    out.append(f"{box.bottom_left}{rule * (inner + 2)}{box.bottom_right}")
    return out


def _shorten(text: str, style: Style) -> str:
    ellipsis = style.box.ellipsis
    return text if len(text) <= BINDING_WIDTH else text[: BINDING_WIDTH - len(ellipsis)] + ellipsis


def _mark(result: AtomCompliance) -> Cell:
    if result.is_failure:
        return Cell(text="FAIL", colour=Colour.RED)
    if result.is_warning:
        return Cell(text="warn", colour=Colour.YELLOW)
    return Cell(text="ok", colour=Colour.GREEN)


def _verdict(passed: bool, yes: str, no: str) -> Cell:
    return Cell(text=yes, colour=Colour.GREEN) if passed else Cell(text=no, colour=Colour.RED)


def _project_row(a: AtomCompliance, style: Style) -> list[Cell]:
    dash = style.box.dash
    return [
        _mark(a),
        Cell(text=a.atom),
        Cell(text="custom" if a.custom else "standard"),
        Cell(text=a.strength.value if a.strength else dash),
        Cell(text=a.status.value),
        Cell(text=_shorten(a.detail, style) if a.detail else dash),
    ]


def render_project(report: Compliance, name: str, style: Style = PLAIN) -> str:
    sections = [(track.track, [_project_row(a, style) for a in track.atoms]) for track in report.tracks]
    dot = style.box.dot
    title = f"{name} {dot} {report.profile} {dot} FSD {report.standard}"
    verdict = _verdict(report.compliant, "compliant", "not compliant")
    header = [
        Column(title="", align=Align.CENTER),
        Column(title="atom"),
        Column(title="kind", align=Align.CENTER),
        Column(title="strength", align=Align.CENTER),
        Column(title="status", align=Align.CENTER),
        Column(title="binding"),
    ]
    box = boxed(title, verdict, header, sections, style)
    return "\n".join([*box, style.paint(USAGE_HINT, Colour.DIM)])


_OUTCOME_COLOURS = {Outcome.PASSED: Colour.GREEN, Outcome.FAILED: Colour.RED, Outcome.SKIPPED: Colour.YELLOW}


def render_report(run: Report, style: Style = PLAIN) -> str:
    dash, dot = style.box.dash, style.box.dot
    sections: dict[str, list[list[Cell]]] = {}
    for e in run.evidence:
        sections.setdefault(e.track, []).append(
            [
                Cell(text=e.outcome.value, colour=_OUTCOME_COLOURS[e.outcome]),
                Cell(text=e.atom),
                Cell(text="custom" if e.custom else "standard"),
                Cell(text=duration_text(e) or dash),
                Cell(text=_shorten(result_text(e), style) if result_text(e) else dash),
            ]
        )
    title = f"{run.project} {dot} report {dot} {run.generated_at:%Y-%m-%d %H:%M:%S} UTC"
    verdict = _verdict(run.passed, "passed", "failed")
    header = [
        Column(title="outcome", align=Align.CENTER),
        Column(title="atom"),
        Column(title="kind", align=Align.CENTER),
        Column(title="time", align=Align.RIGHT),
        Column(title="result"),
    ]
    return "\n".join(boxed(title, verdict, header, list(sections.items()), style))


def _usage(standard: Standard, style: Style) -> list[str]:
    return [
        f"fsd {style.box.dash} the ForkTex Standard of Delivery {standard.version}",
        "",
        "usage:",
        "  fsd [-C DIR]                   this repository: its atoms, bindings and compliance",
        "  fsd [-C DIR] <atom> [args...]  run an atom; arguments go to its command",
        "  fsd [-C DIR] run <atom> [args...]",
        "  fsd [-C DIR] <track>           run a checks track: its compliance, then every atom",
        f"  fsd [-C DIR] report            every routine atom, with evidence: {REPORT_JSON}, {REPORT_MARKDOWN}",
        "  fsd help [name] [--json]       this help, one track, or one atom's full contract",
        "",
    ]


def render_help(standard: Standard, style: Style = PLAIN, only: str | None = None) -> str:
    """The whole standard with the usage, or one track of it with its summary."""
    profiles = list(Profile)
    shown = [t for t in standard.tracks if only in (None, t.name)]
    sections = [
        (
            f"{track.name} {style.box.dot} fsd {track.name}" if track.checks else track.name,
            [
                [
                    Cell(text=a.name),
                    Cell(text=a.effect.value),
                    *(Cell(text=a.strength_for(p).value) for p in profiles),
                    Cell(text=_shorten(a.contract, style)),
                ]
                for a in standard.in_track(track.name)
            ],
        )
        for track in shown
    ]
    header = [
        Column(title="atom"),
        Column(title="effect", align=Align.CENTER),
        *(Column(title=p.value, align=Align.CENTER) for p in profiles),
        Column(title="contract"),
    ]
    box = boxed("the standard", Cell(text=standard.version), header, sections, style)
    if only is not None:
        return "\n".join([shown[0].summary, "", *box])
    return "\n".join([*_usage(standard, style), *box])


def render_atom(atom: Atom, bound: str | None, style: Style = PLAIN) -> str:
    """One atom's full contract, and what it is bound to here when there is a project."""
    strengths = ", ".join(f"{p.value} {atom.strength_for(p).value}" for p in Profile)
    lines = [
        f"{atom.name} {style.box.dash} {atom.track}",
        "",
        atom.contract,
        "",
        f"effect     {atom.effect.value}",
        f"evidence   {atom.evidence.value}",
        f"strength   {strengths}",
    ]
    if bound is not None:
        lines.append(f"bound here {bound or style.box.dash}")
    return "\n".join(lines)


def render_custom(custom: CustomAtom, style: Style = PLAIN) -> str:
    """A custom atom: the repository's own, so its command is all there is to say."""
    return "\n".join(
        [
            f"{custom.name} {style.box.dash} {custom.track} (custom atom of this repository)",
            "",
            f"bound here {' ; '.join(custom.command.steps)}",
        ]
    )


def render_result(result: RunResult) -> str:
    detail = f" ({result.detail})" if result.detail else ""
    return f"fsd: {result.atom} {result.outcome.value}{detail}"


__all__ = [
    "REPORT_JSON",
    "REPORT_MARKDOWN",
    "Style",
    "render_atom",
    "render_custom",
    "render_help",
    "render_project",
    "render_report",
    "render_result",
]
