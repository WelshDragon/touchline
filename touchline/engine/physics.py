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
"""Low-level physics primitives used by the match engine.

The physics layer provides a small vector maths helper, player and ball state
containers, and a pitch representation that encodes real-world dimensions. It
encapsulates the raw numeric operations so higher-level systems can focus on AI
and tactical behaviour without reimplementing mechanics.
"""
import inspect
import math
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

from touchline.utils.debug import MatchDebugger

from .config import ENGINE_CONFIG


@dataclass
class Vector2D:
    """Two-dimensional vector with convenience operations.

    The class intentionally mirrors the bare minimum functionality required by
    the simulation: addition/subtraction for positional offsets, scalar
    multiplication for velocity scaling, and helpers for magnitude/normalisation.
    It keeps the code readable without introducing an external maths library.

    Parameters
    ----------
    x : float
        Horizontal component measured in metres.
    y : float
        Vertical component measured in metres.
    """

    x: float
    y: float

    def __add__(self, other: "Vector2D") -> "Vector2D":
        """Return the vector sum of ``self`` and ``other``."""
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2D") -> "Vector2D":
        """Return the vector difference ``self - other``."""
        return Vector2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vector2D":
        """Scale the vector by ``scalar`` while preserving direction."""
        return Vector2D(self.x * scalar, self.y * scalar)

    def magnitude(self) -> float:
        """Return the Euclidean length of the vector.

        Returns
        -------
        float
            Scalar magnitude measured in metres.
        """
        return math.sqrt(self.x * self.x + self.y * self.y)

    def normalize(self) -> "Vector2D":
        """Return a unit vector pointing in the same direction as ``self``.

        Returns
        -------
        Vector2D
            Normalised vector; zero vector when ``self`` has no magnitude.
        """
        mag = self.magnitude()
        if mag == 0:
            return Vector2D(0, 0)
        return Vector2D(self.x / mag, self.y / mag)

    def distance_to(self, other: "Vector2D") -> float:
        """Return the straight-line distance between ``self`` and ``other``.

        Parameters
        ----------
        other : Vector2D
            Vector whose separation from ``self`` should be measured.

        Returns
        -------
        float
            Euclidean distance in metres between the two points.
        """
        return (other - self).magnitude()


