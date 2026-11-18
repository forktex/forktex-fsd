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


"""`fsd.toml`: what satisfies each atom of the standard in one repository."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path, PureWindowsPath
from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator, Field, StringConstraints, TypeAdapter, ValidationError

from forktex_fsd.errors import BindingError, ProjectNotFoundError
from forktex_fsd.paths import within
from forktex_fsd.standard import Atom, ClosedValueObject, EvidenceKind, Profile, Standard

PROJECT_FILE = "fsd.toml"

# `fsd <name>` answers to fsd's own commands, the tracks and the atoms in one namespace,
# so a custom atom may take none of their names.
COMMANDS = frozenset({"run", "help", "report"})
_HEADER_KEYS = ("standard", "profile")

_Word = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _inside_the_repository(path: str) -> str:
    # PureWindowsPath reads both separators, so one check holds on every OS.
    parsed = PureWindowsPath(path)
    if path.startswith(("/", "\\")) or parsed.drive or ".." in parsed.parts:
        raise ValueError(f"{path!r} must be relative to the repository root and stay inside it")
    return path


_RelativePath = Annotated[_Word, AfterValidator(_inside_the_repository)]
_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_CUSTOM_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class Command(ClosedValueObject):
    """Commands run in order through the platform shell, and the result files they write."""

    steps: Annotated[tuple[_Word, ...], Field(min_length=1)]
    results: tuple[_RelativePath, ...] = ()


class FileBinding(ClosedValueObject):
    """Files, relative to the repository root, whose existence is the evidence."""

    file: Annotated[tuple[_RelativePath, ...], Field(min_length=1)]

    def missing(self, root: Path) -> tuple[str, ...]:
        """The paths that are not a file inside `root`: absent, or a link that leads out of it."""
        return tuple(p for p in self.file if not within(root, p).is_file())


class NotApplicable(ClosedValueObject):
    """Declared not to apply here, with the reason."""

    na: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3)]


Binding = Command | FileBinding | NotApplicable


def _expand_shorthand(value: object) -> object:
    if isinstance(value, dict) and "steps" in value:
        raise ValueError("commands are written as a string, a list, or { run = ... }")
    if isinstance(value, str):
        return {"steps": (value,)}
    if isinstance(value, list):
        return {"steps": tuple(value)}
    if isinstance(value, dict) and isinstance(value.get("file"), str):
        return value | {"file": (value["file"],)}
    if isinstance(value, dict) and "run" in value:
        run, results = value["run"], value.get("results", ())
        rest = {k: v for k, v in value.items() if k not in ("run", "results")}
        return rest | {
            "steps": (run,) if isinstance(run, str) else run,
            "results": (results,) if isinstance(results, str) else results,
        }
    return value


_BINDING = TypeAdapter[Binding](Annotated[Command | FileBinding | NotApplicable, BeforeValidator(_expand_shorthand)])


class _Header(ClosedValueObject):
    standard: str
    profile: Profile


class CustomAtom(ClosedValueObject):
    """An atom the repository adds to one of the standard's tracks."""

    name: str
    track: str
    command: Command


class Bindings(ClosedValueObject):
    """One repository's `fsd.toml`, read against the standard: its root, profile and bindings."""

    root: Path
    profile: Profile
    atoms: dict[str, Binding]
    custom: tuple[CustomAtom, ...] = ()

    def binding(self, atom: str) -> Binding | None:
        return self.atoms.get(atom)

    def custom_atom(self, name: str) -> CustomAtom | None:
        return next((c for c in self.custom if c.name == name), None)

    def custom_in(self, tracks: tuple[str, ...]) -> tuple[CustomAtom, ...]:
        return tuple(c for c in self.custom if c.track in tracks)


def _readable(written: str, implemented: str) -> bool:
    # A checker reads every file of its own major version written for its minor or an earlier one,
    # as a minor version of the standard only adds.
    found, own = _VERSION.fullmatch(written), _VERSION.fullmatch(implemented)
    if found is None or own is None:
        return False
    return found[1] == own[1] and int(found[2]) <= int(own[2])


def _read_header(header: dict[str, Any], standard: Standard) -> _Header:
    try:
        parsed = _Header.model_validate(header)
    except ValidationError as exc:
        raise BindingError(
            f'{PROJECT_FILE} must declare standard = "{standard.major_minor}" and a profile', details={"key": "header"}
        ) from exc
    if not _readable(parsed.standard, standard.major_minor):
        raise BindingError(
            f"{PROJECT_FILE} follows standard {parsed.standard}; this checker implements {standard.major_minor}"
            " and reads files of the same major version up to it",
            details={"key": "standard", "found": parsed.standard, "expected": standard.major_minor},
        )
    return parsed


