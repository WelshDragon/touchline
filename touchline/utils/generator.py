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
import random
from typing import List, Optional

from touchline.models.player import Player, PlayerAttributes
from touchline.models.team import Formation, Team

ROLE_IMPORTANT_ATTRIBUTES = {
    "GK": ["positioning", "decisions", "strength"],
    "RD": ["tackling", "speed", "stamina", "passing"],
    "CD": ["tackling", "heading", "strength", "positioning"],
    "LD": ["tackling", "speed", "stamina", "passing"],
    "RM": ["dribbling", "speed", "passing", "vision"],
    "CM": ["passing", "vision", "decisions", "stamina"],
    "LM": ["dribbling", "speed", "passing", "vision"],
    "CF": ["shooting", "positioning", "strength", "dribbling"],
    "RCF": ["shooting", "dribbling", "speed", "vision"],
    "LCF": ["shooting", "dribbling", "speed", "vision"],
}


def generate_random_player(id: int, name: Optional[str] = None, role: Optional[str] = None) -> Player:
    """Generate a player with random attributes."""
    if name is None:
        # Simple random name generation
        first_names = ["John", "James", "David", "Michael", "Robert", "Carlos", "Juan", "Luis"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Rodriguez"]
        name = f"{random.choice(first_names)} {random.choice(last_names)}"

    if role is None:
        role = random.choice(list(ROLE_IMPORTANT_ATTRIBUTES.keys()))

    # Generate random attributes with role-specific weighting
    base_range = (40, 80)  # Base range for attributes
    boost_range = (60, 90)  # Boosted range for role-specific attributes

    def get_attribute(is_important: bool) -> int:
        if is_important:
            return random.randint(*boost_range)
        return random.randint(*base_range)

    # Define important attributes for each role
    important_attrs = ROLE_IMPORTANT_ATTRIBUTES.get(role, ["passing", "vision", "stamina"])

    attributes = PlayerAttributes(
        # Technical
        passing=get_attribute("passing" in important_attrs),
        shooting=get_attribute("shooting" in important_attrs),
        dribbling=get_attribute("dribbling" in important_attrs),
        tackling=get_attribute("tackling" in important_attrs),
        heading=get_attribute("heading" in important_attrs),
        # Physical
        speed=get_attribute("speed" in important_attrs),
        stamina=get_attribute("stamina" in important_attrs),
        strength=get_attribute("strength" in important_attrs),
        # Mental
        vision=get_attribute("vision" in important_attrs),
        positioning=get_attribute("positioning" in important_attrs),
        decisions=get_attribute("decisions" in important_attrs),
    )

    return Player(player_id=id, name=name, age=random.randint(18, 35), role=role, attributes=attributes)


def generate_team(
    id: int, name: Optional[str] = None, formation_name: str = "4-4-2", starting_player_id: int = 1
) -> Team:
    """Generate a team with random players using specified formation."""
    if name is None:
        # Simple random team name generation
        prefixes = ["FC", "United", "City", "Athletic", "Sporting"]
        cities = ["London", "Madrid", "Paris", "Milan", "Munich"]
        name = f"{random.choice(cities)} {random.choice(prefixes)}"

    # Define formation
    formation_map = {
        "4-4-2": {"RD": 1, "CD": 2, "LD": 1, "RM": 1, "CM": 2, "LM": 1, "RCF": 1, "LCF": 1},
        "4-3-3": {"RD": 1, "CD": 2, "LD": 1, "RM": 1, "CM": 1, "LM": 1, "RCF": 1, "CF": 1, "LCF": 1},
        "3-5-2": {"RD": 1, "CD": 1, "LD": 1, "RM": 1, "CM": 3, "LM": 1, "RCF": 1, "LCF": 1},
    }

    if formation_name not in formation_map:
        raise ValueError(f"Unsupported formation: {formation_name}")

    formation = Formation(name=formation_name, role_counts=formation_map[formation_name])

    # Generate players
    players: List[Player] = []
    player_id = starting_player_id

    # Add goalkeeper
    players.append(generate_random_player(player_id, role="GK"))
    player_id += 1

    # Add outfield players according to formation
    for role_name, count in formation.role_counts.items():
        for _ in range(count):
            players.append(generate_random_player(player_id, role=role_name))
            player_id += 1

    # Add some substitutes
    for _ in range(7):  # 7 substitutes
        players.append(generate_random_player(player_id, role=random.choice(list(ROLE_IMPORTANT_ATTRIBUTES.keys()))))
        player_id += 1

    return Team(team_id=id, name=name, players=players, formation=formation)
