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
import inspect
import math
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

from touchline.utils.debug import MatchDebugger

from .config import ENGINE_CONFIG


@dataclass
class Vector2D:
    x: float
    y: float

    def __add__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vector2D":
        return Vector2D(self.x * scalar, self.y * scalar)

    def magnitude(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def normalize(self) -> "Vector2D":
        mag = self.magnitude()
        if mag == 0:
            return Vector2D(0, 0)
        return Vector2D(self.x / mag, self.y / mag)

    def distance_to(self, other: "Vector2D") -> float:
        return (other - self).magnitude()


@dataclass
class PlayerState:
    position: Vector2D
    velocity: Vector2D
    stamina: float  # Current stamina level (0-100)
    is_with_ball: bool = False

    def move_towards(self, target: Vector2D, dt: float, max_speed: float) -> None:
        """Move player towards target position."""
        direction = (target - self.position).normalize()
        cfg = ENGINE_CONFIG.player_movement
        # Adjust speed based on stamina
        current_max_speed = max_speed * (self.stamina / 100)
        self.velocity = direction * current_max_speed
        self.position = self.position + self.velocity * dt

        # REDUCED: Stamina drain from 2.0 to 0.8 (60% reduction)
        # Was draining 0.75%/sec, now drains ~0.30%/sec at full speed
        stamina_drain = (self.velocity.magnitude() / max_speed) * dt * cfg.stamina_drain_factor
        self.stamina = max(0, self.stamina - stamina_drain)

    def recover_stamina(self, dt: float) -> None:
        """Recover stamina when not sprinting."""
        cfg = ENGINE_CONFIG.player_movement
        if self.velocity.magnitude() < cfg.recovery_threshold:  # When almost stationary
            self.stamina = min(100, self.stamina + dt * cfg.recovery_rate)  # Recover stamina when resting


class BallState:
    """Ball state with instrumented position/velocity to trace writes.

    position and velocity are exposed as properties. Any write is logged
    through an attached MatchDebugger (if present) along with a short
    caller location (function, file, line) to help track the origin of
    unexpected mutations.
    """

    def __init__(
        self,
        position: Vector2D,
        velocity: Vector2D,
        last_touched_time: float = 0.0,
        last_touched_by: Optional[int] = None,
        last_kick_recipient: Optional[int] = None,
        debugger: Optional[MatchDebugger] = None,
    ) -> None:
        self._position = position
        self._velocity = velocity
        self.last_touched_time = last_touched_time
        self.last_touched_by = last_touched_by
        self.last_kick_recipient = last_kick_recipient
        self.debugger = debugger
        self.recent_pass_pairs: deque[tuple[int, int]] = deque(maxlen=12)

    # --- instrumented properties -------------------------------------------------
    @property
    def position(self) -> Vector2D:
        return self._position

    @position.setter
    def position(self, value: Vector2D) -> None:
        self._position = value
        self._log_write("position", (value.x, value.y))

    @property
    def velocity(self) -> Vector2D:
        return self._velocity

    @velocity.setter
    def velocity(self, value: Vector2D) -> None:
        self._velocity = value
        self._log_write("velocity", (value.x, value.y))

    def _log_write(self, field: str, value: tuple[float, float]) -> None:
        if not self.debugger:
            return
        # Inspect the stack to find a concise caller location (skip our own frames)
        stack = inspect.stack()
        # Prefer the frame two levels up if available (caller of the writer)
        caller_frame = stack[2] if len(stack) > 2 else stack[1]
        fname = caller_frame.filename
        lineno = caller_frame.lineno
        func = caller_frame.function
        desc = f"Ball {field} write -> ({value[0]:.2f},{value[1]:.2f}) by {func} at {fname}:{lineno}"
        # Use 0.0 as match_time for these internal traces (engine will correlate by time)
        try:
            self.debugger.log_match_event(0.0, "debug", desc)
        except Exception:
            # Never let logging instrumentation raise during simulation
            pass

    # --- physics operations ------------------------------------------------------
    def update(self, dt: float, friction: Optional[float] = None) -> None:
        """Update ball position and apply friction."""
        if friction is None:
            friction = ENGINE_CONFIG.ball_physics.friction
        # Update position with current velocity
        new_position = self.position + self.velocity * dt
        self.position = new_position

        # Apply friction (air resistance)
        speed = self.velocity.magnitude()
        if speed > 0:
            # Stronger friction at higher speeds
            friction_force = friction ** (dt * (1 + speed / 20))
            self.velocity = self.velocity * friction_force

            # Stop very slow movement
            if self.velocity.magnitude() < ENGINE_CONFIG.ball_physics.stop_threshold:
                self.velocity = Vector2D(0, 0)

    def kick(
        self,
        direction: Vector2D,
        power: float,
        player_id: int,
        current_time: float,
        recipient_id: Optional[int] = None,
    ) -> None:
        """Apply kick force to the ball."""
        # Only allow kicks if enough time has passed since last touch
        # or the player who last touched the ball is the one kicking.
        # (Previous logic used `!=` here which allowed other players to
        # kick the ball immediately — that was a bug.)
        if current_time - self.last_touched_time > 0.5 or self.last_touched_by == player_id:
            self.velocity = direction.normalize() * power
            self.last_touched_time = current_time
            self.last_touched_by = player_id
            # Optionally store the intended recipient (for passes)
            self.last_kick_recipient = recipient_id
            if recipient_id is not None:
                self.recent_pass_pairs.append((player_id, recipient_id))
            # Log kick details if a debugger was attached
            if self.debugger:
                msg = (
                    f"Kick: player {player_id} power={power:.1f} "
                    f"recipient={recipient_id} -> vel=({self.velocity.x:.2f},{self.velocity.y:.2f})"
                )
                self.debugger.log_match_event(current_time, "kick", msg)


class Pitch:
    def __init__(self, width: Optional[float] = None, height: Optional[float] = None) -> None:
        """Initialize pitch with FIFA standard dimensions (in meters)."""
        cfg = ENGINE_CONFIG.pitch
        self.width = width if width is not None else cfg.width
        self.height = height if height is not None else cfg.height
        self.goal_width = cfg.goal_width

        # Define key areas
        self.penalty_area_width = cfg.penalty_area_width
        self.penalty_area_depth = cfg.penalty_area_depth
        self.goal_area_width = cfg.goal_area_width
        self.goal_area_depth = cfg.goal_area_depth

    def is_in_bounds(self, position: Vector2D) -> bool:
        """Check if position is within pitch boundaries."""
        return -self.width / 2 <= position.x <= self.width / 2 and -self.height / 2 <= position.y <= self.height / 2

    def is_goal(self, position: Vector2D) -> Tuple[bool, str]:
        """Check if ball position results in a goal."""
        if abs(position.x) > self.width / 2:  # Ball crossed goal line
            if abs(position.y) <= self.goal_width / 2:  # Within goal posts
                # Negative X is the home team's own goal, so the away team scores.
                return True, "away" if position.x < 0 else "home"
        return False, ""

    def constrain_to_bounds(self, position: Vector2D) -> Vector2D:
        """Constrain position to pitch boundaries."""
        return Vector2D(
            max(-self.width / 2, min(self.width / 2, position.x)),
            max(-self.height / 2, min(self.height / 2, position.y)),
        )
