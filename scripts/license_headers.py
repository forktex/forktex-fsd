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


"""Every source file opens with the licence header: `check` lists those that do not, `fix` adds it."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER_LINES = [
    "Copyright (C) 2026 FORKTEX S.R.L.",
    "",
    "SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ForkTex-Commercial",
    "",
    "This file is part of ForkTex FSD.",
    "",
    "For commercial licensing -- including use in proprietary products, SaaS",
    "deployments, or any context where AGPL obligations cannot be met -- you",
    "MUST obtain a commercial license from FORKTEX S.R.L. (info@forktex.com).",
    "",
    "This program is free software: you can redistribute it and/or modify",
    "it under the terms of the GNU Affero General Public License as published by",
    "the Free Software Foundation, either version 3 of the License, or",
    "(at your option) any later version.",
    "",
    "This program is distributed in the hope that it will be useful,",
    "but WITHOUT ANY WARRANTY; without even the implied warranty of",
    "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the",
    "GNU Affero General Public License for more details.",
    "",
    "You should have received a copy of the GNU Affero General Public License",
    "along with this program. If not, see <https://www.gnu.org/licenses/>.",
]
HEADER = "\n".join(f"# {line}".rstrip() for line in HEADER_LINES) + "\n"
SUFFIXES = {".py", ".toml", ".yml", ".yaml", ".sh"}
SKIP = {".git", ".venv", ".pytest_cache", ".ruff_cache", ".import_linter_cache", "__pycache__", "build", "dist"}


def sources() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.suffix in SUFFIXES and path.is_file() and not SKIP & set(path.relative_to(ROOT).parts)
    )


def _split_shebang(text: str) -> tuple[str, str]:
    if text.startswith("#!"):
        first, _, rest = text.partition("\n")
        return first + "\n", rest
    return "", text


def has_header(text: str) -> bool:
    return _split_shebang(text)[1].startswith(HEADER)


def with_header(text: str) -> str:
    shebang, rest = _split_shebang(text)
    return f"{shebang}{HEADER}\n{rest.lstrip(chr(10))}"


def main(argv: list[str]) -> int:
    if argv not in (["check"], ["fix"]):
        print("usage: license_headers.py check|fix", file=sys.stderr)
        return 2
    missing = [path for path in sources() if not has_header(path.read_text(encoding="utf-8"))]
    if argv == ["fix"]:
        for path in missing:
            path.write_text(with_header(path.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"added the licence header to {len(missing)} file(s)")
        return 0
    for path in missing:
        print(f"missing licence header: {path.relative_to(ROOT)}", file=sys.stderr)
    print(f"{len(sources()) - len(missing)} of {len(sources())} source files carry the licence header")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
