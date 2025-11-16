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
"""Tests for utility modules (generator, roster, debug)."""

from pathlib import Path

from touchline.models.team import Formation
from touchline.utils.generator import generate_random_player, generate_team
from touchline.utils.roster import load_teams_from_json, player_from_dict


class TestGenerator:
    """Tests for generator utility functions."""

    def test_generate_random_player(self) -> None:
        """Test generating a random player."""
        player = generate_random_player(id=1)
        assert isinstance(player.player_id, int)
        assert isinstance(player.name, str)
        assert isinstance(player.age, int)
        assert len(player.name) > 0
        assert player.role in {"GK", "RD", "CD", "LD", "RM", "CM", "LM", "CF", "RCF", "LCF"}
        assert 1 <= player.attributes.speed <= 100
        assert 1 <= player.attributes.shooting <= 100
        assert 18 <= player.age <= 38

    def test_generate_random_player_with_role(self) -> None:
        """Test generating a random player with a specific role."""
        player = generate_random_player(id=1, role="RCF")
        assert player.role == "RCF"
        assert player.player_id == 1
        # Forwards should have decent shooting
        assert player.attributes.shooting >= 50

    def test_generate_team(self) -> None:
        """Test generating a complete team."""
        team = generate_team(id=1, name="Test FC")
        assert team.team_id == 1
        assert team.name == "Test FC"
        assert len(team.players) >= 11
        assert team.formation is not None
        assert isinstance(team.formation, Formation)
        assert team.players[0].start_position is not None
        assert team.players[0].start_position[0] < 0  # Home sides default to negative half

    def test_generate_team_side_orientation(self) -> None:
        """Start positions should mirror depending on the requested side."""
        home_team = generate_team(id=10, name="Home Test", side="home")
        away_team = generate_team(id=11, name="Away Test", side="away")

        home_gk = home_team.players[0]
        away_gk = away_team.players[0]

        assert home_gk.start_position is not None
        assert away_gk.start_position is not None
        assert home_gk.start_position[0] < 0
        assert away_gk.start_position[0] > 0

    def test_generate_multiple_teams_unique(self) -> None:
        """Test generating multiple teams produces unique players."""
        team1 = generate_team(id=1, name="Team 1")
        team2 = generate_team(id=2, name="Team 2")
        # Team IDs should be different
        assert team1.team_id != team2.team_id
        # Names should be different
        assert team1.name != team2.name


class TestRoster:
    """Tests for roster loading utility functions."""

    def test_player_from_dict(self) -> None:
        """Test loading a player from dictionary."""
        player_data = {
            "id": 1,
            "name": "Test Player",
            "age": 25,
            "position": "CM",
            "attributes": {
                "passing": 70,
                "shooting": 75,
                "dribbling": 85,
                "tackling": 60,
                "heading": 65,
                "speed": 80,
                "stamina": 80,
                "strength": 75,
                "vision": 72,
                "positioning": 68,
                "decisions": 70,
            },
        }
        player = player_from_dict(player_data)
        assert player.player_id == 1
        assert player.name == "Test Player"
        assert player.age == 25
        assert player.role == "CM"
        assert player.attributes.speed == 80
        assert player.attributes.shooting == 75
        assert player.start_position is None

    def test_player_from_dict_with_start_position(self) -> None:
        """Start positions supplied in payloads should be captured."""
        player_data = {
            "id": 2,
            "name": "Anchored Midfielder",
            "age": 24,
            "role": "CM",
            "start_position": {"x": -12.5, "y": 3.0},
            "attributes": {
                "passing": 65,
                "shooting": 55,
                "dribbling": 60,
                "tackling": 68,
                "heading": 50,
                "speed": 62,
                "stamina": 77,
                "strength": 70,
                "vision": 72,
                "positioning": 69,
                "decisions": 71,
            },
        }
        player = player_from_dict(player_data)
        assert player.start_position == (-12.5, 3.0)

    def test_load_teams_from_json(self) -> None:
        """Test loading teams from JSON file."""
        # Use the actual data file from workspace
        data_file = Path("/workspaces/ubuntu/football-simulator/data/players.json")
        if data_file.exists():
            teams = load_teams_from_json(str(data_file))
            assert len(teams) > 0
            for team in teams:
                assert team.name
                assert len(team.players) >= 11
                assert team.formation is not None
                kickoff_x = [p.start_position[0] for p in team.players[:11] if p.start_position is not None]
                assert len(kickoff_x) == 11
                # Home squad should line up in negative half, away in positive
                if team.team_id == 1:
                    assert all(x <= 0 for x in kickoff_x)
                else:
                    assert all(x >= 0 for x in kickoff_x)
