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

import math
import random
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from touchline.engine.physics import BallState, Vector2D
    from touchline.engine.player_state import PlayerMatchState


class RoleBehaviour:
    """Base AI behaviour framework for all player roles."""

    def __init__(self, role: str, side: str = "central") -> None:
        self.role = role
        self.side = side
        self._current_all_players: Optional[List["PlayerMatchState"]] = None

    def decide_action(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        dt: float,
    ) -> None:
        """Main decision-making method called every frame. Override in subclasses."""
        pass

    # ==================== HELPER METHODS ====================

    def get_teammates(
        self, player: "PlayerMatchState", all_players: List["PlayerMatchState"]
    ) -> List["PlayerMatchState"]:
        """Get all teammates excluding the player."""
        return [p for p in all_players if p.team == player.team and p.player_id != player.player_id]

    def get_opponents(
        self, player: "PlayerMatchState", all_players: List["PlayerMatchState"]
    ) -> List["PlayerMatchState"]:
        """Get all opponents."""
        return [p for p in all_players if p.team != player.team]

    def distance_to_ball(self, player: "PlayerMatchState", ball: "BallState") -> float:
        """Calculate distance from player to ball."""
        return player.state.position.distance_to(ball.position)

    def is_closest_to_ball(
        self, player: "PlayerMatchState", ball: "BallState", all_players: List["PlayerMatchState"]
    ) -> bool:
        """Check if this player is closest to the ball on their team."""
        teammates = self.get_teammates(player, all_players) + [player]
        distances = [p.state.position.distance_to(ball.position) for p in teammates]
        return min(distances) == player.state.position.distance_to(ball.position)

    def has_ball_possession(self, player: "PlayerMatchState", ball: "BallState") -> bool:
        """Check if player has possession of the ball."""
        # Use the is_with_ball flag set by the match engine
        return player.state.is_with_ball

    def get_goal_position(self, player: "PlayerMatchState", pitch_width: float = 105.0) -> "Vector2D":
        """Get the opponent's goal position."""
        from touchline.engine.physics import Vector2D

        goal_x = pitch_width / 2 if player.is_home_team else -pitch_width / 2
        return Vector2D(goal_x, 0)

    def get_own_goal_position(self, player: "PlayerMatchState", pitch_width: float = 105.0) -> "Vector2D":
        """Get the player's own goal position."""
        from touchline.engine.physics import Vector2D

        goal_x = -pitch_width / 2 if player.is_home_team else pitch_width / 2
        return Vector2D(goal_x, 0)

    def should_shoot(self, player: "PlayerMatchState", ball: "BallState", shooting_attr: int) -> bool:
        """Decide if player should attempt a shot."""
        goal_pos = self.get_goal_position(player)
        distance_to_goal = player.state.position.distance_to(goal_pos)

        # Don't shoot if too far (based on shooting ability)
        max_distance = 25 + (shooting_attr / 100 * 15)  # 25-40m range
        if distance_to_goal > max_distance:
            return False

        # More likely to shoot when closer
        shoot_probability = (1 - distance_to_goal / max_distance) * (shooting_attr / 100)

        # Require better angle when further away
        angle_quality = self.calculate_shot_angle_quality(player, goal_pos)
        if angle_quality < 0.3 and distance_to_goal > 20:
            return False

        return random.random() < shoot_probability * 0.2  # Reduce shooting frequency

    def calculate_shot_angle_quality(self, player: "PlayerMatchState", goal_pos: "Vector2D") -> float:
        """Calculate quality of shooting angle (0-1)."""
        from touchline.engine.physics import Vector2D

        # Check angles to goal posts
        post_width = 7.32 / 2  # Half of goal width
        left_post = Vector2D(goal_pos.x, goal_pos.y + post_width)
        right_post = Vector2D(goal_pos.x, goal_pos.y - post_width)

        angle_left = self._angle_between(player.state.position, left_post, goal_pos)
        angle_right = self._angle_between(player.state.position, right_post, goal_pos)

        # Wider angle = better shot quality
        total_angle = abs(angle_left + angle_right)
        return min(1.0, total_angle / 30)  # Normalize to 0-1

    def _angle_between(self, pos: "Vector2D", target1: "Vector2D", target2: "Vector2D") -> float:
        """Calculate angle between two targets from a position."""
        v1 = (target1 - pos).normalize()
        v2 = (target2 - pos).normalize()
        dot = v1.x * v2.x + v1.y * v2.y
        return math.degrees(math.acos(max(-1, min(1, dot))))

    def find_best_pass_target(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        vision_attr: int,
        passing_attr: int,
    ) -> Optional["PlayerMatchState"]:
        """Find the best teammate to pass to."""
        teammates = self.get_teammates(player, all_players)
        opponents = self.get_opponents(player, all_players)

        if not teammates:
            return None

        best_target = None
        best_score = -1

        goal_pos = self.get_goal_position(player)

        for teammate in teammates:
            # Skip if too far based on passing ability
            distance = player.state.position.distance_to(teammate.state.position)
            max_pass_distance = 30 + (passing_attr / 100 * 30)  # 30-60m range

            if distance > max_pass_distance or distance < 5:
                continue

            # Check if pass lane is clear
            lane_quality = self.calculate_pass_lane_quality(player, teammate, opponents)

            # Prefer passes towards goal
            teammate_distance_to_goal = teammate.state.position.distance_to(goal_pos)
            player_distance_to_goal = player.state.position.distance_to(goal_pos)
            progress_score = max(0, player_distance_to_goal - teammate_distance_to_goal) / 50

            # Weight factors
            distance_score = 1 - (distance / max_pass_distance)
            vision_factor = vision_attr / 100

            total_score = (lane_quality * 0.4 + distance_score * 0.3 + progress_score * 0.3) * vision_factor

            if total_score > best_score:
                best_score = total_score
                best_target = teammate

        return best_target if best_score > 0.3 else None

    def calculate_pass_lane_quality(
        self,
        passer: "PlayerMatchState",
        receiver: "PlayerMatchState",
        opponents: List["PlayerMatchState"],
    ) -> float:
        """Calculate how clear the passing lane is (0-1)."""
        pass_vector = receiver.state.position - passer.state.position
        pass_distance = pass_vector.magnitude()

        if pass_distance < 0.1:
            return 0

        quality = 1.0

        for opponent in opponents:
            # Calculate perpendicular distance from opponent to pass line
            to_opponent = opponent.state.position - passer.state.position
            projection = (to_opponent.x * pass_vector.x + to_opponent.y * pass_vector.y) / (pass_distance**2)

            if 0 <= projection <= 1:  # Opponent is between passer and receiver
                perp_distance = abs(
                    (pass_vector.y * to_opponent.x - pass_vector.x * to_opponent.y) / pass_distance
                )

                # Reduce quality based on proximity
                if perp_distance < 5:
                    quality *= perp_distance / 5

        return quality

    def _move_to_receive_pass(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        speed_attr: int,
        dt: float,
    ) -> bool:
        """Guide intended recipient towards the incoming ball to secure the pass."""
        if ball.last_kick_recipient != player.player_id:
            return False

        if self.has_ball_possession(player, ball):
            ball.last_kick_recipient = None
            return False

        from touchline.engine.physics import Vector2D

        ball_speed = ball.velocity.magnitude()

        # Lead slightly ahead of the ball so the receiver meets it in stride,
        # otherwise target the current ball position when the pass has slowed.
        if ball_speed >= 0.3:
            lead_distance = min(max(ball_speed * 0.35, 1.5), 6.0)
            intercept = ball.position + ball.velocity.normalize() * lead_distance
        else:
            intercept = ball.position

        to_intercept = intercept - player.state.position
        distance = to_intercept.magnitude()

        if distance < 0.4:
            # Close enough – let possession logic take over next frame.
            player.state.velocity = Vector2D(0, 0)
            return True

        direction = to_intercept.normalize()

        # Approximate maximum controllable speed while preparing to receive.
        base_speed = 4.5
        max_speed = base_speed + (speed_attr / 100) * 3.0
        player.state.velocity = direction * max_speed
        player.current_target = intercept

        return True

    def execute_pass(
        self,
        player: "PlayerMatchState",
        target: "PlayerMatchState",
        ball: "BallState",
        passing_attr: int,
        current_time: float,
    ) -> None:
        """Execute a pass to a teammate."""
        distance = player.state.position.distance_to(target.state.position)

        # Calculate pass power based on distance and ability
        base_power = distance * 1.5
        accuracy_factor = passing_attr / 100
        power = base_power * (0.8 + accuracy_factor * 0.4)

        # Add slight inaccuracy based on passing attribute
        inaccuracy = (1 - accuracy_factor) * 2
        target_pos = target.state.position
        offset_x = random.uniform(-inaccuracy, inaccuracy)
        offset_y = random.uniform(-inaccuracy, inaccuracy)

        from touchline.engine.physics import Vector2D

        adjusted_target = Vector2D(target_pos.x + offset_x, target_pos.y + offset_y)
        direction = (adjusted_target - player.state.position).normalize()

        ball.kick(direction, power, player.player_id, current_time, target.player_id)

    def execute_shot(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        shooting_attr: int,
        current_time: float,
    ) -> None:
        """Execute a shot on goal."""
        goal_pos = self.get_goal_position(player)

        # Aim for corners based on shooting ability
        accuracy = shooting_attr / 100
        goal_offset_y = random.uniform(-3, 3) * (1 - accuracy)

        from touchline.engine.physics import Vector2D

        target = Vector2D(goal_pos.x, goal_pos.y + goal_offset_y)
        direction = (target - player.state.position).normalize()

        # Power based on distance and shooting ability
        distance = player.state.position.distance_to(goal_pos)
        power = min(35, distance * 1.2 + 15) * (0.8 + accuracy * 0.4)

        ball.kick(direction, power, player.player_id, current_time)

        # Log shot event if debugger is available
        if hasattr(player, "debugger") and player.debugger:
            # Store event (need access to match state to add to events list)
            # For now, just log it
            player.debugger.log_match_event(current_time, "shot", f"SHOT by player {player.player_id}")

    def move_to_position(
        self,
        player: "PlayerMatchState",
        target: "Vector2D",
        speed_attr: int,
        dt: float,
        sprint: bool = False,
    ) -> None:
        """Move player towards target position."""
        base_speed = 6.0  # Base speed in m/s
        max_speed = base_speed * (0.7 + (speed_attr / 100) * 0.6)  # 4.2 - 7.8 m/s

        if sprint:
            max_speed *= 1.4  # Sprint boost

        # Apply light lane preservation and teammate spacing for outfield players
        from touchline.engine.physics import Vector2D

        adjusted_target = Vector2D(target.x, target.y)

        if getattr(player, "player_role", "") != "GK":
            adjusted_target = self._apply_lane_spacing(player, adjusted_target)

        player.current_target = adjusted_target
        player.state.move_towards(adjusted_target, dt, max_speed)

    def _apply_lane_spacing(
        self,
        player: "PlayerMatchState",
        target: "Vector2D",
        lane_weight: float = 0.25,
        min_spacing: float = 6.0,
    ) -> "Vector2D":
        """Blend target with base lane and push away from nearby teammates to avoid crowding."""
        from touchline.engine.physics import Vector2D

        adjusted = Vector2D(target.x, target.y)

        # Keep some attachment to assigned formation lane when not carrying the ball
        if not player.state.is_with_ball:
            base = player.role_position
            adjusted = Vector2D(
                adjusted.x * (1 - lane_weight) + base.x * lane_weight,
                adjusted.y * (1 - lane_weight) + base.y * lane_weight,
            )

        teammates: Optional[List["PlayerMatchState"]] = None

        if self._current_all_players:
            teammates = [p for p in self._current_all_players if p.team == player.team and p != player]

        if teammates:
            separation = Vector2D(0, 0)

            for mate in teammates:
                offset = adjusted - mate.state.position
                distance = offset.magnitude()

                if distance < 1e-3:
                    continue

                if distance < min_spacing:
                    push_dir = offset.normalize()
                    # Push out proportionally to how close the teammate is
                    push_strength = (min_spacing - distance) / min_spacing
                    separation = separation + push_dir * (push_strength * min_spacing * 0.5)

            adjusted = adjusted + separation

        return adjusted

    def get_defensive_position(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        base_position: "Vector2D",
    ) -> "Vector2D":
        """Calculate defensive position maintaining individual formation positions."""
        from touchline.engine.physics import Vector2D

        own_goal = self.get_own_goal_position(player)

        # Calculate how far forward/back the defensive line should be based on ball position
        # This gives a target X coordinate for the defensive line
        ball_to_goal_distance = abs(ball.position.x - own_goal.x)
        
        # Defensive line positions itself proportionally between base position and ball
        # When ball is far (>40m), stay at base position
        # When ball is close (<20m), push up to around 15m from goal
        if ball_to_goal_distance > 40:
            target_x = base_position.x
        elif ball_to_goal_distance < 20:
            # Push up but not past the ball
            target_x = own_goal.x + (15 if own_goal.x < 0 else -15)
        else:
            # Interpolate between base and advanced position
            t = (40 - ball_to_goal_distance) / 20  # 0 when far, 1 when close
            advanced_x = own_goal.x + (25 if own_goal.x < 0 else -25)
            target_x = base_position.x * (1 - t) + advanced_x * t
        
        # Maintain individual Y position from formation (with slight adjustment for ball)
        # Each player keeps their horizontal spacing
        ball_y_offset = (ball.position.y - base_position.y) * 0.2  # Only 20% pull towards ball
        target_y = base_position.y + ball_y_offset
        
        return Vector2D(target_x, target_y)

    def should_press(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        stamina_threshold: float = 30.0,
    ) -> bool:
        """Decide if player should press the opponent with the ball."""
        if player.state.stamina < stamina_threshold:
            return False

        distance = self.distance_to_ball(player, ball)

        # Press if reasonably close and ball is with opponent
        if distance < 15:
            opponents = self.get_opponents(player, all_players)
            for opp in opponents:
                if self.has_ball_possession(opp, ball):
                    return True

        return False

    def find_space(
        self,
        player: "PlayerMatchState",
        all_players: List["PlayerMatchState"],
        preferred_direction: "Vector2D",
        search_radius: float = 15.0,
    ) -> "Vector2D":
        """Find space away from other players."""
        from touchline.engine.physics import Vector2D

        # Start with preferred direction
        best_pos = player.state.position + preferred_direction.normalize() * 10

        # Check crowding
        min_crowding = float("inf")

        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            test_pos = player.state.position + Vector2D(
                math.cos(rad) * search_radius, math.sin(rad) * search_radius
            )

            # Calculate crowding at this position
            crowding = sum(1 / max(1, p.state.position.distance_to(test_pos)) for p in all_players if p != player)

            if crowding < min_crowding:
                min_crowding = crowding
                best_pos = test_pos

        return best_pos
