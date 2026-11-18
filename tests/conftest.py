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

"""Shared fixtures: the shipped standard, and a repository written to a temp directory."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from forktex_fsd import Bindings, Standard
from forktex_fsd.binding import read_bindings


def shell(*argv: str) -> str:
    """One shell command line, quoted for the platform shell the runner will use."""
    return subprocess.list2cmdline(argv) if sys.platform == "win32" else shlex.join(argv)


def toml(value: str | list[str]) -> str:
    """A TOML value. JSON string escaping is valid TOML basic-string escaping."""
    return json.dumps(value)


#: Commands that pass and fail everywhere this package runs: the interpreter running the tests.
PASS = shell(sys.executable, "-c", "raise SystemExit(0)")
FAIL = shell(sys.executable, "-c", "raise SystemExit(3)")


def record(log: Path, name: str) -> str:
    """A command appending `name` to a log, so a test can see what ran and in what order."""
    return shell(sys.executable, "-c", f"open({str(log)!r}, 'a').write({name!r} + '\\n')")


def say(text: str) -> str:
    """A command printing one line."""
    return shell(sys.executable, "-c", f"print({text!r})")


def echo_args(out: Path) -> str:
    """A command writing the arguments it received, one per line."""
    return shell(sys.executable, "-c", f"import sys; open({str(out)!r}, 'w').write('\\n'.join(sys.argv[1:]))")


def write_files(root: Path, *names: str) -> None:
    for name in names:
        (root / name).write_text("hello", encoding="utf-8")


def write_project(root: Path, body: str = "", profile: str = "library") -> None:
    (root / "fsd.toml").write_text(f'standard = "1.0"\nprofile = "{profile}"\n{body}', encoding="utf-8")


@pytest.fixture(scope="session")
def standard() -> Standard:
    return Standard.load()


@pytest.fixture
def repo(tmp_path: Path, standard: Standard) -> Callable[..., Bindings]:
    """Write `fsd.toml` with the given body and load it."""

    def write(body: str, profile: str = "library") -> Bindings:
        write_project(tmp_path, body, profile)
        return read_bindings(tmp_path, standard)

    return write


#: The files LIBRARY_MUSTS binds `manual` to.
MANUAL_FILES = ("README.md", "AGENTS.md")

#: Every `must` of the library profile bound, so a test can remove exactly one.
LIBRARY_MUSTS = f"""
[operation]
setup = {toml(PASS)}

[assurance]
format = {toml(PASS)}
lint = {toml(PASS)}
test = {toml(PASS)}

[security]
audit = {toml(PASS)}

[delivery]
build = {toml(PASS)}
publish = {toml(PASS)}

[documentation]
manual = {{ file = ["README.md", "AGENTS.md"] }}
"""
