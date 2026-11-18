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

"""Everything forktex-fsd raises, on the forktex error model: a code, a message, details."""

from __future__ import annotations

from forktex.error import AppError, AppErrorCode


class FsdError(AppError):
    """Base for any error the library itself raises."""

    code = AppErrorCode.INTERNAL


class InvalidStandardError(FsdError):
    """A standard that does not parse into tracks and atoms."""

    code = AppErrorCode.VALIDATION


class UnknownAtomError(FsdError):
    """A name that is neither an atom of the standard nor a custom atom of the repository."""

    code = AppErrorCode.NOT_FOUND


class BindingError(FsdError):
    """A repository's fsd.toml is malformed or contradicts the standard."""

    code = AppErrorCode.VALIDATION


class ProjectNotFoundError(FsdError):
    """No fsd.toml where one was looked for."""

    code = AppErrorCode.NOT_FOUND


class UsageError(FsdError):
    """Arguments an atom cannot take: one that is not bound to a command, or the gate."""

    code = AppErrorCode.BAD_REQUEST


__all__ = ["BindingError", "FsdError", "InvalidStandardError", "ProjectNotFoundError", "UnknownAtomError", "UsageError"]
