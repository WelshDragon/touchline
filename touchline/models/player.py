# Copyright (C) 2025 Richard Owen
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from dataclasses import dataclass
from typing import Dict


@dataclass
class PlayerAttributes:
    # Technical
    passing: int
    shooting: int
    dribbling: int
    tackling: int
    heading: int

    # Physical
    speed: int
    stamina: int
    strength: int

    # Mental
    vision: int
    positioning: int
    decisions: int

    def __post_init__(self) -> None:
        # Validate all attributes are between 1 and 100
        for attr, value in self.__dict__.items():
            if not 1 <= value <= 100:
                raise ValueError(f"{attr} must be between 1 and 100")


@dataclass
class Player:
    player_id: int
    name: str
    age: int
    role: str  # GK, RD, CD, LD, RM, CM, LM, CF, LCF, RCF
    attributes: PlayerAttributes

    def get_role_rating(self) -> Dict[str, float]:
        """Calculate player's rating for different roles."""
        ratings = {
            "GK": self._goalkeeper_rating(),
            "RD": self._wide_defender_rating(),
            "CD": self._central_defender_rating(),
            "LD": self._wide_defender_rating(),
            "RM": self._wide_midfielder_rating(),
            "CM": self._central_midfielder_rating(),
            "LM": self._wide_midfielder_rating(),
            "CF": self._central_forward_rating(),
            "RCF": self._support_forward_rating(),
            "LCF": self._support_forward_rating(),
        }

        return ratings

    def _goalkeeper_rating(self) -> float:
        return (
            self.attributes.positioning * 0.3
            + self.attributes.decisions * 0.2
            + self.attributes.speed * 0.2
            + self.attributes.strength * 0.3
        ) / 100

    def _central_defender_rating(self) -> float:
        return (
            self.attributes.tackling * 0.3
            + self.attributes.heading * 0.2
            + self.attributes.strength * 0.2
            + self.attributes.positioning * 0.3
        ) / 100

    def _wide_defender_rating(self) -> float:
        return (
            self.attributes.tackling * 0.25
            + self.attributes.speed * 0.25
            + self.attributes.stamina * 0.2
            + self.attributes.passing * 0.15
            + self.attributes.positioning * 0.15
        ) / 100

    def _central_midfielder_rating(self) -> float:
        return (
            self.attributes.passing * 0.3
            + self.attributes.vision * 0.2
            + self.attributes.stamina * 0.2
            + self.attributes.decisions * 0.15
            + self.attributes.tackling * 0.15
        ) / 100

    def _wide_midfielder_rating(self) -> float:
        return (
            self.attributes.dribbling * 0.3
            + self.attributes.speed * 0.25
            + self.attributes.passing * 0.2
            + self.attributes.stamina * 0.15
            + self.attributes.vision * 0.1
        ) / 100

    def _central_forward_rating(self) -> float:
        return (
            self.attributes.shooting * 0.3
            + self.attributes.dribbling * 0.2
            + self.attributes.speed * 0.2
            + self.attributes.positioning * 0.3
        ) / 100

    def _support_forward_rating(self) -> float:
        return (
            self.attributes.shooting * 0.25
            + self.attributes.dribbling * 0.25
            + self.attributes.speed * 0.2
            + self.attributes.passing * 0.15
            + self.attributes.vision * 0.15
        ) / 100
