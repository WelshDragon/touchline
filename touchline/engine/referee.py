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
    from touchline.engine.physics import BallState, Pitch
    from touchline.utils.debug import MatchDebugger


@dataclass(slots=True)
class RefereeDecision:
    """Outcome returned by the referee after reviewing play."""

    event: Literal["goal", "out", "none"]
    team: Optional[str] = None

    @property
    def is_goal(self) -> bool:
        return self.event == "goal"

    @property
    def is_ball_out(self) -> bool:
        return self.event == "out"


class Referee:
    """Game official responsible for monitoring match state.

    For now the referee only adjudicates goals by reviewing when the
    ball crosses the goal line. Additional responsibilities (fouls,
    offsides, cards, etc.) can be layered on later without touching the
    core match engine logic.
    """

    def __init__(self, pitch: "Pitch", debugger: Optional["MatchDebugger"] = None) -> None:
        self.pitch = pitch
        self.debugger = debugger

    def observe_ball(self, ball: "BallState", current_time: float = 0.0) -> RefereeDecision:
        """Inspect the ball state and issue decisions when needed."""
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

        if self.debugger:
            self.debugger.log_match_event(current_time, "referee", "Ball left play – awarding restart")
        return RefereeDecision("out")
