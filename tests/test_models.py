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
"""Tests for player, formation, and team models."""

import pytest

from touchline.models.player import Player, PlayerAttributes
from touchline.models.team import Formation, Team


class TestPlayerAttributes:
    """Tests for PlayerAttributes class."""

    def test_create_player_attributes(self) -> None:
        """Test creating player attributes."""
        attrs = PlayerAttributes(
            passing=70,
            shooting=75,
            dribbling=85,
            tackling=60,
            heading=65,
            speed=80,
            stamina=80,
            strength=75,
            vision=72,
            positioning=68,
            decisions=70,
        )
        assert attrs.speed == 80
        assert attrs.shooting == 75
        assert attrs.passing == 70
        assert attrs.tackling == 60
        assert attrs.dribbling == 85
        assert attrs.strength == 75
        assert attrs.stamina == 80

    def test_player_attributes_validation_range(self) -> None:
        """Test attributes must be within 1..100."""
        with pytest.raises(ValueError):
            PlayerAttributes(
                passing=0,
                shooting=50,
                dribbling=50,
                tackling=50,
                heading=50,
                speed=50,
                stamina=50,
                strength=50,
                vision=50,
                positioning=50,
                decisions=50,
            )


class TestPlayer:
    """Tests for Player class."""

    def test_create_player(self) -> None:
        attrs = PlayerAttributes(
            passing=70,
            shooting=75,
            dribbling=85,
            tackling=60,
            heading=65,
            speed=80,
            stamina=80,
            strength=75,
            vision=72,
            positioning=68,
            decisions=70,
        )
        player = Player(player_id=1, name="Test Player", age=25, role="RCF", attributes=attrs)
        assert player.player_id == 1
        assert player.name == "Test Player"
        assert player.age == 25
        assert player.role == "RCF"
        assert player.attributes.speed == 80

    def test_get_role_rating_keys(self) -> None:
        attrs = PlayerAttributes(
            passing=80,
            shooting=80,
            dribbling=80,
            tackling=80,
            heading=80,
            speed=80,
            stamina=80,
            strength=80,
            vision=80,
            positioning=80,
            decisions=80,
        )
        player = Player(player_id=2, name="Two", age=27, role="CM", attributes=attrs)
        ratings = player.get_role_rating()
        assert set(ratings.keys()) == {
            "GK",
            "RD",
            "CD",
            "LD",
            "RM",
            "CM",
            "LM",
            "CF",
            "RCF",
            "LCF",
        }
        for value in ratings.values():
            assert 0 <= value <= 1

    def test_forward_rating_higher_than_gk(self) -> None:
        attrs = PlayerAttributes(
            passing=50,
            shooting=90,
            dribbling=85,
            tackling=40,
            heading=50,
            speed=90,
            stamina=70,
            strength=70,
            vision=60,
            positioning=85,
            decisions=65,
        )
        player = Player(player_id=3, name="RCF", age=23, role="RCF", attributes=attrs)
        ratings = player.get_role_rating()
        assert ratings["RCF"] > ratings["GK"]


class TestFormation:
    def test_create_formation(self) -> None:
        formation = Formation(
            name="4-4-2",
            role_counts={"RD": 1, "CD": 2, "LD": 1, "RM": 1, "CM": 2, "LM": 1, "RCF": 1, "LCF": 1},
        )
        assert formation.name == "4-4-2"
        assert formation.role_counts["RD"] == 1
        assert formation.role_counts["CD"] == 2
        assert formation.role_counts["LCF"] == 1

    def test_formation_total_players(self) -> None:
        formation = Formation(
            name="4-3-3",
            role_counts={"RD": 1, "CD": 2, "LD": 1, "RM": 1, "CM": 1, "LM": 1, "RCF": 1, "CF": 1, "LCF": 1},
        )
        assert sum(formation.role_counts.values()) == 10


