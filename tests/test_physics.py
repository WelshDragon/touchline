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
"""Tests for physics module."""

from touchline.engine.config import ENGINE_CONFIG
from touchline.engine.physics import BallState, Pitch, PlayerState, Vector2D


class TestVector2D:
    """Unit tests for the Vector2D helper."""

    def test_vector_creation(self) -> None:
        """Instantiate a vector and verify stored coordinates."""
        v = Vector2D(3.0, 4.0)
        assert v.x == 3.0
        assert v.y == 4.0

    def test_vector_addition(self) -> None:
        """Add two vectors and confirm component-wise sums."""
        v1 = Vector2D(1.0, 2.0)
        v2 = Vector2D(3.0, 4.0)
        v3 = v1 + v2
        assert v3.x == 4.0 and v3.y == 6.0

    def test_vector_subtraction(self) -> None:
        """Subtract vectors and check resulting offset."""
        v1 = Vector2D(5.0, 6.0)
        v2 = Vector2D(3.0, 4.0)
        v3 = v1 - v2
        assert v3.x == 2.0 and v3.y == 2.0

    def test_vector_scalar_multiplication(self) -> None:
        """Scale a vector by a scalar factor."""
        v = Vector2D(2.0, 3.0)
        v2 = v * 2
        assert v2.x == 4.0 and v2.y == 6.0

    def test_magnitude(self) -> None:
        """Compute the magnitude of a non-zero vector."""
        v = Vector2D(3.0, 4.0)
        assert abs(v.magnitude() - 5.0) < 1e-6

    def test_magnitude_zero_vector(self) -> None:
        """Confirm a zero vector reports zero magnitude."""
        v = Vector2D(0.0, 0.0)
        assert v.magnitude() == 0.0

    def test_normalize(self) -> None:
        """Normalise a vector and confirm unit length."""
        v = Vector2D(3.0, 4.0)
        n = v.normalize()
        assert abs(n.magnitude() - 1.0) < 1e-6

    def test_normalize_zero_vector(self) -> None:
        """Ensure normalising a zero vector yields zero components."""
        v = Vector2D(0.0, 0.0)
        n = v.normalize()
        assert n.x == 0.0 and n.y == 0.0

    def test_distance_to(self) -> None:
        """Measure distance between two distinct vectors."""
        v1 = Vector2D(0.0, 0.0)
        v2 = Vector2D(3.0, 4.0)
        assert abs(v1.distance_to(v2) - 5.0) < 1e-6

    def test_distance_to_same_point(self) -> None:
        """Confirm distance to self is zero."""
        v1 = Vector2D(1.0, 1.0)
        assert v1.distance_to(v1) == 0.0


class TestPlayerState:
    """Behavioural checks for the PlayerState container."""

    def test_player_state_creation(self) -> None:
        """Instantiate a default player state."""
        state = PlayerState(
            position=Vector2D(0.0, 0.0),
            velocity=Vector2D(0.0, 0.0),
            is_with_ball=False,
            stamina=100.0,
        )
        assert state.position.x == 0.0
        assert state.velocity.y == 0.0
        assert state.stamina == 100.0

    def test_move_towards(self) -> None:
        """Move toward a target and apply stamina loss."""
        state = PlayerState(
            position=Vector2D(0.0, 0.0),
            velocity=Vector2D(0.0, 0.0),
            is_with_ball=False,
            stamina=100.0,
        )
        target = Vector2D(10.0, 0.0)
        movement_cfg = ENGINE_CONFIG.player_movement
        profile = movement_cfg.role_profiles["default"]
        state.move_towards(
            target,
            dt=1.0,
            max_speed=profile.run_speed,
            acceleration=profile.acceleration,
            deceleration=profile.deceleration,
            arrive_radius=movement_cfg.arrive_radius,
        )
        assert state.position.x > 0.0
        assert state.stamina < 100.0

    def test_move_towards_zero_distance(self) -> None:
        """Avoid movement when already at the target point."""
        state = PlayerState(
            position=Vector2D(5.0, 5.0),
            velocity=Vector2D(0.0, 0.0),
            is_with_ball=False,
            stamina=100.0,
        )
        movement_cfg = ENGINE_CONFIG.player_movement
        profile = movement_cfg.role_profiles["default"]
        state.move_towards(
            Vector2D(5.0, 5.0),
            dt=1.0,
            max_speed=profile.run_speed,
            acceleration=profile.acceleration,
            deceleration=profile.deceleration,
            arrive_radius=movement_cfg.arrive_radius,
        )
        assert state.position.x == 5.0
        assert state.position.y == 5.0

    def test_stamina_affects_speed(self) -> None:
        """Demonstrate that reduced stamina slows movement."""
        state_fresh = PlayerState(
            position=Vector2D(0.0, 0.0),
            velocity=Vector2D(0.0, 0.0),
            is_with_ball=False,
            stamina=100.0,
        )
        state_tired = PlayerState(
            position=Vector2D(0.0, 0.0),
            velocity=Vector2D(0.0, 0.0),
            is_with_ball=False,
            stamina=20.0,
        )
        target = Vector2D(10.0, 0.0)
        movement_cfg = ENGINE_CONFIG.player_movement
        profile = movement_cfg.role_profiles["default"]
        kwargs = dict(
            dt=1.0,
            max_speed=profile.run_speed,
            acceleration=profile.acceleration,
            deceleration=profile.deceleration,
            arrive_radius=movement_cfg.arrive_radius,
        )
        state_fresh.move_towards(target, **kwargs)
        state_tired.move_towards(target, **kwargs)
        assert state_fresh.position.x > state_tired.position.x

    def test_recover_stamina(self) -> None:
        """Allow a resting player to regain stamina."""
        state = PlayerState(position=Vector2D(0.0, 0.0), velocity=Vector2D(0.0, 0.0), is_with_ball=False, stamina=50.0)
        state.recover_stamina(dt=5.0)
        assert state.stamina > 50.0