@dataclass
class PlayerState:
    """Mutable physics state for a single player during the simulation.

    The match engine stores physical quantities (position, velocity, stamina)
    separately from the higher-level player objects so AI decisions and physics
    integration can evolve independently.

    Parameters
    ----------
    position : Vector2D
        Current position on the pitch.
    velocity : Vector2D
        Current velocity in metres per second.
    stamina : float
        Remaining stamina level expressed as a percentage.
    is_with_ball : bool, optional
        Whether the player currently controls the ball.
    """

    position: Vector2D
    velocity: Vector2D
    stamina: float  # Current stamina level (0-100)
    is_with_ball: bool = False

    def move_towards(
        self,
        target: Vector2D,
        dt: float,
        max_speed: float,
        acceleration: float,
        deceleration: float,
        arrive_radius: float,
    ) -> None:
        """Move the player toward ``target`` applying acceleration constraints.

        Parameters
        ----------
        target : Vector2D
            Desired destination for the player.
        dt : float
            Simulation timestep in seconds since the previous update.
        max_speed : float
            Maximum speed for the movement intent in metres per second.
        acceleration : float
            Maximum allowed acceleration per second.
        deceleration : float
            Maximum allowed deceleration per second.
        arrive_radius : float
            Radius in metres at which the player begins slowing down.
        """
        if dt <= 0:
            return

        cfg = ENGINE_CONFIG.player_movement
        offset = target - self.position
        distance = offset.magnitude()
        stamina_scale = max(0.0, self.stamina / 100)

        # No meaningful direction or movement goal – bleed existing velocity.
        if distance < 1e-4 or max_speed <= 0:
            current_speed = self.velocity.magnitude()
            if current_speed > 0:
                drop = min(current_speed, deceleration * dt)
                remaining = current_speed - drop
                if remaining <= 1e-4:
                    self.velocity = Vector2D(0, 0)
                else:
                    self.velocity = self.velocity.normalize() * remaining

                if max_speed > 0:
                    stamina_drain = (current_speed / max_speed) * dt * cfg.stamina_drain_factor
                    self.stamina = max(0.0, self.stamina - stamina_drain)

            self.position = self.position + self.velocity * dt
            return

        direction = offset.normalize()

        desired_speed = max_speed
        if arrive_radius > 0:
            desired_speed *= min(1.0, distance / arrive_radius)

        # Don't overshoot target in a single step
        max_step_speed = distance / dt
        desired_speed = min(desired_speed, max_step_speed)
        desired_speed = max(0.0, desired_speed * stamina_scale)

        current_speed = self.velocity.magnitude()
        alignment = 1.0
        if current_speed > 1e-6:
            alignment = (self.velocity.x * direction.x + self.velocity.y * direction.y) / current_speed

        effective_speed = current_speed
        if alignment < 0.0:
            # Turning around – shed speed before accelerating in the new direction.
            effective_speed = max(0.0, current_speed - deceleration * dt)

        if desired_speed > effective_speed:
            new_speed = effective_speed + min(desired_speed - effective_speed, acceleration * dt)
        else:
            new_speed = effective_speed - min(effective_speed - desired_speed, deceleration * dt)

        speed_cap = max_speed * stamina_scale
        if speed_cap > 0:
            new_speed = min(new_speed, speed_cap)

        if new_speed <= 1e-4:
            self.velocity = Vector2D(0, 0)
        else:
            self.velocity = direction * new_speed

        self.position = self.position + self.velocity * dt

        if max_speed > 0 and new_speed > 0:
            stamina_drain = (new_speed / max_speed) * dt * cfg.stamina_drain_factor
            self.stamina = max(0.0, self.stamina - stamina_drain)

    def recover_stamina(self, dt: float) -> None:
        """Recover stamina when not sprinting.

        Parameters
        ----------
        dt : float
            Simulation timestep in seconds since the previous update.
        """
        cfg = ENGINE_CONFIG.player_movement
        if self.velocity.magnitude() < cfg.recovery_threshold:  # When almost stationary
            self.stamina = min(100, self.stamina + dt * cfg.recovery_rate)  # Recover stamina when resting


