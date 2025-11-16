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
"""Utilities that synthesise test players and teams for quick simulations."""
import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from touchline.engine.config import ENGINE_CONFIG
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
    """Generate a player with random attributes.

    Parameters
    ----------
    id : int
        Unique identifier assigned to the created player.
    name : Optional[str]
        Human-readable name to apply; a pseudo-random name is chosen when omitted.
    role : Optional[str]
        Preferred positional role influencing attribute weighting; random when ``None``.

    Returns
    -------
    Player
        A newly constructed player instance with stochastic attribute scores.
    """
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
    id: int,
    name: Optional[str] = None,
    formation_name: str = "4-4-2",
    starting_player_id: int = 1,
    side: str = "home",
) -> Team:
    """Generate a team with random players using specified formation.

    Parameters
    ----------
    id : int
        Unique identifier assigned to the generated team.
    name : Optional[str]
        Squad name to apply; synthesised when ``None``.
    formation_name : str
        Tactical formation blueprint to instantiate (for example ``"4-4-2"``).
    starting_player_id : int
        Identifier to use for the first generated player; increments for each additional player.
    side : {"home", "away"}
        Which half of the pitch the generated starting XI should occupy. Home
        sides line up in the negative X half, away sides in the positive half.

    Returns
    -------
    Team
        Team object populated with starting XI and substitutes aligned to the requested formation.
    """
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

    # Assign default kick-off locations for the starting XI
    _assign_start_positions(players, side)

    # Add some substitutes
    for _ in range(7):  # 7 substitutes
        players.append(generate_random_player(player_id, role=random.choice(list(ROLE_IMPORTANT_ATTRIBUTES.keys()))))
        player_id += 1

    return Team(team_id=id, name=name, players=players, formation=formation)


def _assign_start_positions(players: List[Player], side: str) -> None:
    """Populate ``start_position`` for the first eleven players in-place.

    Parameters
    ----------
    players : List[Player]
        Roster whose leading eleven entries should receive starting coordinates.
    side : str
        ``"home"`` or ``"away"``; home teams start on the negative X half, away teams on the positive half.
    """
    if side not in {"home", "away"}:
        raise ValueError("side must be either 'home' or 'away'")

    direction = -1 if side == "home" else 1
    role_counts: Dict[str, int] = defaultdict(int)

    for player in players[:11]:
        role_key = player.role.upper()
        slot_index = role_counts[role_key]
        role_counts[role_key] += 1
        base_x, base_y = _formation_slot_offset(role_key, slot_index)
        player.start_position = (direction * base_x, base_y)


def _formation_slot_offset(role: str, index: int) -> Tuple[float, float]:
    """Return the default formation slot coordinates for ``role``.

    Parameters
    ----------
    role : str
        Role identifier such as ``"CM"`` or ``"RCF"``.
    index : int
        Zero-based slot index among teammates sharing the same role.

    Returns
    -------
    Tuple[float, float]
        ``(x, y)`` coordinates relative to the pitch centre.
    """
    cfg = ENGINE_CONFIG.formation
    role = role.upper()

    if role == "GK":
        return (cfg.goalkeeper_x, 0.0)

    if role in {"RD", "LD"}:
        base_offset = -cfg.fullback_base_offset if role == "RD" else cfg.fullback_base_offset
        stagger = -cfg.fullback_stagger if role == "RD" else cfg.fullback_stagger
        y = base_offset + index * stagger
        return (cfg.fullback_x, y)

    if role == "CD":
        offsets = cfg.centreback_offsets
        y = offsets[index] if index < len(offsets) else 0.0
        return (cfg.centreback_x, y)

    if role in {"RM", "LM"}:
        base_offset = -cfg.wide_midfielder_base_offset if role == "RM" else cfg.wide_midfielder_base_offset
        stagger = -cfg.wide_midfielder_stagger if role == "RM" else cfg.wide_midfielder_stagger
        y = base_offset + index * stagger
        return (cfg.wide_midfielder_x, y)

    if role == "CM":
        offsets = cfg.central_midfielder_offsets
        y = offsets[index] if index < len(offsets) else 0.0
        return (cfg.central_midfielder_x, y)

    if role in {"RCF", "LCF"}:
        base_offset = -cfg.wide_forward_base_offset if role == "RCF" else cfg.wide_forward_base_offset
        stagger = -cfg.wide_forward_stagger if role == "RCF" else cfg.wide_forward_stagger
        y = base_offset + index * stagger
        return (cfg.centre_forward_x, y)

    if role == "CF":
        offsets = cfg.centre_forward_offsets
        y = offsets[index] if index < len(offsets) else 0.0
        return (cfg.centre_forward_x, y)

    # Fallback to a central midfielder slot when the role is unknown.
    return (cfg.central_midfielder_x, 0.0)
