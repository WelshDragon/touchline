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
"""Structured logging utilities used to trace match simulations."""
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Deque, List, Optional, TextIO, Tuple


@dataclass
class DebugEvent:
    """Immutable record representing a single logged event.

    Parameters
    ----------
    timestamp : float
        Simulation time (in seconds) when the event was recorded.
    event_type : str
        Category label describing the event, for example ``"GOAL"``.
    details : str
        Human-readable description providing additional context.
    """

    timestamp: float
    event_type: str
    details: str


class MatchDebugger:
    """Helper object that streams structured match telemetry to disk.

    Parameters
    ----------
    output_dir : str, default="debug_logs"
        Directory where new session logs are created; created automatically when missing.
    """

    def __init__(self, output_dir: str = "debug_logs") -> None:
        """Initialise the debugger and start the first logging session.

        Parameters
        ----------
        output_dir : str
            Filesystem directory where log files are created or appended.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.log_file: Optional[TextIO] = None
        self.session_start = time.strftime("%Y%m%d_%H%M%S")
        self._lock = Lock()
        self._line_number = 1
        self._recent_events: Deque[Tuple[int, str]] = deque(maxlen=200)
        self.start_new_session()

    def start_new_session(self) -> None:
        """Start a new debug logging session."""
        if self.log_file:
            self.log_file.close()

        filename = f"match_debug_{self.session_start}.txt"
        self.log_file = open(self.output_dir / filename, "w", encoding="utf-8")
        self.log_file.write(f"=== Match Debug Session: {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")

    def log_ball_state(
        self,
        match_time: float,
        position: tuple[float, float],
        velocity: tuple[float, float],
        possession_team: str | None = None,
    ) -> None:
        """Log the current state of the ball.

        Parameters
        ----------
        match_time : float
            Elapsed match time in seconds.
        position : tuple[float, float]
            Ball coordinates on the pitch (x, y).
        velocity : tuple[float, float]
            Current velocity in metres per second along x and y axes.
        possession_team : str | None
            Identifier for the side deemed to have possession, when known.
        """
        possession_str = f" | Possession: {possession_team}" if possession_team else ""
        self._write_log(
            "BALL_STATE",
            f"Time: {match_time:.1f}s | "
            f"Pos: ({position[0]:.1f}, {position[1]:.1f}) | "
            f"Vel: ({velocity[0]:.1f}, {velocity[1]:.1f})"
            f"{possession_str}",
        )

    def log_player_state(
        self,
        match_time: float,
        player_id: int,
        team_name: str,
        position: tuple[float, float],
        has_ball: bool,
        stamina: float = 100.0,
        velocity: tuple[float, float] | None = None,
        speed: float | None = None,
        target: tuple[float, float] | None = None,
        player_role: str | None = None,
    ) -> None:
        """Log the current state of a player.

        Parameters
        ----------
        match_time : float
            Elapsed match time in seconds.
        player_id : int
            Identifier of the tracked player.
        team_name : str
            Label for the player's team.
        position : tuple[float, float]
            Player coordinates (x, y) in metres.
        has_ball : bool
            Whether the player currently controls the ball.
        stamina : float
            Remaining stamina level expressed as a percentage.
        velocity : tuple[float, float] | None
            Optional instantaneous velocity vector in metres per second.
        speed : float | None
            Optional scalar magnitude of the player's velocity.
        target : tuple[float, float] | None
            Optional target position the player is attempting to reach.
        player_role : str | None
            Tactical role identifier (for example ``"CM"``) if available.
        """
        target_str = f" | Target: ({target[0]:.1f}, {target[1]:.1f})" if target else ""
        role_str = f" | Role: {player_role}" if player_role else ""
        velocity_str = ""
        if velocity is not None:
            velocity_str = f" | Vel: ({velocity[0]:.2f}, {velocity[1]:.2f}) m/s"
        if speed is not None:
            velocity_str += f" | Speed: {speed:.2f} m/s"
        self._write_log(
            "PLAYER_STATE",
            f"Time: {match_time:.1f}s | "
            f"Player {player_id} ({team_name}){role_str} | "
            f"Pos: ({position[0]:.1f}, {position[1]:.1f}) | "
            f"Has Ball: {has_ball} | "
            f"Stamina: {stamina:.1f}"
            f"{velocity_str}"
            f"{target_str}",
        )

    def log_match_event(self, match_time: float, event_type: str, description: str) -> None:
        """Log a match event (goal, shot, etc.).

        Parameters
        ----------
        match_time : float
            Elapsed match time in seconds.
        event_type : str
            Short label identifying the event category.
        description : str
            Human-readable summary of the event.
        """
        self._write_log("MATCH_EVENT", f"Time: {match_time:.1f}s | Event: {event_type} | Details: {description}")

    def log_error(self, error_type: str, description: str) -> None:
        """Log an error or warning.

        Parameters
        ----------
        error_type : str
            Label describing the error classification.
        description : str
            Human-readable explanation of the issue.
        """
        self._write_log("ERROR", f"Type: {error_type} | Details: {description}")

    def _write_log(self, event_type: str, details: str) -> None:
        """Write a log entry to the file.

        Parameters
        ----------
        event_type : str
            Category label for the log entry.
        details : str
            Formatted message body to persist.
        """
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {event_type}: {details}"

        with self._lock:
            line_no = self._line_number
            self._line_number += 1
            self._recent_events.append((line_no, log_entry))

            if self.log_file:
                self.log_file.write(f"{log_entry}\n")
                self.log_file.flush()

    def get_recent_events(self, limit: int = 20) -> List[str]:
        """Return the latest debug entries with line numbers for live displays.

        Parameters
        ----------
        limit : int
            Maximum number of entries to return.

        Returns
        -------
        List[str]
            Up to ``limit`` most recent log lines with prefixed line numbers.
        """
        with self._lock:
            selected = list(self._recent_events)[-limit:]
        return [f"{line_no:05d} {entry}" for line_no, entry in selected]

    def close(self) -> None:
        """Close the log file."""
        if self.log_file:
            self.log_file.close()
            self.log_file = None
