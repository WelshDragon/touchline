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
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

from .base import RoleBehaviour

if TYPE_CHECKING:
    from touchline.engine.physics import BallState, Vector2D
    from touchline.engine.player_state import PlayerMatchState
    from touchline.models.player import Player


class GoalkeeperRoleBehaviour(RoleBehaviour):
    """Goalkeeper AI with realistic shot-stopping, positioning, and distribution."""

    def __init__(self) -> None:
        super().__init__(role="GK", side="central")
        self.box_width = 40.32  # Penalty area width
        self.box_depth = 16.5  # Penalty area depth

    def decide_action(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        dt: float,
    ) -> None:
        """Main goalkeeper decision-making logic."""

        player_model: Player = next((p for p in player.team.players if p.player_id == player.player_id), None)
        if not player_model:
            return

        self._current_all_players = all_players

        # Get attributes
        positioning_attr = player_model.attributes.positioning
        speed_attr = player_model.attributes.speed
        decisions_attr = player_model.attributes.decisions

        try:
            if self._move_to_receive_pass(player, ball, speed_attr, dt):
                return

            if self._pursue_loose_ball(player, ball, all_players, speed_attr):
                return

            # Check if goalkeeper has possession
            if self.has_ball_possession(player, ball):
                self._distribute_ball(player, ball, all_players, player_model, player.match_time)
                return

            # Check if ball is in penalty area and needs saving
            if self._is_ball_dangerous(player, ball):
                self._attempt_save(player, ball, speed_attr, dt)
                return

            # Check if should come out to collect ball (sweeper keeper)
            if self._should_collect_ball(player, ball, decisions_attr, all_players):
                self._collect_ball(player, ball, speed_attr, dt)
                return

            # Default: maintain good positioning
            self._position_for_shot(player, ball, positioning_attr, dt)
        finally:
            self._current_all_players = None

    def _compute_save_window(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
    ) -> Optional[Tuple["Vector2D", float]]:
        ball_speed = ball.velocity.magnitude()

        if ball_speed < 3.0:
            return None

        goal_pos = self.get_own_goal_position(player)
        ball_direction = ball.velocity.normalize()
        to_goal = goal_pos - ball.position

        if ball_direction.x * to_goal.x + ball_direction.y * to_goal.y <= 0:
            return None

        goal_sign = -1 if player.is_home_team else 1
        forward_speed = ball.velocity.x * goal_sign

        if forward_speed <= 0.3:
            return None

        distance_to_plane = (player.state.position.x - ball.position.x) * goal_sign

        if distance_to_plane < -0.3:
            return None

        time_to_plane = distance_to_plane / forward_speed

        if time_to_plane < 0 or time_to_plane > 1.05:
            return None

        intercept_pos = ball.position + ball.velocity * time_to_plane
        goal_half_width = 7.32 / 2

        if abs(intercept_pos.y - goal_pos.y) > goal_half_width + 1.4:
            return None

        if abs(intercept_pos.x - goal_pos.x) > self.box_depth + 1.5:
            return None

        return intercept_pos, time_to_plane

    def _is_ball_dangerous(self, player: "PlayerMatchState", ball: "BallState") -> bool:
        """Check if ball poses immediate threat (shot on goal)."""
        save_window = self._compute_save_window(player, ball)

        if not save_window:
            player.pending_save_target = None
            player.pending_save_eta = float("inf")
            return False

        player.pending_save_target, player.pending_save_eta = save_window
        return True

    def _attempt_save(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        speed_attr: int,
        dt: float,
    ) -> None:
        """Attempt to save/intercept the ball."""
        current_time = player.match_time
        ball_speed = ball.velocity.magnitude()

        save_window = self._compute_save_window(player, ball)

        if save_window:
            intercept_target, eta = save_window
            player.pending_save_target, player.pending_save_eta = save_window
        else:
            intercept_target = player.pending_save_target or (ball.position + ball.velocity * 0.2)
            eta = max(0.0, player.pending_save_eta - dt) if player.pending_save_eta != float("inf") else 0.2
            player.pending_save_eta = eta

        # Estimate whether the keeper can reach the intercept point in time.
        base_speed = 6.0 * (0.7 + (speed_attr / 100) * 0.6)
        max_speed = base_speed * 1.4  # sprinting effort for shot stopping
        travel_distance = player.state.position.distance_to(intercept_target)
        time_available = max(eta, dt)
        reachable_distance = max_speed * (time_available + 0.05)  # tiny reaction buffer
        can_reach_window = travel_distance <= reachable_distance + 0.35

        self.move_to_position(player, intercept_target, speed_attr, dt, ball, sprint=True)

        # If close enough, can catch/punch
        distance = self.distance_to_ball(player, ball)
        success = distance < 1.5 or (can_reach_window and eta <= 0.25)

        log_window = eta <= 0.2 or success

        if player.debugger and log_window and (
            success or current_time - getattr(player, "last_save_log_time", -1000.0) > 0.25
        ):
            outcome = "success" if success else "failed"
            if success:
                reason = "secured"
            elif not can_reach_window:
                reason = "unreachable_window"
            else:
                reason = "distance_too_large"
            detail = (
                f"GK {player.player_id} save attempt {outcome}: distance={distance:.2f}m "
                f"ball_speed={ball_speed:.2f}m/s"
            )

            if not success:
                detail += f" threshold=1.50m eta={eta:.2f}s"

            player.debugger.log_match_event(current_time, "save_attempt", detail + f" reason={reason}")
            player.last_save_log_time = current_time

        if success:
            # Stop the ball (save!)
            from touchline.engine.physics import Vector2D

            if can_reach_window:
                player.state.position = intercept_target
            player.state.velocity = Vector2D(0, 0)
            ball.velocity = Vector2D(0, 0)
            if can_reach_window:
                ball.position = intercept_target
            player.state.is_with_ball = True
            ball.last_touched_by = player.player_id
            ball.last_touched_time = current_time
            ball.last_kick_recipient = None
            player.pending_save_target = None
            player.pending_save_eta = float("inf")

    def _should_collect_ball(
        self, player: "PlayerMatchState", ball: "BallState", decisions_attr: int, all_players: List["PlayerMatchState"]
    ) -> bool:
        """Decide if goalkeeper should come out to collect loose ball."""
        goal_pos = self.get_own_goal_position(player)

        # Ball in penalty area
        ball_in_box = abs(ball.position.x - goal_pos.x) < self.box_depth and abs(ball.position.y) < self.box_width / 2

        if not ball_in_box:
            return False

        # Ball is slow (loose ball)
        if ball.velocity.magnitude() > 5:
            return False

        # No opponent too close (based on decisions)
        opponents = self.get_opponents(player, all_players)
        safe_distance = 8 + (decisions_attr / 100) * 5  # Better decisions = more aggressive

        for opp in opponents:
            if opp.state.position.distance_to(ball.position) < safe_distance:
                return False

        return True

    def _collect_ball(self, player: "PlayerMatchState", ball: "BallState", speed_attr: int, dt: float) -> None:
        """Move to collect loose ball."""
        self.move_to_position(player, ball.position, speed_attr, dt, ball, sprint=True)

        # Collect if close
        if self.distance_to_ball(player, ball) < 1.5:
            from touchline.engine.physics import Vector2D

            ball.velocity = Vector2D(0, 0)
            player.state.is_with_ball = True

    def _position_for_shot(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        positioning_attr: int,
        dt: float,
    ) -> None:
        """Position goalkeeper on goal line based on ball position."""
        from touchline.engine.physics import Vector2D

        goal_pos = self.get_own_goal_position(player)

        # Position between ball and goal center while staying in front of the goal line
        goal_to_ball = (ball.position - goal_pos).normalize()

        # Distance from goal line (2-4m depending on positioning attribute)
        goal_distance = 2 + (positioning_attr / 100) * 2

        # Calculate optimal position and clamp to the field side of the goal line
        field_direction = 1.0 if player.is_home_team else -1.0
        optimal_x = goal_pos.x + goal_to_ball.x * goal_distance
        min_offset = 0.8
        if (optimal_x - goal_pos.x) * field_direction < min_offset:
            optimal_x = goal_pos.x + field_direction * min_offset

        # Y position: bisect angle to goal posts
        angle_factor = (ball.position.y - goal_pos.y) * 0.3  # Move across goal
        optimal_y = goal_pos.y + angle_factor

        # Constrain to goal width
        max_y = 3.0  # Don't stray too far from center
        optimal_y = max(-max_y, min(max_y, optimal_y))

        target_pos = Vector2D(optimal_x, optimal_y)

        # Move to position
        self.move_to_position(player, target_pos, 50, dt, ball, sprint=False)

    def _distribute_ball(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        player_model: "Player",
        current_time: float,
    ) -> None:
        """Distribute ball to teammates (throw or kick)."""
        passing_attr = player_model.attributes.passing
        vision_attr = player_model.attributes.vision

        # Find best target
        target = self.find_best_pass_target(player, ball, all_players, vision_attr, passing_attr)

        if target:
            # Execute distribution
            self.execute_pass(player, target, ball, passing_attr, current_time)
            player.state.is_with_ball = False
