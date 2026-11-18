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


"""The built wheel, installed on each Linux userland a consumer runs, passes every consumer scenario there.

macOS and Windows cannot run in a container on a Linux host; the CI workflow runs the suite on
them natively.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from _containers import LINUX, WORK, start_linux
from testcontainers.core.container import DockerContainer

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("dist")
    subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(out), str(ROOT)], check=True)
    [built] = out.glob("forktex_fsd-*.whl")
    return built


@pytest.fixture(scope="session", params=sorted(LINUX))
def linux(request: pytest.FixtureRequest, wheel: Path) -> Iterator[tuple[str, DockerContainer]]:
    image, _ = LINUX[request.param]
    container = start_linux(image, wheel, ROOT)
    try:
        yield request.param, container
    finally:
        container.stop()


def run(container: DockerContainer, *argv: str) -> tuple[int, str]:
    code, output = container.exec(list(argv))
    return code, output.decode(errors="replace")


def test_the_shell_is_the_distributions_own(linux):
    name, container = linux
    assert run(container, "readlink", "-f", "/bin/sh") == (0, LINUX[name][1] + "\n")


def test_every_consumer_scenario_passes(linux):
    _, container = linux
    code, output = run(
        container, "python", "-m", "pytest", f"{WORK}/tests/usage", "--rootdir", WORK, "-q", "-p", "no:cacheprovider"
    )
    assert code == 0, output


def test_the_installed_command_reads_a_project(linux):
    _, container = linux
    code, output = run(container, "sh", "-c", "fsd help test && fsd -C /tmp help")
    assert code == 0, output
    assert output.startswith("test — assurance")