def _standard_atom_under(section: str, atom: Atom) -> Atom:
    if atom.track != section:
        raise BindingError(
            f"`{atom.name}` belongs under [{atom.track}], not [{section}]",
            details={"atom": atom.name, "section": section, "expected": atom.track},
        )
    return atom


def _validate(name: str, value: object) -> Binding:
    try:
        return _BINDING.validate_python(value)
    except ValidationError as exc:
        raise BindingError(
            f"`{name}`: not a command, a {{ file }} or an {{ na }} — {exc.errors()[0]['msg']}", details={"atom": name}
        ) from exc


def _parse_binding(atom: Atom, value: object) -> Binding:
    binding = _validate(atom.name, value)
    expected = FileBinding if atom.evidence is EvidenceKind.FILE else Command
    if not isinstance(binding, expected | NotApplicable):
        raise BindingError(
            f"`{atom.name}` is evidenced by a {atom.evidence.value}, not a {type(binding).__name__}",
            details={"atom": atom.name, "expected": atom.evidence.value},
        )
    return binding


def _parse_custom(section: str, name: str, value: object, tracks: set[str]) -> CustomAtom:
    if not _CUSTOM_NAME.fullmatch(name):
        raise BindingError(
            f"`{name}` is not a usable atom name: letters, digits, `.`, `_` and `-`, starting with a letter or digit",
            details={"atom": name},
        )
    if name in COMMANDS | tracks:
        raise BindingError(
            f"`{name}` names an fsd command or a track; a custom atom may not be called {sorted(COMMANDS | tracks)}",
            details={"atom": name},
        )
    binding = _validate(name, value)
    if not isinstance(binding, Command):
        raise BindingError(
            f"`{name}` is not in the standard, so it is a custom atom, and a custom atom is a command",
            details={"atom": name, "expected": EvidenceKind.COMMAND.value},
        )
    return CustomAtom(name=name, track=section, command=binding)


class _Sections(ClosedValueObject):
    atoms: dict[str, Binding]
    custom: tuple[CustomAtom, ...]


def _section_entries(section: str, entries: object, tracks: set[str]) -> dict[str, object]:
    if section not in tracks:
        raise BindingError(
            f"[{section}] is not a track of the standard; tracks: {sorted(tracks)}", details={"section": section}
        )
    if not isinstance(entries, dict):
        raise BindingError(
            f"`{section}` is a track, so it is written as a table: [{section}]", details={"section": section}
        )
    return entries


def _read_sections(sections: dict[str, Any], standard: Standard) -> _Sections:
    tracks = {t.name for t in standard.tracks}
    known = {a.name: a for a in standard.atoms}
    atoms: dict[str, Binding] = {}
    custom: dict[str, CustomAtom] = {}
    for section, entries in sections.items():
        for name, value in _section_entries(section, entries, tracks).items():
            if name in known:
                atoms[name] = _parse_binding(_standard_atom_under(section, known[name]), value)
            elif name in custom:
                raise BindingError(
                    f"custom atom `{name}` is under both [{custom[name].track}] and [{section}]",
                    details={"atom": name, "section": section},
                )
            else:
                custom[name] = _parse_custom(section, name, value, tracks)
    return _Sections(atoms=atoms, custom=tuple(custom.values()))


def parse_bindings(text: str, root: Path, standard: Standard) -> Bindings:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise BindingError(f"{PROJECT_FILE} is not valid TOML: {exc}", details={"key": "toml"}) from exc
    header = _read_header({k: v for k, v in data.items() if k in _HEADER_KEYS}, standard)
    sections = _read_sections({k: v for k, v in data.items() if k not in _HEADER_KEYS}, standard)
    return Bindings(root=root, profile=header.profile, atoms=sections.atoms, custom=sections.custom)


def read_bindings(root: Path, standard: Standard) -> Bindings:
    path = root / PROJECT_FILE
    if not path.is_file():
        raise ProjectNotFoundError(f"no {PROJECT_FILE} in {root}", details={"root": str(root)})
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BindingError(f"{PROJECT_FILE} is not UTF-8: {exc}", details={"key": "encoding"}) from exc
    return parse_bindings(text, root, standard)


def find_root(start: Path) -> Path:
    for directory in (start, *start.parents):
        if (directory / PROJECT_FILE).is_file():
            return directory
    raise ProjectNotFoundError(f"no {PROJECT_FILE} in {start} or any directory above it", details={"start": str(start)})


__all__ = [
    "COMMANDS",
    "PROJECT_FILE",
    "Binding",
    "Bindings",
    "Command",
    "CustomAtom",
    "FileBinding",
    "NotApplicable",
    "find_root",
    "parse_bindings",
    "read_bindings",
]
