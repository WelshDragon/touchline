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
"""Simple referee implementation to oversee match events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from touchline.engine.physics import BallState, Pitch, Vector2D
    from touchline.utils.debug import MatchDebugger


@dataclass(slots=True)
class RefereeDecision:
    """Structured ruling describing the referee's interpretation of the last phase.

    Parameters
    ----------
    event : Literal["goal", "out", "none"]
        Canonical label for what occurred.
    team : str | None, optional
        Name of the team credited with the outcome when relevant (for example, the scoring side).
    restart_type : Literal["goal_kick", "throw_in", "corner"] | None, optional
        Identifier for the restart the referee awards after the stoppage.
    awarded_side : str | None, optional
        Side (``"home"`` or ``"away"``) that receives the restart.
    restart_spot : Vector2D | None, optional
        Ball location where play should resume.

    """

    event: Literal["goal", "out", "none"]
    team: Optional[str] = None
    restart_type: Optional[Literal["goal_kick", "throw_in", "corner"]] = None
    awarded_side: Optional[str] = None
    restart_spot: Optional["Vector2D"] = None

    @property
    def is_goal(self) -> bool:
        """Return ``True`` when the decision represents a goal being scored."""
        return self.event == "goal"

    @property
    def is_ball_out(self) -> bool:
        """Return ``True`` when the ball has left the pitch but no goal was scored."""
        return self.event == "out"

    @property
    def has_restart(self) -> bool:
        """Return ``True`` when a restart (goal kick, throw-in, corner) must be taken."""
        return self.restart_type is not None


class Referee:
    """Game official responsible for evaluating ball state and issuing rulings.

    The referee is intentionally lightweight: it determines whether the ball
    has left the pitch, resolves which team deserves possession, and records
    goals. Future match rules (fouls, offsides, card discipline) can be layered
    on top without touching the rest of the engine.

    Parameters
    ----------
    pitch : Pitch
        Pitch instance defining the playable area and goal dimensions.
    debugger : MatchDebugger | None, optional
        Optional logging helper used to emit structured debug events.
    """

    def __init__(self, pitch: "Pitch", debugger: Optional["MatchDebugger"] = None) -> None:
        """Create a referee linked to a pitch geometry and optional debugger.

        Parameters
        ----------
        pitch : Pitch
            Pitch instance defining the playable area and goal dimensions.
        debugger : MatchDebugger | None, optional
            Optional logging helper used to emit structured debug events when
            the referee makes a decision.

        """
        self.pitch = pitch
        self.debugger = debugger

    def observe_ball(
        self,
        ball: "BallState",
        current_time: float = 0.0,
        *,
        last_touch_side: Optional[str] = None,
        possession_side: Optional[str] = None,
    ) -> RefereeDecision:
        """Inspect the ball state and issue decisions when the ball leaves play.

        Parameters
        ----------
        ball : BallState
            Current state of the match ball.
        current_time : float, optional
            Simulation timestamp when the observation occurs.
        last_touch_side : str | None, optional
            Which side last touched the ball. Used to resolve corners vs goal
            kicks and to determine who committed a touch-line violation.
        possession_side : str | None, optional
            Team currently considered to be in possession when the ball leaves
            play. Acts as a tie-breaker when the last toucher cannot be
            determined (for example due to simultaneous touches).

        Returns
        -------
        RefereeDecision
            Rich description of the ruling: whether a goal was scored, what
            restart is awarded, and where play should resume.

        """
        if self.pitch.is_in_bounds(ball.position):
            return RefereeDecision("none")

        is_goal, team = self.pitch.is_goal(ball.position)
        if is_goal:
            if self.debugger:
                self.debugger.log_match_event(
                    current_time,
                    "referee",
                    f"Goal awarded to {team} after ball crossed the line",
                )
            return RefereeDecision("goal", team)

        restart_type: Optional[Literal["goal_kick", "throw_in", "corner"]] = None
        awarded_side: Optional[str] = None

        half_width = self.pitch.width / 2
        half_height = self.pitch.height / 2
        position = ball.position
        restart_spot = position

        if abs(position.x) > half_width:  # crossed goal line
            defending_side = "home" if position.x < 0 else "away"
            attacking_side = "away" if defending_side == "home" else "home"

            if last_touch_side is None:
                restart_type = "goal_kick"
                awarded_side = defending_side
            elif last_touch_side == attacking_side:
                restart_type = "goal_kick"
                awarded_side = defending_side
            else:
                restart_type = "corner"
                awarded_side = attacking_side
        elif abs(position.y) > half_height:  # touchline -> throw-in
            if last_touch_side == "home":
                awarded_side = "away"
            elif last_touch_side == "away":
                awarded_side = "home"
            else:
                awarded_side = possession_side or "home"
            restart_type = "throw_in"

        if restart_type and self.debugger:
            self.debugger.log_match_event(
                current_time,
                "referee",
                f"Restart awarded: {restart_type} to {awarded_side}",
            )

        return RefereeDecision("out", restart_type=restart_type, awarded_side=awarded_side, restart_spot=restart_spot)
