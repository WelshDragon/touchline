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
import json
from pathlib import Path
from typing import Tuple

from touchline.models.player import Player, PlayerAttributes
from touchline.models.team import Formation, Team


def player_from_dict(d: dict) -> Player:
    """Create a Player instance from a dict.

    Expected keys: id, name, age, role, attributes (falls back to legacy "position").
    """
    attrs = d.get("attributes", {}) or {}
    pa = PlayerAttributes(
        passing=attrs.get("passing", 50),
        shooting=attrs.get("shooting", 50),
        dribbling=attrs.get("dribbling", 50),
        tackling=attrs.get("tackling", 50),
        heading=attrs.get("heading", 50),
        speed=attrs.get("speed", 50),
        stamina=attrs.get("stamina", 50),
        strength=attrs.get("strength", 50),
        vision=attrs.get("vision", 50),
        positioning=attrs.get("positioning", 50),
        decisions=attrs.get("decisions", 50),
    )

    role_value = d.get("role") or d.get("position", "CM")

    p = Player(
        player_id=d.get("id", 0),
        name=d.get("name", f"player_{d.get('id', 0)}"),
        age=d.get("age", 25),
        role=role_value,
        attributes=pa,
    )
    return p


def load_teams_from_json(path: str) -> Tuple[Team, Team]:
    """Load home/away teams from a JSON file and return (home, away).

    File schema matches data/players.json in the repository.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Players JSON not found: {path}")

    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    def build_team(section: str) -> Team:
        tdata = data[section]
        players = []
        for pl in tdata.get("players", []):
            players.append(player_from_dict(pl))
        formation_data = tdata.get("formation", {}) or {}
        role_counts = formation_data.get(
            "roles",
            {"RD": 1, "CD": 2, "LD": 1, "RM": 1, "CM": 2, "LM": 1, "RCF": 1, "LCF": 1},
        )
        if "positions" in formation_data and "roles" not in formation_data:
            role_counts = formation_data["positions"]
        formation = Formation(
            name=formation_data.get("name", "custom"),
            role_counts=role_counts,
        )
        team = Team(
            team_id=tdata.get("id", 0),
            name=tdata.get("name", f"Team_{section}"),
            players=players,
            formation=formation,
        )
        return team

    home = build_team("home")
    away = build_team("away")
    return home, away