class TestTeam:
    """Tests for Team class."""

    def test_create_team(self) -> None:
        formation = Formation(
            name="4-4-2",
            role_counts={"RD": 1, "CD": 2, "LD": 1, "RM": 1, "CM": 2, "LM": 1, "RCF": 1, "LCF": 1},
        )
        players = self._create_test_players(11)
        team = Team(team_id=1, name="Test FC", players=players, formation=formation)
        assert team.team_id == 1
        assert team.name == "Test FC"
        assert len(team.players) == 11
        assert team.formation.name == "4-4-2"

    def test_team_requires_minimum_11_players(self) -> None:
        formation = Formation(
            name="4-4-2",
            role_counts={"RD": 1, "CD": 2, "LD": 1, "RM": 1, "CM": 2, "LM": 1, "RCF": 1, "LCF": 1},
        )
        with pytest.raises(ValueError, match="must have at least 11 players"):
            Team(team_id=1, name="Test FC", players=self._create_test_players(10), formation=formation)

    def test_get_team_rating(self) -> None:
        formation = Formation(
            name="4-4-2",
            role_counts={"RD": 1, "CD": 2, "LD": 1, "RM": 1, "CM": 2, "LM": 1, "RCF": 1, "LCF": 1},
        )
        players = self._create_test_players(11)
        team = Team(team_id=1, name="Test FC", players=players, formation=formation)
        rating = team.get_team_rating()
        assert 0 <= rating <= 1

    def test_team_formation_matches_roles(self) -> None:
        formation = Formation(
            name="4-4-2",
            role_counts={"RD": 1, "CD": 2, "LD": 1, "RM": 1, "CM": 2, "LM": 1, "RCF": 1, "LCF": 1},
        )
        players = self._create_test_players(11)
        team = Team(team_id=1, name="Test FC", players=players, formation=formation)
        role_counts = {
            "GK": sum(1 for p in team.players if p.role == "GK"),
            "RD": sum(1 for p in team.players if p.role == "RD"),
            "CD": sum(1 for p in team.players if p.role == "CD"),
            "LD": sum(1 for p in team.players if p.role == "LD"),
            "RM": sum(1 for p in team.players if p.role == "RM"),
            "CM": sum(1 for p in team.players if p.role == "CM"),
            "LM": sum(1 for p in team.players if p.role == "LM"),
            "RCF": sum(1 for p in team.players if p.role == "RCF"),
            "LCF": sum(1 for p in team.players if p.role == "LCF"),
        }
        assert role_counts["GK"] == 1
        assert role_counts["RD"] == 1
        assert role_counts["CD"] == 2
        assert role_counts["LD"] == 1
        assert role_counts["RM"] == 1
        assert role_counts["CM"] == 2
        assert role_counts["LM"] == 1
        assert role_counts["RCF"] == 1
        assert role_counts["LCF"] == 1

    def _create_test_players(self, count: int) -> list[Player]:
        players: list[Player] = []
        # First player is goalkeeper
        players.append(
            Player(
                player_id=0,
                name="Goalkeeper",
                age=28,
                role="GK",
                attributes=PlayerAttributes(
                    passing=60,
                    shooting=40,
                    dribbling=50,
                    tackling=50,
                    heading=60,
                    speed=60,
                    stamina=70,
                    strength=75,
                    vision=55,
                    positioning=80,
                    decisions=75,
                ),
            )
        )
        # Rest are outfield players
        roles = ["RD", "CD", "CD", "LD", "RM", "CM", "CM", "LM", "RCF", "LCF"]
        for i in range(1, min(count, 11)):
            players.append(
                Player(
                    player_id=i,
                    name=f"Player {i}",
                    age=25,
                    role=roles[i - 1] if i <= len(roles) else "CM",
                    attributes=PlayerAttributes(
                        passing=70,
                        shooting=70,
                        dribbling=70,
                        tackling=70,
                        heading=70,
                        speed=70,
                        stamina=70,
                        strength=70,
                        vision=70,
                        positioning=70,
                        decisions=70,
                    ),
                )
            )
        # If more than 11, add extras as midfielders
        for i in range(11, count):
            players.append(
                Player(
                    player_id=i,
                    name=f"Player {i}",
                    age=25,
                    role="CM",
                    attributes=PlayerAttributes(
                        passing=70,
                        shooting=70,
                        dribbling=70,
                        tackling=70,
                        heading=70,
                        speed=70,
                        stamina=70,
                        strength=70,
                        vision=70,
                        positioning=70,
                        decisions=70,
                    ),
                )
            )
        return players
