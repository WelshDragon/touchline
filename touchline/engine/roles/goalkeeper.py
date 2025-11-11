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

from typing import TYPE_CHECKING, List

from .base import RoleBehaviour

if TYPE_CHECKING:
    from touchline.engine.physics import BallState
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
            # Check if goalkeeper has possession
            if self.has_ball_possession(player, ball):
                self._distribute_ball(player, ball, all_players, player_model, player.match_time)
                return

            # Check if ball is in penalty area and needs saving
            if self._is_ball_dangerous(player, ball):
                self._attempt_save(player, ball, speed_attr, positioning_attr, dt)
                return

            # Check if should come out to collect ball (sweeper keeper)
            if self._should_collect_ball(player, ball, decisions_attr, all_players):
                self._collect_ball(player, ball, speed_attr, dt)
                return

            # Default: maintain good positioning
            self._position_for_shot(player, ball, positioning_attr, dt)
        finally:
            self._current_all_players = None

    def _is_ball_dangerous(self, player: "PlayerMatchState", ball: "BallState") -> bool:
        """Check if ball poses immediate threat (shot on goal)."""
        goal_pos = self.get_own_goal_position(player)

        # Ball heading towards goal
        if ball.velocity.magnitude() > 3:
            # Project ball trajectory
            ball_to_goal = goal_pos - ball.position
            ball_direction = ball.velocity.normalize()

            dot_product = ball_to_goal.x * ball_direction.x + ball_to_goal.y * ball_direction.y

            # Ball moving towards goal and close
            if dot_product > 0 and ball.position.distance_to(goal_pos) < 25:
                return True

        return False

    def _attempt_save(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        speed_attr: int,
        positioning_attr: int,
        dt: float,
    ) -> None:
        """Attempt to save/intercept the ball."""
        # Calculate where ball will be
        ball_future_pos = ball.position + ball.velocity * 0.3  # Look 0.3 seconds ahead

        # Move to intercept
        self.move_to_position(player, ball_future_pos, speed_attr, dt, sprint=True)

        # If close enough, can catch/punch
        if self.distance_to_ball(player, ball) < 1.5:
            # Stop the ball (save!)
            from touchline.engine.physics import Vector2D

            ball.velocity = Vector2D(0, 0)
            player.state.is_with_ball = True

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
        self.move_to_position(player, ball.position, speed_attr, dt, sprint=True)

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

        # Position between ball and goal center
        ball_to_goal = (goal_pos - ball.position).normalize()

        # Distance from goal line (2-4m depending on positioning attribute)
        goal_distance = 2 + (positioning_attr / 100) * 2

        # Calculate optimal position
        optimal_x = goal_pos.x + ball_to_goal.x * goal_distance

        # Y position: bisect angle to goal posts
        angle_factor = (ball.position.y - goal_pos.y) * 0.3  # Move across goal
        optimal_y = goal_pos.y + angle_factor

        # Constrain to goal width
        max_y = 3.0  # Don't stray too far from center
        optimal_y = max(-max_y, min(max_y, optimal_y))

        target_pos = Vector2D(optimal_x, optimal_y)

        # Move to position
        self.move_to_position(player, target_pos, 50, dt, sprint=False)

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
