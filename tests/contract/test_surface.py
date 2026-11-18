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


"""The public surface is a contract: adding or removing a name is a deliberate change here."""

from __future__ import annotations

from forktex.error import AppError, AppErrorCode

import forktex_fsd

PUBLIC = {
    # the entry point
    "Project",
    # the standard
    "Atom",
    "Effect",
    "EvidenceKind",
    "Profile",
    "Standard",
    "Strength",
    "Track",
    # a repository's fsd.toml
    "Binding",
    "Bindings",
    "Command",
    "CustomAtom",
    "FileBinding",
    "NotApplicable",
    # what Project returns
    "AtomCompliance",
    "Compliance",
    "Status",
    "TrackCompliance",
    "Outcome",
    "RunResult",
    "AtomEvidence",
    "Format",
    "Report",
    "ResultFile",
    # errors, on the forktex error model
    "BindingError",
    "FsdError",
    "InvalidStandardError",
    "ProjectNotFoundError",
    "UnknownAtomError",
    "UsageError",
    "__version__",
}


def test_the_package_exports_exactly_this():
    assert set(forktex_fsd.__all__) == PUBLIC
    assert all(hasattr(forktex_fsd, name) for name in forktex_fsd.__all__)


def test_errors_carry_forktex_codes():
    assert issubclass(forktex_fsd.FsdError, AppError)
    codes = {
        forktex_fsd.BindingError: AppErrorCode.VALIDATION,
        forktex_fsd.InvalidStandardError: AppErrorCode.VALIDATION,
        forktex_fsd.ProjectNotFoundError: AppErrorCode.NOT_FOUND,
        forktex_fsd.UnknownAtomError: AppErrorCode.NOT_FOUND,
        forktex_fsd.UsageError: AppErrorCode.BAD_REQUEST,
    }
    assert {error: error.code for error in codes} == codes
