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

from typing import TYPE_CHECKING, List, Optional

from touchline.engine.config import ENGINE_CONFIG

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
            if self._move_to_receive_pass(player, ball, speed_attr, dt):
                return

            if self._pursue_loose_ball(player, ball, all_players, speed_attr):
                return

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

        opponents = self.get_opponents(player, all_players)
        fwd_cfg = ENGINE_CONFIG.role.forward

        # Prioritize shooting if in good position
        if distance_to_goal < fwd_cfg.shoot_distance_threshold and self.should_shoot(player, ball, shooting_attr):
            self.execute_shot(player, ball, shooting_attr, current_time)
            return

        # Look for best pass option
        best_target = self.find_best_pass_target(
            player,
            ball,
            all_players,
            vision_attr,
            passing_attr,
        )

        if best_target:
            teammate_distance = best_target.state.position.distance_to(goal_pos)
            progressive = teammate_distance < distance_to_goal

            if progressive or vision_attr >= fwd_cfg.vision_progressive_threshold:
                self.execute_pass(player, best_target, ball, passing_attr, current_time)
                return

            if self._is_under_pressure(player, opponents) and vision_attr >= fwd_cfg.vision_pressure_release_threshold:
                self.execute_pass(player, best_target, ball, passing_attr, current_time)
                return

        # Try to recycle possession if being swarmed
        relief_target = None
        if self._is_under_pressure(player, opponents):
            relief_target = self._find_relief_pass(
                player,
                ball,
                all_players,
                opponents,
                vision_attr,
            )

        if relief_target:
            self.execute_pass(player, relief_target, ball, passing_attr, current_time)
            return

        # Dribble towards goal
        self._dribble_at_goal(
            player,
            ball,
            dribbling_attr,
            passing_attr,
            vision_attr,
            all_players,
            opponents,
            current_time,
        )

    def _dribble_at_goal(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        dribbling_attr: int,
        passing_attr: int,
        vision_attr: int,
        all_players: List["PlayerMatchState"],
        opponents: List["PlayerMatchState"],
        current_time: float,
    ) -> None:
        """Dribble towards goal."""
        from touchline.engine.physics import Vector2D

        goal_pos = self.get_goal_position(player)
        fwd_cfg = ENGINE_CONFIG.role.forward

        # Check for immediate pressure
        immediate_pressure = self._is_under_pressure(player, opponents, radius=fwd_cfg.pressure_radius)

        if immediate_pressure and dribbling_attr < fwd_cfg.pressure_dribble_threshold:
            relief_target = self._find_relief_pass(
                player,
                ball,
                all_players,
                opponents,
                vision_attr,
            )

            if relief_target:
                self.execute_pass(player, relief_target, ball, passing_attr, current_time)
                return

            # Try to shield ball or find space
            space_direction = self._find_escape_direction(player, opponents)
            # Update player velocity to move in escape direction
            dribble_speed = (
                fwd_cfg.dribble_pressure_base
                + (dribbling_attr / 100) * fwd_cfg.dribble_pressure_attr_scale
            )
            player.state.velocity = space_direction.normalize() * dribble_speed
        else:
            # Dribble directly at goal
            direction = (goal_pos - player.state.position).normalize()
            dribble_speed = (
                fwd_cfg.dribble_speed_base
                + (dribbling_attr / 100) * fwd_cfg.dribble_speed_attr_scale
            )
            player.state.velocity = direction * dribble_speed

        # Keep the ball just ahead of the dribbler so opponents can challenge.
        control_offset = fwd_cfg.dribble_control_offset
        carry_factor = fwd_cfg.dribble_velocity_blend
        if player.state.velocity.magnitude() > 0:
            carry_dir = player.state.velocity.normalize()
            target_pos = player.state.position + carry_dir * control_offset
            ball.position = Vector2D(
                ball.position.x + (target_pos.x - ball.position.x) * 0.6,
                ball.position.y + (target_pos.y - ball.position.y) * 0.6,
            )
            ball.velocity = player.state.velocity * carry_factor
        else:
            ball.position = player.state.position
            ball.velocity = Vector2D(0, 0)

    def _find_escape_direction(
        self, player: "PlayerMatchState", opponents: List["PlayerMatchState"]
    ) -> "Vector2D":
        """Find direction with least pressure."""
        import math

        from touchline.engine.physics import Vector2D

        fwd_cfg = ENGINE_CONFIG.role.forward
        best_direction = Vector2D(1, 0)
        max_space = float("-inf")

        for angle in range(0, 360, fwd_cfg.escape_angle_step):
            rad = math.radians(angle)
            direction = Vector2D(math.cos(rad), math.sin(rad))

            # Calculate space in this direction
            space = fwd_cfg.escape_base_space
            for opp in opponents:
                to_opp = opp.state.position - player.state.position
                dot = to_opp.x * direction.x + to_opp.y * direction.y

                if dot > 0:  # Opponent in this direction
                    distance = to_opp.magnitude()
                    space -= fwd_cfg.escape_opponent_scale / max(1.0, distance)

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
        fwd_cfg = ENGINE_CONFIG.role.forward

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
        sprint = (
            ball_carrier
            and ball_carrier.state.position.distance_to(player.state.position)
            < fwd_cfg.run_ballcarrier_distance
        )

        # Adjust run target based on forward type
        run_target = self._adjust_attacking_run(player, run_target, ball, goal_pos)

        self.move_to_position(player, run_target, speed_attr, dt, ball, sprint=sprint)

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
        fwd_cfg = ENGINE_CONFIG.role.forward

        target_x = goal_pos.x * fwd_cfg.run_goal_weight + ball.position.x * fwd_cfg.run_ball_weight
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
        onside_margin = fwd_cfg.onside_margin
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
        fwd_cfg = ENGINE_CONFIG.role.forward

        for opp in opponents:
            if opp.player_role in ["GK", "CD", "LD", "RD"]:  # Defensive players
                if self.has_ball_possession(opp, ball):
                    distance = player.state.position.distance_to(opp.state.position)
                    return distance < fwd_cfg.pressing_distance

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
                self.move_to_position(player, opp.state.position, speed_attr, dt, ball, sprint=True)
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
        fwd_cfg = ENGINE_CONFIG.role.forward

        # Adjust based on ball position but don't drop too deep
        if abs(ball.position.x - goal_pos.x) > abs(hold_position.x - goal_pos.x):
            # Ball is behind, can drop slightly
            offset = ball.position - hold_position
            if offset.magnitude() > 1e-3:
                adjustment = offset.normalize() * fwd_cfg.hold_position_adjustment
                hold_position = hold_position + adjustment

        self.move_to_position(player, hold_position, positioning_attr, dt, ball, sprint=False)

    def _is_under_pressure(
        self,
        player: "PlayerMatchState",
        opponents: List["PlayerMatchState"],
        radius: Optional[float] = None,
    ) -> bool:
        """Detect if any opponent is within pressing distance."""
        fwd_cfg = ENGINE_CONFIG.role.forward
        radius = fwd_cfg.pressure_radius if radius is None else radius
        return any(opp.state.position.distance_to(player.state.position) < radius for opp in opponents)

    def _find_relief_pass(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        opponents: List["PlayerMatchState"],
        vision_attr: int,
    ) -> "PlayerMatchState" | None:
        """Find a nearby teammate with space to recycle possession."""
        teammates = self.get_teammates(player, all_players)

        if not teammates:
            return None

        best_target = None
        best_score = 0.0
        goal_pos = self.get_goal_position(player)
        fwd_cfg = ENGINE_CONFIG.role.forward

        for teammate in teammates:
            distance = player.state.position.distance_to(teammate.state.position)

            if distance < fwd_cfg.relief_min_distance or distance > fwd_cfg.relief_max_distance:
                continue

            lane_quality = self.calculate_pass_lane_quality(player, teammate, opponents)

            # Prefer teammates with time and space
            nearest_opponent = min(
                (opp.state.position.distance_to(teammate.state.position) for opp in opponents),
                default=fwd_cfg.relief_nearest_default,
            )

            space_score = min(nearest_opponent / fwd_cfg.relief_space_divisor, 1.0)

            # Encourage diagonal or lateral passes when pressured
            angle_progress = goal_pos.distance_to(teammate.state.position) < goal_pos.distance_to(
                player.state.position
            )
            momentum_score = (
                fwd_cfg.relief_progress_bonus if angle_progress else fwd_cfg.relief_support_bonus
            )

            distance_score = 1 - (distance / fwd_cfg.relief_max_distance)
            vision_factor = fwd_cfg.relief_vision_base + (vision_attr / 100) * fwd_cfg.relief_vision_scale

            weighted_score = (
                lane_quality * fwd_cfg.relief_lane_weight
                + space_score * fwd_cfg.relief_space_weight
                + distance_score * fwd_cfg.relief_distance_weight
            )

            total_score = (weighted_score + momentum_score) * vision_factor

            if total_score > best_score:
                best_score = total_score
                best_target = teammate

        return best_target if best_score > fwd_cfg.relief_score_threshold else None


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
        fwd_cfg = ENGINE_CONFIG.role.forward
        adjusted_y = position.y * fwd_cfg.centre_adjust_factor  # Drift slightly but stay central
        adjusted_y = max(-fwd_cfg.centre_max_width, min(fwd_cfg.centre_max_width, adjusted_y))

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
        fwd_cfg = ENGINE_CONFIG.role.forward
        adjusted_y = max(position.y, fwd_cfg.wide_min_offset)  # Stay left or cut inside

        # Sometimes cut inside towards goal
        if ball.position.y < 0:  # Ball on right
            adjusted_y = min(adjusted_y, fwd_cfg.wide_max_width)  # Stay wider
        else:  # Ball on left
            adjusted_y = position.y * fwd_cfg.cut_inside_factor  # Can cut inside more

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
        fwd_cfg = ENGINE_CONFIG.role.forward
        adjusted_y = min(position.y, -fwd_cfg.wide_min_offset)  # Stay right or cut inside

        # Sometimes cut inside towards goal
        if ball.position.y > 0:  # Ball on left
            adjusted_y = max(adjusted_y, -fwd_cfg.wide_max_width)  # Stay wider
        else:  # Ball on right
            adjusted_y = position.y * fwd_cfg.cut_inside_factor  # Can cut inside more

        return Vector2D(position.x, adjusted_y)
