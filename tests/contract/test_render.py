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

"""Rendering: boxed tables whose every line is one width, colour only when asked for."""

from __future__ import annotations

from forktex_fsd._render import BINDING_WIDTH, Align, Cell, Colour, Column, Style, boxed, render_help, render_project
from forktex_fsd.check import check


def widths(lines: list[str]) -> set[int]:
    return {len(line) for line in lines}


def test_a_box_has_one_width_from_title_to_bottom():
    lines = boxed(
        "title",
        Cell(text="ok"),
        [Column(title="a"), Column(title="bb")],
        [("one", [[Cell(text="x"), Cell(text="yyyy")]]), ("a longer section name", [[Cell(text="z"), Cell(text="")]])],
        Style(),
    )
    assert len(widths(lines)) == 1
    assert lines[0].startswith("┌─ title ")
    assert lines[0].endswith(" ok ─┐")
    assert lines[2].startswith("├─ one ")
    assert lines[-1].startswith("└") and lines[-1].endswith("┘")


def test_ascii_box_for_terminals_without_box_drawing():
    lines = boxed("t", Cell(text="v"), [Column(title="h")], [("s", [[Cell(text="x")]])], Style(unicode=False))
    assert lines[0].startswith("+- t ")
    assert lines[1].startswith("| ")
    assert lines[-1] == "+" + "-" * (len(lines[-1]) - 2) + "+"


def test_paint_only_when_enabled():
    assert Style().paint("ok", Colour.GREEN) == "ok"
    assert Style(colour=True).paint("ok", Colour.GREEN) == "\033[32mok\033[0m"


def test_an_ascii_style_draws_nothing_but_ascii(repo, standard):
    ascii_only = Style(unicode=False)
    compliance = check(standard, repo(f'[assurance]\ntest = "{"x" * 200}"\n'))
    render_project(compliance, "demo", ascii_only).encode("ascii")
    render_help(standard, ascii_only).encode("ascii")


def test_colour_does_not_break_alignment(repo, standard):
    report = check(standard, repo('[assurance]\nvalidate = "pyright"\n'))
    coloured = render_project(report, "demo", Style(colour=True))
    plain = render_project(report, "demo", Style())
    assert "\033[31mFAIL" in coloured
    assert "\033[32mok" in coloured
    stripped = coloured
    for code in ("\033[31m", "\033[32m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"):
        stripped = stripped.replace(code, "")
    assert stripped == plain


def test_a_long_binding_is_shortened_to_the_column(repo, standard):
    report = check(standard, repo(f'[assurance]\ntest = "{"x" * 200}"\n'))
    row = next(r for r in render_project(report, "demo").splitlines() if " test " in r)
    assert ("x" * (BINDING_WIDTH - 1) + "…") in row


def test_each_column_is_aligned_its_own_way():
    header = [Column(title="name"), Column(title="state", align=Align.CENTER), Column(title="secs", align=Align.RIGHT)]
    rows = [
        [Cell(text="a"), Cell(text="ok"), Cell(text="1.5")],
        [Cell(text="bbbb"), Cell(text="fail"), Cell(text="12.5")],
    ]
    lines = boxed("t", Cell(text="v"), header, [("s", rows)], Style())
    assert lines[1] == "│ name   state   secs │"
    assert lines[3] == "│ a       ok      1.5 │"
    assert lines[4] == "│ bbbb   fail    12.5 │"


def test_colour_paints_the_text_not_the_padding():
    header = [Column(title="state", align=Align.CENTER)]
    lines = boxed("t", Cell(text="v"), header, [("s", [[Cell(text="ok", colour=Colour.GREEN)]])], Style(colour=True))
    assert "\033[32mok\033[0m" in lines[3]
