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


"""FSD, the ForkTex Standard of Delivery: a software compliance standard and the library that checks it."""

from __future__ import annotations

import logging
from importlib.metadata import version as _distribution_version

from forktex_fsd.binding import Binding, Bindings, Command, CustomAtom, FileBinding, NotApplicable
from forktex_fsd.check import AtomCompliance, Compliance, Status, TrackCompliance
from forktex_fsd.errors import (
    BindingError,
    FsdError,
    InvalidStandardError,
    ProjectNotFoundError,
    UnknownAtomError,
    UsageError,
)
from forktex_fsd.project import Project
from forktex_fsd.report import AtomEvidence, Report
from forktex_fsd.results import Format, ResultFile
from forktex_fsd.run import Outcome, RunResult
from forktex_fsd.standard import Atom, Effect, EvidenceKind, Profile, Standard, Strength, Track

__version__ = _distribution_version("forktex-fsd")

logging.getLogger("forktex_fsd").addHandler(logging.NullHandler())

__all__ = [
    "Atom",
    "AtomCompliance",
    "AtomEvidence",
    "Binding",
    "BindingError",
    "Bindings",
    "Command",
    "Compliance",
    "CustomAtom",
    "Effect",
    "EvidenceKind",
    "FileBinding",
    "Format",
    "FsdError",
    "InvalidStandardError",
    "NotApplicable",
    "Outcome",
    "Profile",
    "Project",
    "ProjectNotFoundError",
    "Report",
    "ResultFile",
    "RunResult",
    "Standard",
    "Status",
    "Strength",
    "Track",
    "TrackCompliance",
    "UnknownAtomError",
    "UsageError",
    "__version__",
]
