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

"""The standard: the shipped data loads, and a malformed standard is refused by name."""

from __future__ import annotations

import pytest

from forktex_fsd import Effect, EvidenceKind, Profile, Standard, InvalidStandardError, UnknownAtomError, Strength

MINIMAL = """
version = "9.9.0"
[tracks.one]
summary = "A track for the test."
[atoms.alpha]
track = "one"
contract = "Something that must hold."
effect = "external"
evidence = "command"
strength = { library = "must", application = "must", service = "should" }
"""


def test_shipped_standard_has_five_tracks_in_order(standard: Standard):
    assert [t.name for t in standard.tracks] == ["operation", "assurance", "security", "delivery", "documentation"]


def test_the_checks_tracks_are_the_ones_that_run_whole(standard: Standard):
    assert [t.name for t in standard.tracks if t.checks] == ["assurance", "security", "documentation"]
    assert standard.track("assurance") == standard.tracks[1]
    assert standard.track("verify") is None


def test_every_atom_is_bound_by_a_command_or_files(standard: Standard):
    assert {a.evidence for a in standard.atoms} == {EvidenceKind.COMMAND, EvidenceKind.FILE}


def test_atoms_beyond_the_workspace_are_the_delivery_actions(standard: Standard):
    assert {a.name for a in standard.atoms if a.effect is Effect.EXTERNAL} == {"publish", "deploy", "rollback"}
    assert {a.name for a in standard.atoms if a.effect is Effect.HOST} == {"install"}


def test_each_profile_requires_its_own_way_of_reaching_users(standard: Standard):
    must = {
        profile: {a.name for a in standard.atoms if a.strength_for(profile) is Strength.MUST} for profile in Profile
    }
    assert must[Profile.LIBRARY] - must[Profile.APPLICATION] == {"publish"}
    assert must[Profile.APPLICATION] - must[Profile.LIBRARY] == {"install"}
    assert must[Profile.SERVICE] - must[Profile.LIBRARY] == {"start", "stop", "status", "deploy"}


def test_in_track_keeps_standard_order(standard: Standard):
    assert [a.name for a in standard.in_track("operation")] == ["setup", "start", "stop", "status", "clean"]


def test_unknown_atom_is_named_with_the_known_ones(standard: Standard):
    with pytest.raises(UnknownAtomError, match="no atom 'ci'.*setup"):
        standard.atom("ci")


def test_minimal_standard_parses():
    parsed = Standard.parse(MINIMAL)
    assert parsed.version == "9.9.0"
    assert parsed.major_minor == "9.9"
    assert parsed.atom("alpha").strength_for(Profile.SERVICE) is Strength.SHOULD


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("not = [valid", "invalid standard"),
        ('version = "1"', "invalid standard"),
        (MINIMAL.replace('track = "one"', 'track = "nowhere"'), "unknown track 'nowhere'"),
        (MINIMAL.replace(', service = "should"', ""), "no strength for"),
        (MINIMAL.replace('evidence = "command"', 'evidence = "composite"'), "invalid standard"),
        (
            MINIMAL.replace('summary = "A track for the test."', 'summary = "A track for the test."\nchecks = true'),
            "acts beyond the workspace",
        ),
    ],
)
def test_malformed_standard_is_refused(text: str, message: str):
    with pytest.raises(InvalidStandardError, match=message):
        Standard.parse(text)
