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

import tomllib
from enum import StrEnum
from importlib.resources import files
from typing import Annotated, Self

from forktex.types import BaseValueObject
from pydantic import ConfigDict, Field, ValidationError, model_validator

from forktex_fsd.errors import InvalidStandardError, UnknownAtomError


class ClosedValueObject(BaseValueObject):
    """A forktex value object that refuses unknown keys, so a typo in a file fails instead of vanishing."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Profile(StrEnum):
    """How the software reaches its user: consumed, installed or deployed."""

    LIBRARY = "library"
    APPLICATION = "application"
    SERVICE = "service"


class Strength(StrEnum):
    """How much an atom binds a profile."""

    MUST = "must"
    SHOULD = "should"
    NOT_APPLICABLE = "na"


class Effect(StrEnum):
    """What running an atom touches, from inspecting only to acting on the world."""

    READ_ONLY = "read-only"
    LOCAL = "local"
    HOST = "host"
    EXTERNAL = "external"

    @property
    def is_routine(self) -> bool:
        """Stays in the workspace, so it may run as a matter of course: inside a track run or a report."""
        return self in (Effect.READ_ONLY, Effect.LOCAL)


class EvidenceKind(StrEnum):
    """What a repository binds an atom to."""

    COMMAND = "command"
    FILE = "file"


class Track(ClosedValueObject):
    """A purpose axis; compliance is reported per track."""

    name: str
    summary: Annotated[str, Field(min_length=10)]
    checks: bool = False


class Atom(ClosedValueObject):
    """One checkable capability, stated as a technology-agnostic contract."""

    name: str
    track: str
    contract: Annotated[str, Field(min_length=10)]
    effect: Effect
    evidence: EvidenceKind
    strength: dict[Profile, Strength]

    @model_validator(mode="after")
    def _strength_for_every_profile(self) -> Self:
        missing = set(Profile) - set(self.strength)
        if missing:
            raise ValueError(f"atom {self.name!r} gives no strength for {sorted(missing)}")
        return self

    def strength_for(self, profile: Profile) -> Strength:
        return self.strength[profile]


class Standard(ClosedValueObject):
    """The whole standard, in the order it is written."""

    version: str
    tracks: tuple[Track, ...]
    atoms: tuple[Atom, ...]

    @classmethod
    def load(cls) -> Standard:
        """The standard this version of the package ships."""
        return cls.parse(files("forktex_fsd").joinpath("standard.toml").read_text(encoding="utf-8"))

    @classmethod
    def parse(cls, text: str) -> Standard:
        """A standard written in the shape of `standard.toml`."""
        try:
            data = tomllib.loads(text)
            return cls(
                version=data["version"],
                tracks=tuple(Track(name=name, **body) for name, body in data["tracks"].items()),
                atoms=tuple(Atom(name=name, **body) for name, body in data["atoms"].items()),
            )
        except (tomllib.TOMLDecodeError, KeyError, TypeError, ValidationError) as exc:
            raise InvalidStandardError(f"invalid standard: {exc}") from exc

    @model_validator(mode="after")
    def _tracks_resolve(self) -> Self:
        known = {t.name for t in self.tracks}
        checking = {t.name for t in self.tracks if t.checks}
        for atom in self.atoms:
            if atom.track not in known:
                raise ValueError(f"atom {atom.name!r} names unknown track {atom.track!r}")
            if atom.track in checking and not atom.effect.is_routine:
                raise ValueError(
                    f"atom {atom.name!r} acts beyond the workspace, so {atom.track!r} cannot be a checks track"
                )
        return self

    @property
    def major_minor(self) -> str:
        return ".".join(self.version.split(".")[:2])

    def atom(self, name: str) -> Atom:
        for atom in self.atoms:
            if atom.name == name:
                return atom
        known = ", ".join(a.name for a in self.atoms)
        raise UnknownAtomError(f"the standard has no atom {name!r}; known: {known}", details={"atom": name})

    def in_track(self, track: str) -> tuple[Atom, ...]:
        return tuple(a for a in self.atoms if a.track == track)

    def track(self, name: str) -> Track | None:
        return next((t for t in self.tracks if t.name == name), None)


__all__ = ["Atom", "ClosedValueObject", "Effect", "EvidenceKind", "Profile", "Standard", "Strength", "Track"]
