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
"""Team and formation domain models."""
from dataclasses import dataclass
from typing import Dict, List

from touchline.models.player import Player


@dataclass
class Formation:
    """Description of an outfield tactical shape excluding the goalkeeper.

    Parameters
    ----------
    name : str
        Human-readable name of the formation (for example ``"4-4-2"``).
    role_counts : Dict[str, int]
        Mapping of role codes to the number of players required in that role.
    """

    name: str  # e.g., "4-4-2", "4-3-3"
    role_counts: Dict[str, int]  # e.g., {"RD": 1, "CD": 2, "LD": 1, "RM": 1, ...}

    def __post_init__(self) -> None:
        """Ensure the formation defines ten outfield players."""
        if sum(self.role_counts.values()) != 10:
            raise ValueError("Formation must have exactly 10 outfield players")


@dataclass
class Team:
    """Container representing a club or squad and its tactical setup.

    Parameters
    ----------
    team_id : int
        Unique identifier for the team.
    name : str
        Display name for the squad.
    players : List[Player]
        Complete roster available to the team.
    formation : Formation
        Tactical formation currently assigned to the team.
    """

    team_id: int
    name: str
    players: List[Player]
    formation: Formation

    def __post_init__(self) -> None:
        """Validate that the roster contains a full starting eleven."""
        if len(self.players) < 11:
            raise ValueError("Team must have at least 11 players")

    def get_team_rating(self) -> float:
        """Calculate overall team rating based on starting 11 and formation.

        Returns
        -------
        float
            Average rating across the starting eleven with the chosen formation.
        """
        total_rating = 0.0

        # Get best players for each role based on formation
        goalkeepers = self.get_players_by_role("GK")
        if not goalkeepers:
            raise ValueError("Formation requires at least one goalkeeper")

        ratings_cache: Dict[int, Dict[str, float]] = {p.player_id: p.get_role_rating() for p in self.players}

        gk_rating = max(ratings_cache[p.player_id]["GK"] for p in goalkeepers)

        # Add role-specific ratings weighted by formation
        for role, count in self.formation.role_counts.items():
            players = self.get_players_by_role(role)
            if len(players) < count:
                raise ValueError(f"Not enough {role} players for formation")

            # Get the top N players for this role where N is the number required by formation
            best_players = sorted(
                players,
                key=lambda p: ratings_cache[p.player_id].get(role, 0.0),
                reverse=True,
            )[:count]

            role_rating = sum(ratings_cache[p.player_id].get(role, 0.0) for p in best_players) / count
            total_rating += role_rating * count

        # Add goalkeeper rating
        total_rating += gk_rating

        # Return average rating (11 players total)
        return total_rating / 11

    def get_players_by_role(self, role: str) -> List[Player]:
        """Get all players who can play in a given role.

        Parameters
        ----------
        role : str
            Role code to filter by (for example ``"CM"``).

        Returns
        -------
        List[Player]
            Players on the roster whose primary role matches ``role``.
        """
        return [p for p in self.players if p.role == role]
