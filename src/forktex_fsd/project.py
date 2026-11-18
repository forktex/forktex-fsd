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


"""`Project`: a repository and the standard it is held to — the one entry point."""

from __future__ import annotations

from pathlib import Path

from forktex.types import BaseValueObject

from forktex_fsd.binding import Binding, Bindings, CustomAtom, find_root, read_bindings
from forktex_fsd.check import Compliance, check
from forktex_fsd.report import Report, build_report
from forktex_fsd.run import OnOutput, Outcome, RunResult, run
from forktex_fsd.standard import Profile, Standard


class Project(BaseValueObject):
    """A repository bound to the standard in its `fsd.toml`."""

    standard: Standard
    bindings: Bindings

    @classmethod
    def find(cls, start: Path | str | None = None) -> Project:
        """The project whose `fsd.toml` is in `start` (default: the working directory) or the nearest one above it."""
        return cls.load(find_root(Path(start or Path.cwd()).resolve()))

    @classmethod
    def load(cls, root: Path | str) -> Project:
        """The project whose `fsd.toml` is exactly in `root`, held to the standard this version ships."""
        standard = Standard.load()
        return cls(standard=standard, bindings=read_bindings(Path(root).resolve(), standard))

    @property
    def root(self) -> Path:
        return self.bindings.root

    @property
    def profile(self) -> Profile:
        return self.bindings.profile

    @property
    def custom(self) -> tuple[CustomAtom, ...]:
        return self.bindings.custom

    def binding(self, atom: str) -> Binding | None:
        return self.bindings.binding(atom)

    def check(self) -> Compliance:
        """Compliance per track. Executes nothing, so it is safe on a repository you do not trust."""
        return check(self.standard, self.bindings)

    def run(self, name: str, *args: str, on_output: OnOutput | None = None) -> tuple[RunResult, ...]:
        """Run one atom with `args`, or a checks track atom by atom until one fails.

        A track runs only when it is compliant; otherwise its one result is a
        failure naming its gaps. Output goes to the terminal, or line by line
        to `on_output`.
        """
        track = self.standard.track(name)
        if track is not None and track.checks and not args:
            compliance = next(t for t in self.check().tracks if t.track == name)
            if not compliance.compliant:
                gaps = ", ".join(a.atom for a in compliance.failures)
                return (RunResult(atom=name, outcome=Outcome.FAILED, detail=f"not compliant — {gaps}"),)
        return run(self.standard, self.bindings, name, args, on_output)

    def report(self, *, on_output: OnOutput | None = None) -> Report:
        """Run every routine atom without stopping, and keep the evidence."""
        return build_report(self.standard, self.bindings, on_output=on_output)


__all__ = ["Project"]