class BallState:
    """Ball state with instrumented position/velocity to trace writes.

    position and velocity are exposed as properties. Any write is logged
    through an attached MatchDebugger (if present) along with a short
    caller location (function, file, line) to help track the origin of
    unexpected mutations.

    Parameters
    ----------
    position : Vector2D
        Initial coordinates of the ball relative to the pitch centre.
    velocity : Vector2D
        Initial velocity vector in metres per second.
    last_touched_time : float, optional
        Simulation timestamp when the ball was last played.
    last_touched_by : int | None, optional
        Player identifier for the last touch, if known.
    last_kick_recipient : int | None, optional
        Intended recipient identifier for the last kick (used for passes).
    debugger : MatchDebugger | None, optional
        Debugger instance used to log instrumentation events when the ball state mutates.
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
        """Create a new ball state with optional instrumentation.

        Parameters
        ----------
        position : Vector2D
            Initial coordinates of the ball relative to the pitch centre.
        velocity : Vector2D
            Initial velocity vector in metres per second.
        last_touched_time : float, optional
            Simulation timestamp when the ball was last played.
        last_touched_by : int | None, optional
            Player identifier for the last touch, if known.
        last_kick_recipient : int | None, optional
            Intended recipient identifier for the last kick (used for passes).
        debugger : MatchDebugger | None, optional
            Debugger used to log instrumentation events when the ball state mutates.

        """
        self._position = position
        self._velocity = velocity
        self.last_touched_time = last_touched_time
        self.last_touched_by = last_touched_by
        self.last_kick_recipient = last_kick_recipient
        self.debugger = debugger
        self.recent_pass_pairs: deque[tuple[int, int]] = deque(maxlen=12)
        self.is_airborne = False
        self.time_until_ground = 0.0
        self.just_bounced = False
        self._log_match_time = 0.0
        self.possessing_team_side: Optional[str] = None  # "home", "away", or None

    # --- instrumented properties -------------------------------------------------
    @property
    def position(self) -> Vector2D:
        """Return the current ball position."""
        return self._position

    @position.setter
    def position(self, value: Vector2D) -> None:
        """Update the ball position and emit a debug trace if enabled."""
        self._position = value
        self._log_write("position", (value.x, value.y))

    @property
    def velocity(self) -> Vector2D:
        """Return the ball's velocity vector."""
        return self._velocity

    @velocity.setter
    def velocity(self, value: Vector2D) -> None:
        """Update the ball velocity and ground it if it fully stops."""
        self._velocity = value
        self._log_write("velocity", (value.x, value.y))
        if value.x == 0 and value.y == 0:
            self.ground()

    def set_log_match_time(self, match_time: float) -> None:
        """Update the timestamp used when emitting debug write events.

        Parameters
        ----------
        match_time : float
            Match clock timestamp applied to subsequent log entries.
        """
        self._log_match_time = match_time

    def _log_write(self, field: str, value: tuple[float, float]) -> None:
        """Emit a debugger trace describing a write to ``field``.

        Parameters
        ----------
        field : str
            Name of the BallState property being modified (for example ``"position"``).
        value : tuple[float, float]
            Snapshot of the written value encoded as a 2-D tuple for logging.
        """
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
        try:
            self.debugger.log_match_event(self._log_match_time, "debug", desc)
        except Exception:
            # Never let logging instrumentation raise during simulation
            pass

    # --- physics operations ------------------------------------------------------
    def update(self, dt: float, friction: Optional[float] = None) -> None:
        """Update ball position and apply friction.

        Parameters
        ----------
        dt : float
            Simulation timestep in seconds since the previous update.
        friction : float | None, optional
            Override for friction coefficient; defaults to configuration.
        """
        if friction is None:
            friction = ENGINE_CONFIG.ball_physics.friction
        cfg = ENGINE_CONFIG.ball_physics
        # Update position with current velocity
        new_position = self.position + self.velocity * dt
        self.position = new_position

        # Apply friction (air resistance)
        speed = self.velocity.magnitude()
        if speed > 0:
            # Stronger friction at higher speeds
            friction_force = friction ** (dt * (1 + speed / 20))
            self.velocity = self.velocity * friction_force

        speed = self.velocity.magnitude()
        if self.is_airborne:
            self.time_until_ground = max(0.0, self.time_until_ground - dt)
            if self.time_until_ground == 0.0:
                self._apply_bounce()
                speed = self.velocity.magnitude()

        if not self.is_airborne and speed > 0:
            ground_drag = max(0.0, 1 - cfg.ground_drag * dt)
            self.velocity = self.velocity * ground_drag

        # Stop very slow movement and treat as settled
        if self.velocity.magnitude() < cfg.stop_threshold:
            self.velocity = Vector2D(0, 0)
            self.ground()

    def kick(
        self,
        direction: Vector2D,
        power: float,
        player_id: int,
        current_time: float,
        recipient_id: Optional[int] = None,
        *,
        kicker_position: Optional[Vector2D] = None,
    ) -> None:
        """Apply kick force to the ball.

        Parameters
        ----------
        direction : Vector2D
            Direction vector representing the intended travel path.
        power : float
            Magnitude of the kick in metres per second.
        player_id : int
            Identifier of the player performing the kick.
        current_time : float
            Simulation timestamp when the kick occurred.
        recipient_id : int | None, optional
            Intended receiving player identifier for pass tracking.
        kicker_position : Vector2D | None, optional
            Origin position of the kick used for debug logging.
        """
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
                distance_text = ""
                if kicker_position is not None:
                    distance = kicker_position.distance_to(self.position)
                    distance_text = f" distance={distance:.2f}m"
                msg = (
                    f"Kick: player {player_id} power={power:.1f} "
                    f"recipient={recipient_id} -> vel=({self.velocity.x:.2f},{self.velocity.y:.2f})"
                    f"{distance_text}"
                )
                self.debugger.log_match_event(current_time, "kick", msg)

            speed = self.velocity.magnitude()
            cfg = ENGINE_CONFIG.ball_physics
            if speed >= cfg.airborne_speed_threshold:
                self.is_airborne = True
                excess = speed - cfg.airborne_speed_threshold
                flight_time = excess * cfg.airborne_time_scale
                self.time_until_ground = min(cfg.airborne_time_max, flight_time)
                self.just_bounced = False
            else:
                self.ground()

    def ground(self) -> None:
        """Mark the ball as in contact with the ground."""
        self.is_airborne = False
        self.time_until_ground = 0.0
        self.just_bounced = False

    def _apply_bounce(self) -> None:
        """Dampen velocity when the ball returns to the ground."""
        cfg = ENGINE_CONFIG.ball_physics
        speed = self.velocity.magnitude()
        if speed <= 0:
            self.ground()
            return

        damped_speed = speed * cfg.bounce_damping
        if damped_speed < cfg.bounce_stop_speed:
            self.velocity = Vector2D(0, 0)
            self.ground()
        else:
            direction = self.velocity.normalize()
            self.velocity = direction * damped_speed
            self.is_airborne = False
            self.just_bounced = True


