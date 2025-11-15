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
"""Role behaviours for central and wide midfielders."""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from touchline.engine.config import ENGINE_CONFIG

from .base import RoleBehaviour

if TYPE_CHECKING:
    from touchline.engine.physics import BallState, Vector2D
    from touchline.engine.player_state import PlayerMatchState


class MidfielderBaseBehaviour(RoleBehaviour):
    """Base midfielder AI with shared behaviors for linking play.

    Parameters
    ----------
    role : str
        Midfield role code assigned to the behaviour instance.
    side : str
        Pitch side primarily occupied by the midfielder (``"left"``, ``"right"``, or ``"central"``).
    """

    def decide_action(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        dt: float,
    ) -> None:
        """Coordinate midfielder decision-making for this frame.

        Parameters
        ----------
        player : PlayerMatchState
            Controlled midfielder whose behaviour is being updated.
        ball : BallState
            Current ball state for the frame.
        all_players : List[PlayerMatchState]
            Snapshot of all players on the pitch.
        dt : float
            Simulation timestep in seconds since the previous update.
        """
        from touchline.models.player import Player

        player_model: Player = next((p for p in player.team.players if p.player_id == player.player_id), None)
        if not player_model:
            return

        self._current_all_players = all_players

        # Get attributes
        passing_attr = player_model.attributes.passing
        vision_attr = player_model.attributes.vision
        dribbling_attr = player_model.attributes.dribbling
        tackling_attr = player_model.attributes.tackling
        speed_attr = player_model.attributes.speed
        shooting_attr = player_model.attributes.shooting
        opponents = self.get_opponents(player, all_players)
        mid_cfg = ENGINE_CONFIG.role.midfielder

        try:
            if self._move_to_receive_pass(player, ball, speed_attr, dt):
                return

            if self._pursue_loose_ball(player, ball, all_players, speed_attr):
                return

            # If midfielder has the ball, decide next action
            if self.has_ball_possession(player, ball):
                self._play_with_ball(
                    player,
                    ball,
                    all_players,
                    passing_attr,
                    vision_attr,
                    shooting_attr,
                    dribbling_attr,
                    player.match_time,
                )
                return

            # Press opponent if they have ball
            if self.should_press(
                player,
                ball,
                all_players,
                stamina_threshold=mid_cfg.press_stamina_threshold,
            ):
                self._press_opponent(player, ball, opponents, speed_attr, tackling_attr, dt)
                return

            # Support attack if team has ball
            if self._team_has_possession(player, ball, all_players):
                self._support_attack(player, ball, all_players, vision_attr, speed_attr, dt)
                return

            # Track back and support defense
            self._support_defense(player, ball, all_players, tackling_attr, dt)
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

    def _play_with_ball(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        passing_attr: int,
        vision_attr: int,
        shooting_attr: int,
        dribbling_attr: int,
        current_time: float,
    ) -> None:
        """Decide action when midfielder has the ball."""
        # Check if in shooting position
        if self.should_shoot(player, ball, shooting_attr):
            self.execute_shot(player, ball, shooting_attr, current_time)
            return

        opponents = self.get_opponents(player, all_players)
        mid_cfg = ENGINE_CONFIG.role.midfielder

        # Look for forward pass
        target = self.find_best_pass_target(player, ball, all_players, vision_attr, passing_attr)

        if target:
            # Check if pass is progressive
            goal_pos = self.get_goal_position(player)
            target_closer = target.state.position.distance_to(goal_pos) < player.state.position.distance_to(goal_pos)

            if target_closer or vision_attr >= mid_cfg.progressive_pass_vision_threshold:
                self.execute_pass(player, target, ball, passing_attr, current_time)
                return

            # If under pressure, take the safe pass even if it's not progressive
            if self._is_under_pressure(player, opponents) and target:
                self.execute_pass(player, target, ball, passing_attr, current_time)
                return

        # Dribble forward if no good pass
        self._dribble_forward(
            player,
            ball,
            dribbling_attr,
            passing_attr,
            vision_attr,
            all_players,
            opponents,
            current_time,
        )

    def _dribble_forward(
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
        """Dribble the ball forward."""
        from touchline.engine.physics import Vector2D

        goal_pos = self.get_goal_position(player)
        mid_cfg = ENGINE_CONFIG.role.midfielder

        # Check for nearby pressure
        under_pressure = self._is_under_pressure(player, opponents, radius=mid_cfg.pressure_radius)

        if under_pressure and dribbling_attr < mid_cfg.pressure_dribble_threshold:
            relief_target = self._find_relief_pass(player, ball, all_players, opponents, vision_attr)

            if relief_target:
                self.execute_pass(player, relief_target, ball, passing_attr, current_time)
            else:
                # Shield the ball but add small backpedal to avoid freezing in place
                retreat_dir = (player.state.position - goal_pos).normalize()
                player.state.velocity = retreat_dir * mid_cfg.retreat_speed
                ball.position = player.state.position
                ball.velocity = Vector2D(0, 0)
        else:
            # Dribble towards goal or find space
            direction = (goal_pos - player.state.position).normalize()

            # Calculate speed based on dribbling ability (slower than running without ball)
            speed_scale = mid_cfg.dribble_speed_attr_scale
            base_speed = mid_cfg.dribble_speed_base

            if under_pressure:
                base_speed = mid_cfg.dribble_pressure_base
                speed_scale = mid_cfg.dribble_pressure_attr_scale

            dribble_speed = base_speed + (dribbling_attr / 100) * speed_scale

            # Update player velocity to dribble forward
            player.state.velocity = direction * dribble_speed

            # Keep ball at player's feet (stick to player position)
            ball.position = player.state.position
            ball.velocity = Vector2D(0, 0)

    def _is_under_pressure(
        self,
        player: "PlayerMatchState",
        opponents: List["PlayerMatchState"],
        radius: Optional[float] = None,
    ) -> bool:
        """Detect if any opponent is within pressing distance."""
        mid_cfg = ENGINE_CONFIG.role.midfielder
        radius = mid_cfg.pressure_radius if radius is None else radius
        return any(opp.state.position.distance_to(player.state.position) < radius for opp in opponents)

    def _find_relief_pass(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        opponents: List["PlayerMatchState"],
        vision_attr: int,
    ) -> "PlayerMatchState" | None:
        """Find a nearby safe teammate to recycle possession under pressure."""
        teammates = self.get_teammates(player, all_players)

        if not teammates:
            return None

        best_target = None
        best_score = 0.0
        own_goal = self.get_own_goal_position(player)
        mid_cfg = ENGINE_CONFIG.role.midfielder

        for teammate in teammates:
            distance = player.state.position.distance_to(teammate.state.position)

            if distance < mid_cfg.relief_min_distance or distance > mid_cfg.relief_max_distance:
                continue

            lane_quality = self.calculate_pass_lane_quality(player, teammate, opponents)

            # Prefer teammates with space around them
            nearest_opponent = min(
                (opp.state.position.distance_to(teammate.state.position) for opp in opponents),
                default=mid_cfg.relief_nearest_default,
            )

            space_score = min(nearest_opponent / mid_cfg.relief_space_divisor, 1.0)

            # Allow backwards passes, but give a small bonus if the pass keeps momentum
            progress = own_goal.distance_to(teammate.state.position) < own_goal.distance_to(player.state.position)
            momentum_score = mid_cfg.relief_progress_bonus if progress else 0.0

            distance_score = 1 - (distance / mid_cfg.relief_max_distance)
            vision_factor = mid_cfg.relief_vision_base + (vision_attr / 100) * mid_cfg.relief_vision_scale

            weighted_score = (
                lane_quality * mid_cfg.relief_lane_weight
                + space_score * mid_cfg.relief_space_weight
                + distance_score * mid_cfg.relief_distance_weight
            )

            total_score = (weighted_score + momentum_score) * vision_factor

            if total_score > best_score:
                best_score = total_score
                best_target = teammate

        return best_target if best_score > mid_cfg.relief_score_threshold else None

    def _press_opponent(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        opponents: List["PlayerMatchState"],
        speed_attr: int,
        tackling_attr: int,
        dt: float,
    ) -> None:
        """Press the opponent with the ball."""
        # Find opponent with ball
        target_opp = None
        for opp in opponents:
            if self.has_ball_possession(opp, ball):
                target_opp = opp
                break

        if target_opp:
            # Sprint towards opponent
            self.move_to_position(
                player,
                target_opp.state.position,
                speed_attr,
                dt,
                ball,
                sprint=True,
                intent="press",
            )

            # Attempt tackle if close
            mid_cfg = ENGINE_CONFIG.role.midfielder

            if player.state.position.distance_to(target_opp.state.position) < mid_cfg.press_success_distance:
                import random

                success_threshold = (tackling_attr / 100) * mid_cfg.press_success_scale

                if random.random() < success_threshold:
                    # Won the ball!
                    from touchline.engine.physics import Vector2D

                    ball.velocity = Vector2D(0, 0)
                    player.state.is_with_ball = True

    def _support_attack(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        vision_attr: int,
        speed_attr: int,
        dt: float,
    ) -> None:
        """Move to support the attack."""
        goal_pos = self.get_goal_position(player)
        mid_cfg = ENGINE_CONFIG.role.midfielder

        # Find space ahead of the ball
        if ball.position.distance_to(goal_pos) < player.state.position.distance_to(goal_pos):
            # Ball is ahead, support from behind
            support_pos = ball.position - (goal_pos - ball.position).normalize() * mid_cfg.support_trail_distance
        else:
            # Make forward run
            support_pos = ball.position + (goal_pos - ball.position).normalize() * mid_cfg.support_forward_distance

        # Adjust to side based on midfielder type
        support_pos = self._adjust_support_position(player, support_pos, ball)

        # Move to support position
        self.move_to_position(player, support_pos, speed_attr, dt, ball, sprint=False, intent="support")

    def _support_defense(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        tackling_attr: int,
        dt: float,
    ) -> None:
        """Track back and support defense."""
        # Get defensive position
        defensive_pos = self.get_defensive_position(player, ball, player.role_position)

        # Midfielders sit slightly higher than defenders
        own_goal = self.get_own_goal_position(player)
        mid_cfg = ENGINE_CONFIG.role.midfielder
        adjustment_direction = (self.get_goal_position(player) - own_goal).normalize()
        adjustment = adjustment_direction * mid_cfg.support_defense_push

        defensive_pos = defensive_pos + adjustment

        # Move to defensive position
        self.move_to_position(player, defensive_pos, tackling_attr, dt, ball, sprint=False, intent="shape")

    def _adjust_support_position(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Adjust support position based on side (overridden by subclasses)."""
        return position


class RightMidfielderRoleBehaviour(MidfielderBaseBehaviour):
    """Right midfielder / Right winger AI."""

    def __init__(self) -> None:
        """Instantiate the right-sided midfielder behaviour."""
        super().__init__(role="RM", side="right")

    def _adjust_support_position(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Stay wide on the right flank."""
        from touchline.engine.physics import Vector2D

        # Maintain width on right touchline
        mid_cfg = ENGINE_CONFIG.role.midfielder
        adjusted_y = min(position.y, -mid_cfg.right_width)  # Stay wide right
        return Vector2D(position.x, adjusted_y)


class CentralMidfielderRoleBehaviour(MidfielderBaseBehaviour):
    """Central midfielder AI - box-to-box play."""

    def __init__(self) -> None:
        """Instantiate the central midfielder behaviour."""
        super().__init__(role="CM", side="central")

    def _adjust_support_position(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Stay central but shift slightly towards ball."""
        from touchline.engine.physics import Vector2D

        # Central but can drift
        mid_cfg = ENGINE_CONFIG.role.midfielder
        shift_y = (ball.position.y - position.y) * mid_cfg.central_shift_factor
        adjusted_y = position.y + shift_y

        # Stay within central corridor
        adjusted_y = max(-mid_cfg.central_max_width, min(mid_cfg.central_max_width, adjusted_y))
        return Vector2D(position.x, adjusted_y)


class LeftMidfielderRoleBehaviour(MidfielderBaseBehaviour):
    """Left midfielder / Left winger AI."""

    def __init__(self) -> None:
        """Instantiate the left-sided midfielder behaviour."""
        super().__init__(role="LM", side="left")

    def _adjust_support_position(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Stay wide on the left flank."""
        from touchline.engine.physics import Vector2D

        # Maintain width on left touchline
        mid_cfg = ENGINE_CONFIG.role.midfielder
        adjusted_y = max(position.y, mid_cfg.left_width)  # Stay wide left
        return Vector2D(position.x, adjusted_y)
