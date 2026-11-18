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

"""Install the built wheel into a throwaway environment and use it as a consumer would.

The only check that exercises the packaged artifact: the standard must ship inside
the wheel, and the installed `fsd` script must check this repository.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def executables(env: Path) -> Path:
    return env / ("Scripts" if sys.platform == "win32" else "bin")


def main() -> int:
    wheels = list((ROOT / "dist").glob("forktex_fsd-*-py3-none-any.whl"))
    if len(wheels) != 1:
        print(f"smoke: expected one wheel in dist/, found {len(wheels)} — run `fsd build`", file=sys.stderr)
        return 1
    wheel = wheels[0]
    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / "env"
        venv.create(env, with_pip=True)
        bin_dir = executables(env)
        python, fsd = bin_dir / "python", bin_dir / "fsd"
        subprocess.run([python, "-m", "pip", "install", "-q", str(wheel)], check=True)
        subprocess.run(
            [python, "-c", f"from forktex_fsd import Project; assert Project.find({str(ROOT)!r}).check().tracks"],
            check=True,
        )
        subprocess.run([fsd, "help"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([fsd, "-C", str(ROOT), "manual"], check=True, stderr=subprocess.DEVNULL)
    print(f"smoke: {wheel.name} installs, ships its standard, and its fsd script reads this repository")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
