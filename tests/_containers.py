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


"""The one container factory: a pinned Linux userland with this repository's wheel installed."""

from __future__ import annotations

from pathlib import Path

from testcontainers.core.container import DockerContainer

#: The Linux userlands a consumer runs fsd on, and the `/bin/sh` each one brings.
LINUX = {
    "debian": ("python:3.14.6-slim-trixie", "/usr/bin/dash"),
    "alpine": ("python:3.14.6-alpine3.23", "/bin/busybox"),
}

WORK = "/work"


def start_linux(image: str, wheel: Path, root: Path) -> DockerContainer:
    """A running container with the wheel installed, and the tests and documentation mounted read-only at /work."""
    container = (
        DockerContainer(image)
        .with_command("sleep infinity")
        .with_env("PYTHONDONTWRITEBYTECODE", "1")
        .with_volume_mapping(str(wheel.parent), "/dist", "ro")
    )
    for name in ("tests", "docs", "README.md"):
        container = container.with_volume_mapping(str(root / name), f"{WORK}/{name}", "ro")
    container.start()
    code, output = container.exec(
        ["pip", "install", "-q", "--root-user-action=ignore", f"/dist/{wheel.name}", "pytest>=9.2"]
    )
    if code != 0:
        container.stop()
        raise RuntimeError(f"installing {wheel.name} on {image} failed:\n{output.decode(errors='replace')}")
    return container
