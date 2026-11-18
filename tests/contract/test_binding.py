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

"""`fsd.toml`: every way a binding can be written, and every way it can be wrong."""

from __future__ import annotations

from pathlib import Path


import pytest

from forktex_fsd import (
    Binding,
    ProjectNotFoundError,
    BindingError,
    CustomAtom,
    Command,
    FileBinding,
    NotApplicable,
    Profile,
    Standard,
)
from forktex_fsd.binding import find_root, parse_bindings, read_bindings


def parse(standard: Standard, body: str, head: str = 'standard = "1.0"\nprofile = "library"\n'):
    return parse_bindings(head + body, Path("."), standard)


def test_the_four_binding_forms(standard: Standard):
    project = parse(
        standard,
        """
[assurance]
format = "fmt --check"
test = ["runner -q", "report --total"]
[delivery]
publish = { na = "an internal tool, never published" }
[documentation]
manual = { file = "README.md" }
""",
    )
    assert project.profile is Profile.LIBRARY
    assert project.binding("format") == Command(steps=("fmt --check",))
    assert project.binding("test") == Command(steps=("runner -q", "report --total"))
    assert project.binding("publish") == NotApplicable(na="an internal tool, never published")
    assert project.binding("manual") == FileBinding(file=("README.md",))
    assert project.binding("lint") is None


def test_an_unknown_name_under_a_track_is_a_custom_atom_of_that_track(standard: Standard):
    project = parse(
        standard, '[operation]\nmigrate = ["alembic upgrade head", "seed"]\n[assurance]\ncontracts = "schemathesis"\n'
    )
    migrate = project.custom_atom("migrate")
    assert migrate == CustomAtom(
        name="migrate", track="operation", command=Command(steps=("alembic upgrade head", "seed"))
    )
    assert [c.name for c in project.custom_in(("assurance", "security"))] == ["contracts"]
    assert project.custom_atom("test") is None
    assert project.binding("migrate") is None


def test_a_file_atom_may_be_declared_not_applicable(standard: Standard):
    project = parse(standard, '[documentation]\nmanual = { na = "generated elsewhere" }\n')
    assert project.binding("manual") == NotApplicable(na="generated elsewhere")


def test_a_file_binding_may_name_several_files(standard: Standard):
    project = parse(standard, '[documentation]\nmanual = { file = ["README.md", "AGENTS.md"] }\n')
    assert project.binding("manual") == FileBinding(file=("README.md", "AGENTS.md"))


@pytest.mark.parametrize(
    ("body", "details"),
    [
        ("[assurance\n", {"key": "toml"}),
        ("[quality]\nlint = 'x'\n", {"section": "quality"}),
        ("assurance = 'x'\n", {"section": "assurance"}),
        ("[assurance]\ngate = { na = 'not needed' }\n", {"atom": "gate", "expected": "command"}),
        ("[assurance]\ngate = { file = 'x' }\n", {"atom": "gate", "expected": "command"}),
        ("[assurance]\naudit = 'scan'\n", {"atom": "audit", "section": "assurance", "expected": "security"}),
        ("[operation]\nassurance = 'x'\n", {"atom": "assurance"}),
        ("[delivery]\ndelivery = 'x'\n", {"atom": "delivery"}),
        ("[assurance]\ntest = ''\n", {"atom": "test"}),
        ("[assurance]\ntest = '   '\n", {"atom": "test"}),
        ("[assurance]\ntest = []\n", {"atom": "test"}),
        ("[assurance]\ntest = ['a', 1]\n", {"atom": "test"}),
        ("[assurance]\ntest = { steps = ['x'], extra = 1 }\n", {"atom": "test"}),
        ("[assurance]\ntest = { steps = ['x'] }\n", {"atom": "test"}),
        ("[assurance]\ntest = { run = 'x', results = ['../out.xml'] }\n", {"atom": "test"}),
        ("[assurance]\ntest = { file = 'x' }\n", {"atom": "test", "expected": "command"}),
        ("[documentation]\nmanual = 'cat README.md'\n", {"atom": "manual", "expected": "file"}),
        ("[delivery]\npublish = { na = '' }\n", {"atom": "publish"}),
        ("[documentation]\nmanual = { file = '' }\n", {"atom": "manual"}),
        ("[documentation]\nmanual = { file = [] }\n", {"atom": "manual"}),
        ("[documentation]\nmanual = { file = 'README.md', na = 'both' }\n", {"atom": "manual"}),
        ("[documentation]\nmanual = { file = 'README.md', fiel = 'typo' }\n", {"atom": "manual"}),
        ("[documentation]\nmanual = { file = '/etc/hostname' }\n", {"atom": "manual"}),
        ("[documentation]\nmanual = { file = ['README.md', '../../etc/passwd'] }\n", {"atom": "manual"}),
        ("[documentation]\nmanual = { file = 'C:/Windows/win.ini' }\n", {"atom": "manual"}),
        ("[documentation]\nmanual = { file = '\\\\server\\share\\x' }\n", {"atom": "manual"}),
        ("[operation]\nrun = 'x'\n", {"atom": "run"}),
        ("[assurance]\nhelp = 'x'\n", {"atom": "help"}),
        ("[operation]\nseed = 'a'\n[assurance]\nseed = 'b'\n", {"atom": "seed", "section": "assurance"}),
        ("[operation]\n'-h' = 'x'\n", {"atom": "-h"}),
        ("[operation]\n'' = 'x'\n", {"atom": ""}),
        ("[delivery]\npublish = { na = '     ' }\n", {"atom": "publish"}),
    ],
)
def test_an_invalid_binding_is_refused_naming_where(standard: Standard, body: str, details: dict[str, str]):
    with pytest.raises(BindingError) as refused:
        parse(standard, body)
    assert details.items() <= refused.value.details.items()


