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
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Deque, List, Optional, TextIO, Tuple


@dataclass
class DebugEvent:
    timestamp: float
    event_type: str
    details: str


class MatchDebugger:
    def __init__(self, output_dir: str = "debug_logs") -> None:
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
        """Log the current state of the ball."""
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
        target: tuple[float, float] | None = None,
        player_role: str | None = None,
    ) -> None:
        """Log the current state of a player."""
        target_str = f" | Target: ({target[0]:.1f}, {target[1]:.1f})" if target else ""
        role_str = f" | Role: {player_role}" if player_role else ""
        self._write_log(
            "PLAYER_STATE",
            f"Time: {match_time:.1f}s | "
            f"Player {player_id} ({team_name}){role_str} | "
            f"Pos: ({position[0]:.1f}, {position[1]:.1f}) | "
            f"Has Ball: {has_ball} | "
            f"Stamina: {stamina:.1f}"
            f"{target_str}",
        )

    def log_match_event(self, match_time: float, event_type: str, description: str) -> None:
        """Log a match event (goal, shot, etc.)."""
        self._write_log("MATCH_EVENT", f"Time: {match_time:.1f}s | Event: {event_type} | Details: {description}")

    def log_error(self, error_type: str, description: str) -> None:
        """Log an error or warning."""
        self._write_log("ERROR", f"Type: {error_type} | Details: {description}")

    def _write_log(self, event_type: str, details: str) -> None:
        """Write a log entry to the file."""
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
        """Return the latest debug entries with line numbers for live displays."""
        with self._lock:
            selected = list(self._recent_events)[-limit:]
        return [f"{line_no:05d} {entry}" for line_no, entry in selected]

    def close(self) -> None:
        """Close the log file."""
        if self.log_file:
            self.log_file.close()
            self.log_file = None
