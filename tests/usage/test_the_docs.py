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


"""Every example the documentation ships is one this version accepts."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from forktex_fsd import Profile, Project, Standard

ROOT = Path(__file__).resolve().parents[2]
PAGES = ("README.md", "docs/guide.md", "docs/reference.md")
FENCE = re.compile(r"```(\w+)\n(.*?)```", re.S)


def blocks(language: str) -> list[tuple[str, str]]:
    return [
        (f"{page}#{index}", body)
        for page in PAGES
        for index, (lang, body) in enumerate(FENCE.findall((ROOT / page).read_text(encoding="utf-8")))
        if lang == language
    ]


WHOLE_FILES = [(where, body) for where, body in blocks("toml") if body.startswith("# fsd.toml")]
FRAGMENTS = [(where, body) for where, body in blocks("toml") if not body.startswith("# fsd.toml")]
PYTHON_FILES = [(where, body) for where, body in blocks("python") if body.split("\n", 1)[0].endswith(".py")]


def test_the_documentation_has_whole_files_and_fragments():
    assert len(WHOLE_FILES) >= 4 and len(FRAGMENTS) >= 4 and len(PYTHON_FILES) >= 2


def load(root: Path, text: str) -> Project:
    (root / "fsd.toml").write_text(text, encoding="utf-8")
    return Project.load(root)


@pytest.mark.parametrize(("where", "body"), WHOLE_FILES, ids=[w for w, _ in WHOLE_FILES])
def test_every_whole_fsd_toml_is_accepted(where: str, body: str, tmp_path: Path):
    assert load(tmp_path, body).check().tracks


@pytest.mark.parametrize(("where", "body"), FRAGMENTS, ids=[w for w, _ in FRAGMENTS])
def test_every_fragment_is_accepted_under_a_header(where: str, body: str, tmp_path: Path):
    assert load(tmp_path, f'standard = "1.0"\nprofile = "service"\n{body}').check().tracks


@pytest.mark.parametrize(("where", "body"), PYTHON_FILES, ids=[w for w, _ in PYTHON_FILES])
def test_every_python_example_compiles(where: str, body: str):
    compile(body, where, "exec")


def test_the_guides_compliance_script_reads_a_workspace(tmp_path, capsys):
    [script] = [body for _, body in PYTHON_FILES if body.startswith("# compliance.py")]
    (tmp_path / "plain").mkdir()
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "fsd.toml").write_text('standard = "1.0"\nprofile = "library"\n', encoding="utf-8")
    namespace: dict[str, object] = {"__name__": "compliance"}
    exec(compile(script, "compliance.py", "exec"), namespace)

    assert namespace["main"](tmp_path) == 1  # type: ignore[operator]
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split()[:2] == ["lib", "library"]
    assert lines[1].split() == ["plain", "no", "fsd.toml"]


def test_the_readmes_atom_table_is_the_standard():
    standard = Standard.load()
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    start = text.index("| Track | Atom |")
    table = text[start : text.index("\n\n", start)].splitlines()[2:]
    rows = []
    track = ""
    for line in table:
        cells = [c.strip() for c in line.strip("|").split("|")]
        track = cells[0].strip("* ✓") or track
        rows.append((track, cells[1].strip("`"), cells[3], tuple(cells[4:7])))
    checks = {t.name for t in standard.tracks if t.checks}
    marked = {line.split("|")[1].strip("* ✓") for line in table if "✓" in line}
    assert marked == checks
    assert rows == [
        (a.track, a.name, a.effect.value, tuple(a.strength_for(p).value for p in Profile)) for a in standard.atoms
    ]