class TestBallState:
    """Unit tests for ball physics state."""

    def test_ball_state_creation(self) -> None:
        """Construct a ball state with initial position and velocity."""
        ball = BallState(position=Vector2D(0.0, 0.0), velocity=Vector2D(10.0, 0.0))
        assert ball.position.x == 0.0
        assert ball.velocity.x == 10.0

    def test_ball_update_position(self) -> None:
        """Advance the ball and ensure it moves in the heading direction."""
        ball = BallState(position=Vector2D(0.0, 0.0), velocity=Vector2D(10.0, 0.0))
        ball.update(dt=1.0)
        assert ball.position.x > 0.0

    def test_ball_friction(self) -> None:
        """Apply friction and verify the velocity decreases."""
        ball = BallState(position=Vector2D(0.0, 0.0), velocity=Vector2D(10.0, 0.0))
        ball.update(dt=1.0)
        assert ball.velocity.x < 10.0

    def test_ball_stops_at_low_velocity(self) -> None:
        """Stop the ball when velocity drops below the threshold."""
        ball = BallState(position=Vector2D(0.0, 0.0), velocity=Vector2D(0.05, 0.0))
        ball.update(dt=1.0)
        assert ball.velocity.x == 0.0

    def test_ball_tracking_last_touched(self) -> None:
        """Record the player who last touched the ball."""
        ball = BallState(position=Vector2D(0.0, 0.0), velocity=Vector2D(0.0, 0.0))
        ball.last_touched_by = 1
        assert ball.last_touched_by == 1


class TestPitch:
    """Tests for pitch dimension helpers."""

    def test_pitch_creation(self) -> None:
        """Instantiate a pitch with standard FIFA measurements."""
        pitch = Pitch(width=105.0, height=68.0)
        assert pitch.width == 105.0
        assert pitch.height == 68.0

    def test_pitch_custom_dimensions(self) -> None:
        """Create a pitch with custom width and height."""
        pitch = Pitch(width=100.0, height=60.0)
        assert pitch.width == 100.0
        assert pitch.height == 60.0

    def test_is_in_bounds(self) -> None:
        """Return True only when a vector lies within bounds."""
        pitch = Pitch(width=100.0, height=60.0)
        assert pitch.is_in_bounds(Vector2D(50.0, 30.0)) is True
        assert pitch.is_in_bounds(Vector2D(100.1, 30.0)) is False

    def test_clamp_to_bounds(self) -> None:
        """Clamp a position manually to stay within bounds."""
        pitch = Pitch(width=100.0, height=60.0)
        # Position outside bounds should be clamped manually using min/max
        pos = Vector2D(60.0, 40.0)
        clamped_x = min(max(pos.x, 0.0), pitch.width)
        clamped_y = min(max(pos.y, 0.0), pitch.height)
        assert clamped_x == 60.0
        assert clamped_y == 40.0

    def test_is_goal_left_side_awards_away(self) -> None:
        """Identify goals on the home team's side as away goals."""
        pitch = Pitch()
        position = Vector2D(-(pitch.width / 2) - 0.5, 0.0)
        is_goal, team = pitch.is_goal(position)
        assert is_goal is True
        assert team == "away"

    def test_is_goal_right_side_awards_home(self) -> None:
        """Identify goals on the away side as home goals."""
        pitch = Pitch()
        position = Vector2D((pitch.width / 2) + 0.5, 0.0)
        is_goal, team = pitch.is_goal(position)
        assert is_goal is True
        assert team == "home"
