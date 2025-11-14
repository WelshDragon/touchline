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
"""Player-specific state management for the match engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from touchline.engine.physics import BallState, PlayerState, Vector2D
from touchline.engine.roles import create_role_behaviour
from touchline.models.team import Team
from touchline.utils.debug import MatchDebugger


@dataclass
class PlayerContext:
    """Snapshot of shared state used across helper methods."""

    player: "PlayerMatchState"
    ball: BallState
    all_players: List["PlayerMatchState"]
    teammates: List["PlayerMatchState"] = field(init=False)
    opponents: List["PlayerMatchState"] = field(init=False)

    def __post_init__(self) -> None:
        self.teammates = [p for p in self.all_players if p.team == self.player.team and p != self.player]
        self.opponents = [p for p in self.all_players if p.team != self.player.team]


@dataclass
class PassDecision:
    """Concrete pass choice selected under pressure."""

    target: "PlayerMatchState"
    pass_type: str
    power: float
    score: float
    lane_quality: float
    lead_target: Vector2D
    origin: str = "base"


class PlayerMatchState:
    """Runtime state and behaviour for a player participating in a match."""

    def __init__(
        self,
        player_id: int,
        team: Team,
        state: PlayerState,
        role_position: Vector2D,
        match_time: float = 0.0,
        is_home_team: bool = False,
        debugger: Optional[MatchDebugger] = None,
        current_target: Optional[Vector2D] = None,
        player_role: str = "",
    ) -> None:
        self.player_id = player_id
        self.team = team
        self.state = state
        self.role_position = role_position
        self.match_time = match_time
        self.is_home_team = is_home_team
        self.debugger = debugger
        self.current_target = current_target
        self.player_role = player_role
        self.role_behaviour = create_role_behaviour(self.player_role)
        self.player_role = self.role_behaviour.role
        self.last_save_log_time = -1000.0
        self.pending_save_target: Optional[Vector2D] = None
        self.pending_save_eta: float = float("inf")
        self.off_ball_state: str = "idle"

    def update_ai(self, ball: BallState, dt: float, all_players: List["PlayerMatchState"]) -> None:
        """Update AI behaviour for the player."""
        self.match_time += dt

