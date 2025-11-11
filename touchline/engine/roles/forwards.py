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
    from touchline.engine.physics import BallState, Vector2D
    from touchline.engine.player_state import PlayerMatchState


class ForwardBaseBehaviour(RoleBehaviour):
    """Base forward AI with attacking and goal-scoring behaviors."""

    def decide_action(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        dt: float,
    ) -> None:
        """Main forward decision-making logic."""
        from touchline.models.player import Player

        player_model: Player = next((p for p in player.team.players if p.player_id == player.player_id), None)
        if not player_model:
            return

        self._current_all_players = all_players

        # Get attributes
        shooting_attr = player_model.attributes.shooting
        dribbling_attr = player_model.attributes.dribbling
        speed_attr = player_model.attributes.speed
        positioning_attr = player_model.attributes.positioning
        passing_attr = player_model.attributes.passing
        vision_attr = player_model.attributes.vision

        try:
            # If forward has the ball, look to score or pass
            if self.has_ball_possession(player, ball):
                self._attack_with_ball(
                    player,
                    ball,
                    all_players,
                    shooting_attr,
                    dribbling_attr,
                    passing_attr,
                    vision_attr,
                    player.match_time,
                )
                return

            # Check if team has possession
            if self._team_has_possession(player, ball, all_players):
                # Make attacking run
                self._make_attacking_run(player, ball, all_players, speed_attr, positioning_attr, dt)
                return

            # Press defenders when out of possession
            if self._should_press_defender(player, ball, all_players):
                self._press_defender(player, ball, all_players, speed_attr, dt)
                return

            # Hold position and wait for opportunity
            self._hold_position(player, ball, positioning_attr, dt)
        finally:
            self._current_all_players = None

    def _team_has_possession(
        self, player: "PlayerMatchState", ball: "BallState", all_players: List["PlayerMatchState"]
    ) -> bool:
        """Check if team has possession of ball."""
        teammates = self.get_teammates(player, all_players) + [player]

        for teammate in teammates:
            if self.has_ball_possession(teammate, ball):
                return True
        return False

    def _attack_with_ball(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        shooting_attr: int,
        dribbling_attr: int,
        passing_attr: int,
        vision_attr: int,
        current_time: float,
    ) -> None:
        """Decide action when forward has the ball in attacking position."""
        goal_pos = self.get_goal_position(player)
        distance_to_goal = player.state.position.distance_to(goal_pos)

        # Prioritize shooting if in good position
        if distance_to_goal < 25 and self.should_shoot(player, ball, shooting_attr):
            self.execute_shot(player, ball, shooting_attr, current_time)
            return

        # Look for better positioned teammate
        teammates = self.get_teammates(player, all_players)
        better_positioned = None
        min_distance = distance_to_goal

        for teammate in teammates:
            teammate_distance = teammate.state.position.distance_to(goal_pos)
            if teammate_distance < min_distance and teammate_distance < 20:
                # Check if pass lane is clear
                opponents = self.get_opponents(player, all_players)
                lane_quality = self.calculate_pass_lane_quality(player, teammate, opponents)
                if lane_quality > 0.5:
                    better_positioned = teammate
                    min_distance = teammate_distance

        if better_positioned and vision_attr > 60:
            # Pass to better positioned teammate
            self.execute_pass(player, better_positioned, ball, passing_attr, current_time)
            return

        # Dribble towards goal
        self._dribble_at_goal(player, ball, dribbling_attr, all_players)

    def _dribble_at_goal(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        dribbling_attr: int,
        all_players: List["PlayerMatchState"],
    ) -> None:
        """Dribble towards goal."""
        from touchline.engine.physics import Vector2D

        goal_pos = self.get_goal_position(player)
        opponents = self.get_opponents(player, all_players)

        # Check for immediate pressure
        immediate_pressure = any(
            opp.state.position.distance_to(player.state.position) < 2.5 for opp in opponents
        )

        if immediate_pressure and dribbling_attr < 70:
            # Try to shield ball or find space
            space_direction = self._find_escape_direction(player, opponents)
            # Update player velocity to move in escape direction
            dribble_speed = 2 + (dribbling_attr / 100) * 2  # 2-4 m/s when under pressure
            player.state.velocity = space_direction.normalize() * dribble_speed
        else:
            # Dribble directly at goal
            direction = (goal_pos - player.state.position).normalize()
            dribble_speed = 3.5 + (dribbling_attr / 100) * 2.5  # 3.5-6 m/s
            player.state.velocity = direction * dribble_speed

        # Keep ball at player's feet
        ball.position = player.state.position
        ball.velocity = Vector2D(0, 0)

    def _find_escape_direction(
        self, player: "PlayerMatchState", opponents: List["PlayerMatchState"]
    ) -> "Vector2D":
        """Find direction with least pressure."""
        import math

        from touchline.engine.physics import Vector2D

        best_direction = Vector2D(1, 0)
        max_space = 0

        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            direction = Vector2D(math.cos(rad), math.sin(rad))

            # Calculate space in this direction
            space = 10.0  # Base space
            for opp in opponents:
                to_opp = opp.state.position - player.state.position
                dot = to_opp.x * direction.x + to_opp.y * direction.y

                if dot > 0:  # Opponent in this direction
                    distance = to_opp.magnitude()
                    space -= 10 / max(1, distance)

            if space > max_space:
                max_space = space
                best_direction = direction

        return best_direction

    def _make_attacking_run(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        speed_attr: int,
        positioning_attr: int,
        dt: float,
    ) -> None:
        """Make an attacking run to receive the ball."""
        goal_pos = self.get_goal_position(player)
        opponents = self.get_opponents(player, all_players)

        # Find space behind defense or between defenders
        run_target = self._find_attacking_space(player, ball, goal_pos, opponents, positioning_attr)

        # Time the run based on ball carrier
        ball_carrier = None
        teammates = self.get_teammates(player, all_players)
        for teammate in teammates:
            if self.has_ball_possession(teammate, ball):
                ball_carrier = teammate
                break

        # Sprint if ball carrier is looking to pass
        sprint = ball_carrier and ball_carrier.state.position.distance_to(player.state.position) < 30

        # Adjust run target based on forward type
        run_target = self._adjust_attacking_run(player, run_target, ball, goal_pos)

        self.move_to_position(player, run_target, speed_attr, dt, sprint=sprint)

    def _find_attacking_space(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        goal_pos: "Vector2D",
        opponents: List["PlayerMatchState"],
        positioning_attr: int,
    ) -> "Vector2D":
        """Find space in attacking third."""
        from touchline.engine.physics import Vector2D

        # Look for space between defenders and goal
        # Better positioning allows better run identification

        # Target area ahead of ball and towards goal
        target_x = goal_pos.x * 0.7 + ball.position.x * 0.3
        target_y = ball.position.y

        # Check for offside (simplified)
        # Don't run past all defenders
        deepest_defender_x = goal_pos.x
        for opp in opponents:
            if opp.player_role in ["GK"]:
                continue
            if abs(opp.state.position.x - goal_pos.x) < abs(deepest_defender_x - goal_pos.x):
                deepest_defender_x = opp.state.position.x

        # Stay onside
        onside_margin = 2
        if player.is_home_team:
            target_x = min(target_x, deepest_defender_x - onside_margin)
        else:
            target_x = max(target_x, deepest_defender_x + onside_margin)

        return Vector2D(target_x, target_y)

    def _adjust_attacking_run(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState", goal_pos: "Vector2D"
    ) -> "Vector2D":
        """Adjust attacking run based on forward type (overridden by subclasses)."""
        return position

    def _should_press_defender(
        self, player: "PlayerMatchState", ball: "BallState", all_players: List["PlayerMatchState"]
    ) -> bool:
        """Decide if should press defender with ball."""
        opponents = self.get_opponents(player, all_players)

        for opp in opponents:
            if opp.player_role in ["GK", "CD", "LD", "RD"]:  # Defensive players
                if self.has_ball_possession(opp, ball):
                    distance = player.state.position.distance_to(opp.state.position)
                    return distance < 20  # Press if within range

        return False

    def _press_defender(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        speed_attr: int,
        dt: float,
    ) -> None:
        """Press defender with the ball."""
        opponents = self.get_opponents(player, all_players)

        for opp in opponents:
            if self.has_ball_possession(opp, ball):
                # Sprint towards opponent
                self.move_to_position(player, opp.state.position, speed_attr, dt, sprint=True)
                break

    def _hold_position(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        positioning_attr: int,
        dt: float,
    ) -> None:
        """Hold attacking position."""
        goal_pos = self.get_goal_position(player)

        # Stay high up the pitch
        hold_position = player.role_position

        # Adjust based on ball position but don't drop too deep
        if abs(ball.position.x - goal_pos.x) > abs(hold_position.x - goal_pos.x):
            # Ball is behind, can drop slightly
            adjustment = (ball.position - hold_position).normalize() * 5
            hold_position = hold_position + adjustment

        self.move_to_position(player, hold_position, positioning_attr, dt, sprint=False)


