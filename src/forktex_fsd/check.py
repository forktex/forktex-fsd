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

from __future__ import annotations

from enum import StrEnum

from forktex.types import BaseWireValueObject
from pydantic import computed_field

from forktex_fsd.binding import Binding, Bindings, Command, CustomAtom, FileBinding, NotApplicable
from forktex_fsd.standard import Atom, Profile, Standard, Strength


class Status(StrEnum):
    """What an atom's binding amounts to, read without running anything."""

    BOUND = "bound"
    PRESENT = "present"
    DECLARED_NA = "declared-na"
    NOT_APPLICABLE = "na"
    UNBOUND = "unbound"
    MISSING_FILE = "missing-file"


_GAPS = frozenset({Status.UNBOUND, Status.MISSING_FILE})


class AtomCompliance(BaseWireValueObject):
    """One atom's place in the compliance report."""

    atom: str
    strength: Strength | None
    status: Status
    detail: str = ""
    custom: bool = False

    @property
    def is_gap(self) -> bool:
        return self.status in _GAPS

    @property
    def is_failure(self) -> bool:
        return self.is_gap and self.strength is Strength.MUST

    @property
    def is_warning(self) -> bool:
        return self.is_gap and self.strength is Strength.SHOULD


class TrackCompliance(BaseWireValueObject):
    """One track's atoms; compliant when no required atom is a gap."""

    track: str
    atoms: tuple[AtomCompliance, ...]

    @property
    def failures(self) -> tuple[AtomCompliance, ...]:
        return tuple(a for a in self.atoms if a.is_failure)

    @property
    def warnings(self) -> tuple[AtomCompliance, ...]:
        return tuple(a for a in self.atoms if a.is_warning)

    @computed_field
    @property
    def compliant(self) -> bool:
        return not self.failures


class Compliance(BaseWireValueObject):
    """Compliance per track, for one repository against one standard."""

    standard: str
    profile: Profile
    tracks: tuple[TrackCompliance, ...]

    @computed_field
    @property
    def compliant(self) -> bool:
        return all(t.compliant for t in self.tracks)


def _describe(binding: Binding) -> str:
    match binding:
        case Command(steps=steps):
            return " ; ".join(steps)
        case FileBinding(file=paths):
            return ", ".join(paths)
        case _:
            return binding.na


def _status(binding: Binding | None, bindings: Bindings) -> Status:
    match binding:
        case None:
            return Status.UNBOUND
        case NotApplicable():
            return Status.DECLARED_NA
        case FileBinding() as files:
            return Status.MISSING_FILE if files.missing(bindings.root) else Status.PRESENT
        case _:
            return Status.BOUND


def _bound_result(atom: Atom, bindings: Bindings) -> AtomCompliance:
    strength = atom.strength_for(bindings.profile)
    binding = bindings.binding(atom.name)
    status = _status(binding, bindings)
    if status is Status.UNBOUND and strength is Strength.NOT_APPLICABLE:
        status = Status.NOT_APPLICABLE
    return AtomCompliance(
        atom=atom.name, strength=strength, status=status, detail=_describe(binding) if binding else ""
    )


def _custom_result(custom: CustomAtom) -> AtomCompliance:
    # A custom atom is the repository's own: it is reported, never held against compliance.
    return AtomCompliance(
        atom=custom.name, strength=None, status=Status.BOUND, detail=_describe(custom.command), custom=True
    )


def _track_results(
    track: str, standard: Standard, bindings: Bindings, results: dict[str, AtomCompliance]
) -> TrackCompliance:
    standard_atoms = tuple(results[a.name] for a in standard.in_track(track))
    custom_atoms = tuple(_custom_result(c) for c in bindings.custom_in((track,)))
    return TrackCompliance(track=track, atoms=standard_atoms + custom_atoms)


def check(standard: Standard, bindings: Bindings) -> Compliance:
    """Compliance per track, read from the bindings alone: nothing is executed."""
    results = {a.name: _bound_result(a, bindings) for a in standard.atoms}
    return Compliance(
        standard=standard.version,
        profile=bindings.profile,
        tracks=tuple(_track_results(t.name, standard, bindings, results) for t in standard.tracks),
    )


__all__ = ["AtomCompliance", "Compliance", "Status", "TrackCompliance", "check"]