@pytest.mark.parametrize(
    ("head", "details"),
    [
        ('profile = "library"\n', {"key": "header"}),
        ('standard = "0.2"\nprofile = "library"\n', {"key": "standard", "found": "0.2", "expected": "1.0"}),
        ('standard = "1.1"\nprofile = "library"\n', {"key": "standard", "found": "1.1", "expected": "1.0"}),
        ('standard = "2.0"\nprofile = "library"\n', {"key": "standard", "found": "2.0", "expected": "1.0"}),
        ('standard = "1.x"\nprofile = "library"\n', {"key": "standard", "found": "1.x", "expected": "1.0"}),
        ('standard = "1.0"\n', {"key": "header"}),
        ('standard = "1.0"\nprofile = "app"\n', {"key": "header"}),
    ],
)
def test_the_header_is_required_and_checked(standard: Standard, head: str, details: dict[str, str]):
    with pytest.raises(BindingError) as refused:
        parse(standard, "", head=head)
    assert refused.value.details == details


def test_a_path_inside_the_repository_is_accepted(standard: Standard):
    project = parse(standard, '[documentation]\nmanual = { file = ["docs/guide.md", "./README.md"] }\n')
    assert project.binding("manual") == FileBinding(file=("docs/guide.md", "./README.md"))


def test_read_bindings_reads_the_file(tmp_path: Path, standard: Standard):
    (tmp_path / "fsd.toml").write_text('standard = "1.0"\nprofile = "service"\n', encoding="utf-8")
    project = read_bindings(tmp_path, standard)
    assert project.profile is Profile.SERVICE
    assert project.root == tmp_path


def test_read_bindings_without_a_file_says_where_it_looked(tmp_path: Path, standard: Standard):
    with pytest.raises(ProjectNotFoundError) as missing:
        read_bindings(tmp_path, standard)
    assert missing.value.details == {"root": str(tmp_path)}


def test_find_root_finds_the_nearest_fsd_toml_above(tmp_path: Path):
    (tmp_path / "fsd.toml").write_text("", encoding="utf-8")
    deep = tmp_path / "src" / "pkg"
    deep.mkdir(parents=True)
    assert find_root(deep) == tmp_path
    assert find_root(tmp_path) == tmp_path


def test_find_root_without_a_project_says_where_it_looked(tmp_path: Path):
    with pytest.raises(ProjectNotFoundError) as missing:
        find_root(tmp_path)
    assert missing.value.details == {"start": str(tmp_path)}


def test_a_file_written_for_an_earlier_minor_of_the_same_major_is_read(standard: Standard):
    assert parse(standard, "", head='standard = "1.0"\nprofile = "library"\n').profile is Profile.LIBRARY


def test_a_file_that_is_not_utf8_is_refused(tmp_path: Path, standard: Standard):
    (tmp_path / "fsd.toml").write_bytes(b'standard = "1.0"\n# \xff\n')
    with pytest.raises(BindingError) as refused:
        read_bindings(tmp_path, standard)
    assert refused.value.details == {"key": "encoding"}


def test_every_binding_is_a_binding():
    for binding in (Command(steps=("x",)), FileBinding(file=("x",)), NotApplicable(na="why not")):
        assert isinstance(binding, Binding)


def test_results_may_be_one_path_or_several(standard: Standard):
    project = parse(standard, '[assurance]\ntest = { run = "pytest", results = "build/junit.xml" }\n')
    assert project.binding("test") == Command(steps=("pytest",), results=("build/junit.xml",))


def test_a_byte_order_mark_is_read_past(tmp_path: Path, standard: Standard):
    (tmp_path / "fsd.toml").write_bytes('\ufeffstandard = "1.0"\nprofile = "service"\n'.encode())
    assert read_bindings(tmp_path, standard).profile is Profile.SERVICE