class CentreForwardRoleBehaviour(ForwardBaseBehaviour):
    """Central striker AI - main goal threat."""

    def __init__(self) -> None:
        super().__init__(role="CF", side="central")

    def _adjust_attacking_run(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState", goal_pos: "Vector2D"
    ) -> "Vector2D":
        """Stay central, make runs through the middle."""
        from touchline.engine.physics import Vector2D

        # Stay in central channel
        adjusted_y = position.y * 0.3  # Drift slightly but stay central
        adjusted_y = max(-8, min(8, adjusted_y))

        return Vector2D(position.x, adjusted_y)


class LeftCentreForwardRoleBehaviour(ForwardBaseBehaviour):
    """Left forward / Left winger AI."""

    def __init__(self) -> None:
        super().__init__(role="LCF", side="left")

    def _adjust_attacking_run(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState", goal_pos: "Vector2D"
    ) -> "Vector2D":
        """Make diagonal runs from left."""
        from touchline.engine.physics import Vector2D

        # Prefer left side or diagonal runs towards center
        adjusted_y = max(position.y, 5)  # Stay left or cut inside

        # Sometimes cut inside towards goal
        if ball.position.y < 0:  # Ball on right
            adjusted_y = min(adjusted_y, 15)  # Stay wider
        else:  # Ball on left
            adjusted_y = position.y * 0.7  # Can cut inside more

        return Vector2D(position.x, adjusted_y)


class RightCentreForwardRoleBehaviour(ForwardBaseBehaviour):
    """Right forward / Right winger AI."""

    def __init__(self) -> None:
        super().__init__(role="RCF", side="right")

    def _adjust_attacking_run(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState", goal_pos: "Vector2D"
    ) -> "Vector2D":
        """Make diagonal runs from right."""
        from touchline.engine.physics import Vector2D

        # Prefer right side or diagonal runs towards center
        adjusted_y = min(position.y, -5)  # Stay right or cut inside

        # Sometimes cut inside towards goal
        if ball.position.y > 0:  # Ball on left
            adjusted_y = max(adjusted_y, -15)  # Stay wider
        else:  # Ball on right
            adjusted_y = position.y * 0.7  # Can cut inside more

        return Vector2D(position.x, adjusted_y)
