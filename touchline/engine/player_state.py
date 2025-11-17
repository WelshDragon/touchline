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
    """Snapshot of shared state used across helper methods.

    Instances are short lived; they capture the player under consideration, the
    ball, and cached teammate/opponent lists so repeated decisions avoid
    recomputing filters over the full player collection.

    Parameters
    ----------
    player : PlayerMatchState
        Player currently being evaluated.
    ball : BallState
        Shared ball state for the frame.
    all_players : List[PlayerMatchState]
        Full roster of active player match states.
    """

    player: "PlayerMatchState"
    ball: BallState
    all_players: List["PlayerMatchState"]
    teammates: List["PlayerMatchState"] = field(init=False)
    opponents: List["PlayerMatchState"] = field(init=False)

    def __post_init__(self) -> None:
        """Populate teammate/opponent lists derived from ``all_players``."""
        self.teammates = [p for p in self.all_players if p.team == self.player.team and p != self.player]
        self.opponents = [p for p in self.all_players if p.team != self.player.team]


@dataclass
class PassDecision:
    """Concrete pass choice selected under pressure.

    Parameters
    ----------
    target : PlayerMatchState
        Intended teammate that should receive the pass.
    pass_type : str
        Descriptor for the pass style (for example ``"ground"`` or ``"lob"``).
    power : float
        Kick power applied to the pass.
    score : float
        Heuristic quality score associated with the decision.
    lane_quality : float
        Clearance rating for the passing lane (0-1).
    lead_target : Vector2D
        Anticipated intercept position for the receiver.
    origin : str
        Source identifier for the decision logic, defaults to ``"base"``.
    """

    target: "PlayerMatchState"
    pass_type: str
    power: float
    score: float
    lane_quality: float
    lead_target: Vector2D
    origin: str = "base"


class PlayerMatchState:
    """Runtime state and behaviour for a player participating in a match.

    Parameters
    ----------
    player_id : int
        Identifier that maps back to the static roster entry.
    team : Team
        Team instance the player belongs to.
    state : PlayerState
        Mutable physics state used by the engine integration loop.
    role_position : Vector2D
        Home-half reference position that represents the role's nominal slot.
    match_time : float, optional
        Initial per-player clock, normally aligned with the global timer.
    is_home_team : bool, optional
        Flag used for quick side comparisons.
    debugger : MatchDebugger | None, optional
        Optional debugger for emitting per-player diagnostics.
    current_target : Vector2D | None, optional
        Active navigation waypoint used by role logic.
    player_role : str, optional
        Short role code (for example ``"CM"``) that determines behavioural scripts.
    """

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
        """Create a match state wrapper around a player roster entry.

        Parameters
        ----------
        player_id : int
            Identifier that maps back to the static roster entry.
        team : Team
            Team instance the player belongs to.
        state : PlayerState
            Mutable physics state used by the engine integration loop.
        role_position : Vector2D
            Home-half reference position that represents the role's nominal slot.
        match_time : float, optional
            Initial per-player clock, normally aligned with the global timer.
        is_home_team : bool, optional
            Flag used for quick side comparisons.
        debugger : MatchDebugger | None, optional
            Optional debugger for emitting per-player diagnostics.
        current_target : Vector2D | None, optional
            Active navigation waypoint used by role logic.
        player_role : str, optional
            Short role code that determines behavioural scripts.

        """
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
        self.tempo_hold_until: float = 0.0
        self.tempo_hold_cooldown_until: float = 0.0
        self.space_move_until: float = 0.0
        self.space_move_heading: Optional[Vector2D] = None
        self.space_probe_loops: int = 0
        self.target_source: Optional[str] = None
        self.last_intent_change_time: float = -10.0  # Track when intent last changed

    def update_ai(self, ball: BallState, dt: float, all_players: List["PlayerMatchState"]) -> None:
        """Advance the per-player AI, updating timers and delegating to the role.

        Parameters
        ----------
        ball : BallState
            Current ball state used to inform role behaviour.
        dt : float
            Simulation timestep in seconds since the previous update.
        all_players : List[PlayerMatchState]
            Complete set of match player states used for context.
        """
        self.match_time += dt