class Pitch:
    """Rectangular playing surface with goal metadata.

    The pitch exposes helpers to determine whether the ball remains in play,
    whether a goal has been scored, and to clamp positions to legal bounds.
    All measurements use metres to align with FIFA regulations.

    Parameters
    ----------
    width : float | None, optional
        Pitch width override in metres; defaults to configuration.
    height : float | None, optional
        Pitch height override in metres; defaults to configuration.
    """

    def __init__(self, width: Optional[float] = None, height: Optional[float] = None) -> None:
        """Initialise pitch with FIFA standard dimensions (in metres).

        Parameters
        ----------
        width : float | None, optional
            Pitch width override in metres; defaults to configuration.
        height : float | None, optional
            Pitch height override in metres; defaults to configuration.
        """
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
        """Check if position is within pitch boundaries.

        Parameters
        ----------
        position : Vector2D
            Location to check for boundary compliance.

        Returns
        -------
        bool
            ``True`` when the position is inside the legal playing area.
        """
        return -self.width / 2 <= position.x <= self.width / 2 and -self.height / 2 <= position.y <= self.height / 2

    def is_goal(self, position: Vector2D) -> Tuple[bool, str]:
        """Check if ball position results in a goal.

        Parameters
        ----------
        position : Vector2D
            Ball position to evaluate against goal boundaries.

        Returns
        -------
        Tuple[bool, str]
            Tuple of goal flag and scoring side (``"home"`` or ``"away"``) when applicable.
        """
        if abs(position.x) > self.width / 2:  # Ball crossed goal line
            if abs(position.y) <= self.goal_width / 2:  # Within goal posts
                # Negative X is the home team's own goal, so the away team scores.
                return True, "away" if position.x < 0 else "home"
        return False, ""

    def constrain_to_bounds(self, position: Vector2D) -> Vector2D:
        """Constrain position to pitch boundaries.

        Parameters
        ----------
        position : Vector2D
            Location to clamp to the playable area.

        Returns
        -------
        Vector2D
            Adjusted position guaranteed to lie within the field limits.
        """
        return Vector2D(
            max(-self.width / 2, min(self.width / 2, position.x)),
            max(-self.height / 2, min(self.height / 2, position.y)),
        )
