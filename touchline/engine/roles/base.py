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

from touchline.engine.config import ENGINE_CONFIG

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

    def _can_kick_ball(self, player: "PlayerMatchState", ball: "BallState") -> bool:
        """Only allow ball strikes when the player is within control range."""
        control_limit = ENGINE_CONFIG.possession.max_control_distance
        return player.state.position.distance_to(ball.position) <= control_limit

    def get_goal_position(self, player: "PlayerMatchState", pitch_width: Optional[float] = None) -> "Vector2D":
        """Get the opponent's goal position."""
        from touchline.engine.physics import Vector2D

        width = pitch_width if pitch_width is not None else ENGINE_CONFIG.pitch.width
        goal_x = width / 2 if player.is_home_team else -width / 2
        return Vector2D(goal_x, 0)

    def get_own_goal_position(self, player: "PlayerMatchState", pitch_width: Optional[float] = None) -> "Vector2D":
        """Get the player's own goal position."""
        from touchline.engine.physics import Vector2D

        width = pitch_width if pitch_width is not None else ENGINE_CONFIG.pitch.width
        goal_x = -width / 2 if player.is_home_team else width / 2
        return Vector2D(goal_x, 0)

    def should_shoot(self, player: "PlayerMatchState", ball: "BallState", shooting_attr: int) -> bool:
        """Decide if player should attempt a shot."""
        goal_pos = self.get_goal_position(player)
        distance_to_goal = player.state.position.distance_to(goal_pos)

        shoot_cfg = ENGINE_CONFIG.role.shooting

        # Don't shoot if too far (based on shooting ability)
        max_distance = shoot_cfg.max_distance_base + (shooting_attr / 100) * shoot_cfg.max_distance_bonus
        if distance_to_goal > max_distance:
            return False

        # More likely to shoot when closer
        shoot_probability = (1 - distance_to_goal / max_distance) * (shooting_attr / 100)

        # Require better angle when further away
        angle_quality = self.calculate_shot_angle_quality(player, goal_pos)
        if angle_quality < shoot_cfg.angle_threshold and distance_to_goal > shoot_cfg.long_range_distance:
            return False

        return random.random() < shoot_probability * shoot_cfg.probability_scale

    def calculate_shot_angle_quality(self, player: "PlayerMatchState", goal_pos: "Vector2D") -> float:
        """Calculate quality of shooting angle (0-1)."""
        from touchline.engine.physics import Vector2D

        # Check angles to goal posts
        post_width = ENGINE_CONFIG.pitch.goal_width / 2
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
        pass_cfg = ENGINE_CONFIG.role.passing

        for teammate in teammates:
            # Skip if too far based on passing ability
            distance = player.state.position.distance_to(teammate.state.position)
            max_pass_distance = pass_cfg.max_distance_base + (passing_attr / 100) * pass_cfg.max_distance_bonus

            if distance > max_pass_distance or distance < pass_cfg.min_distance:
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

            total_score = (
                lane_quality * pass_cfg.lane_weight
                + distance_score * pass_cfg.distance_weight
                + progress_score * pass_cfg.progress_weight
            ) * vision_factor

            recent_pairs = getattr(ball, "recent_pass_pairs", None)
            penalty = 0.0
            if recent_pairs:
                if recent_pairs and recent_pairs[-1] == (teammate.player_id, player.player_id):
                    penalty += pass_cfg.immediate_return_penalty

                for idx, pair in enumerate(reversed(recent_pairs), start=1):
                    if pair == (player.player_id, teammate.player_id):
                        decay = pass_cfg.repeat_penalty_base - pass_cfg.repeat_penalty_decay * (idx - 1)
                        penalty += max(0.0, decay)
                        break

            total_score -= penalty

            if total_score > best_score:
                best_score = total_score
                best_target = teammate

        return best_target if best_score > pass_cfg.score_threshold else None

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

        pass_cfg = ENGINE_CONFIG.role.passing

        for opponent in opponents:
            # Calculate perpendicular distance from opponent to pass line
            to_opponent = opponent.state.position - passer.state.position
            projection = (to_opponent.x * pass_vector.x + to_opponent.y * pass_vector.y) / (pass_distance**2)

            if 0 <= projection <= 1:  # Opponent is between passer and receiver
                perp_distance = abs(
                    (pass_vector.y * to_opponent.x - pass_vector.x * to_opponent.y) / pass_distance
                )

                # Reduce quality based on proximity
                if perp_distance < pass_cfg.lane_block_distance:
                    quality *= perp_distance / pass_cfg.lane_block_distance

        return quality

    def _project_ball_intercept(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        player_speed: float,
        *,
        max_time: Optional[float] = None,
        time_step: Optional[float] = None,
        reaction_buffer: Optional[float] = None,
        fallback_fraction: Optional[float] = None,
        fallback_cap: Optional[float] = None,
    ) -> "Vector2D":
        """Predict where the player can meet the ball along its path."""

        intercept_cfg = ENGINE_CONFIG.role.intercept

        max_time = intercept_cfg.max_time if max_time is None else max_time
        time_step = intercept_cfg.time_step if time_step is None else time_step
        reaction_buffer = intercept_cfg.reaction_buffer if reaction_buffer is None else reaction_buffer
        fallback_fraction = intercept_cfg.fallback_fraction if fallback_fraction is None else fallback_fraction
        fallback_cap = intercept_cfg.fallback_cap if fallback_cap is None else fallback_cap

        ball_speed = ball.velocity.magnitude()
        intercept = ball.position

        if ball_speed >= intercept_cfg.min_ball_speed:
            best_candidate: Optional["Vector2D"] = None

            steps = int(max_time / time_step)

            for i in range(1, steps + 1):
                t = i * time_step
                future_pos = ball.position + ball.velocity * t
                distance = player.state.position.distance_to(future_pos)

                if distance <= player_speed * (t + reaction_buffer):
                    best_candidate = future_pos
                    break

            if best_candidate is not None:
                intercept = best_candidate
            elif ball_speed > 0:
                direction = ball.velocity.normalize()
                travel = min(ball_speed * fallback_fraction, fallback_cap)
                intercept = ball.position + direction * travel

        return intercept

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

        # Predict an intercept point along the current ball trajectory so the
        # receiver meets the pass in stride instead of waiting for it to slow
        # down at their feet.
        from touchline.engine.physics import Vector2D

        receive_cfg = ENGINE_CONFIG.role.receive_pass

        player_speed = receive_cfg.player_speed_base + (speed_attr / 100) * receive_cfg.player_speed_attr_scale
        intercept = self._project_ball_intercept(player, ball, player_speed)

        to_intercept = intercept - player.state.position
        distance = to_intercept.magnitude()

        if distance < receive_cfg.stop_distance:
            # Close enough – let possession logic take over next frame.
            player.state.velocity = Vector2D(0, 0)
            return True

        direction = to_intercept.normalize()

        # Approximate maximum controllable speed while preparing to receive.
        base_speed = receive_cfg.move_base_speed
        max_speed = base_speed + (speed_attr / 100) * receive_cfg.move_attr_scale
        player.state.velocity = direction * max_speed
        player.current_target = intercept

        return True

    def _pursue_loose_ball(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        speed_attr: int,
    ) -> bool:
        """Send the nearest teammate after an unattached ball."""
        if ball.last_kick_recipient is not None:
            return False

        if any(p.state.is_with_ball for p in all_players):
            return False

        teammates = self.get_teammates(player, all_players) + [player]
        closest = min(teammates, key=lambda p: p.state.position.distance_to(ball.position))

        if closest is not player:
            return False

        from touchline.engine.physics import Vector2D

        loose_cfg = ENGINE_CONFIG.role.loose_ball

        player_speed = loose_cfg.player_speed_base + (speed_attr / 100) * loose_cfg.player_speed_attr_scale
        intercept = self._project_ball_intercept(
            player,
            ball,
            player_speed,
            max_time=loose_cfg.intercept_max_time,
            reaction_buffer=loose_cfg.intercept_reaction_buffer,
            fallback_fraction=loose_cfg.intercept_fallback_fraction,
            fallback_cap=loose_cfg.intercept_fallback_cap,
        )

        # If the ball is travelling toward the player, avoid projecting an intercept
        # point that sits behind them on the incoming path – that causes the awkward
        # backpedal when they are already well positioned.
        ball_speed = ball.velocity.magnitude()
        if ball_speed > 0:
            direction = ball.velocity.normalize()
            to_player = player.state.position - ball.position
            player_along = to_player.x * direction.x + to_player.y * direction.y
            intercept_along = (intercept - ball.position).x * direction.x + (intercept - ball.position).y * direction.y

            if player_along >= 0 and intercept_along > player_along:
                intercept = ball.position + direction * player_along

        to_intercept = intercept - player.state.position
        distance = to_intercept.magnitude()

        if distance < loose_cfg.stop_distance:
            player.state.velocity = Vector2D(0, 0)
            player.current_target = intercept
            return True

        direction = to_intercept.normalize()
        base_speed = loose_cfg.move_base_speed
        max_speed = base_speed + (speed_attr / 100) * loose_cfg.move_attr_scale
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
        if not self._can_kick_ball(player, ball):
            return

        distance = player.state.position.distance_to(target.state.position)

        # Calculate pass speed using a capped easing curve so long passes travel fast
        # enough without turning into shots, while short passes remain controlled.
        pass_cfg = ENGINE_CONFIG.role.passing
        accuracy_factor = passing_attr / 100
        min_speed = pass_cfg.power_min_base + pass_cfg.power_min_bonus * accuracy_factor
        max_speed = pass_cfg.power_max_base + pass_cfg.power_max_bonus * accuracy_factor
        distance_ratio = min(distance / pass_cfg.distance_norm, 1.0)
        eased_ratio = distance_ratio ** pass_cfg.easing_exponent
        power = min_speed + (max_speed - min_speed) * eased_ratio

        # Add slight inaccuracy based on passing attribute
        inaccuracy = (1 - accuracy_factor) * pass_cfg.inaccuracy_max
        target_pos = target.state.position
        offset_x = random.uniform(-inaccuracy, inaccuracy)
        offset_y = random.uniform(-inaccuracy, inaccuracy)

        from touchline.engine.physics import Vector2D

        adjusted_target = Vector2D(target_pos.x + offset_x, target_pos.y + offset_y)
        direction = (adjusted_target - player.state.position).normalize()

        ball.kick(
            direction,
            power,
            player.player_id,
            current_time,
            target.player_id,
            kicker_position=player.state.position,
        )

    def execute_shot(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        shooting_attr: int,
        current_time: float,
    ) -> None:
        """Execute a shot on goal."""
        if not self._can_kick_ball(player, ball):
            return
        goal_pos = self.get_goal_position(player)

        from touchline.engine.physics import Vector2D

        pitch_cfg = ENGINE_CONFIG.pitch
        shoot_cfg = ENGINE_CONFIG.role.shooting
        shooter_pos = player.state.position
        half_goal_width = pitch_cfg.goal_width / 2
        goal_corners = [
            Vector2D(goal_pos.x, half_goal_width),
            Vector2D(goal_pos.x, -half_goal_width),
        ]

        goalkeeper_pos: Optional[Vector2D] = None
        if self._current_all_players:
            opponents = [p for p in self._current_all_players if p.team != player.team]
            goalkeeper = next((p for p in opponents if p.player_role == "GK"), None)
            if goalkeeper is None and opponents:
                goalkeeper = min(opponents, key=lambda opp: opp.state.position.distance_to(goal_pos))
            if goalkeeper is not None:
                goalkeeper_pos = goalkeeper.state.position

        def _point_to_segment_distance(point: Vector2D, start: Vector2D, end: Vector2D) -> float:
            segment = end - start
            seg_len_sq = segment.x * segment.x + segment.y * segment.y
            if seg_len_sq <= 1e-9:
                return (point - start).magnitude()
            t = ((point.x - start.x) * segment.x + (point.y - start.y) * segment.y) / seg_len_sq
            t = max(0.0, min(1.0, t))
            closest = Vector2D(start.x + segment.x * t, start.y + segment.y * t)
            return (point - closest).magnitude()

        if goalkeeper_pos is not None:
            best_corner = max(
                goal_corners,
                key=lambda corner: _point_to_segment_distance(goalkeeper_pos, shooter_pos, corner),
            )
        else:
            best_corner = max(goal_corners, key=lambda corner: abs(corner.y - shooter_pos.y))

        accuracy = shooting_attr / 100
        inset_range = shoot_cfg.goal_offset_range * (1 - accuracy)
        inset_amount = random.uniform(0.0, inset_range) if inset_range > 0 else 0.0

        target_y = best_corner.y
        if abs(best_corner.y) > 1e-6:
            target_y = best_corner.y - math.copysign(inset_amount, best_corner.y)

        depth_bias = shoot_cfg.corner_depth_bias
        depth_variation = shoot_cfg.corner_depth_spread * (1 - accuracy)
        depth_offset = depth_bias + (random.uniform(0.0, depth_variation) if depth_variation > 0 else 0.0)
        target_x = best_corner.x + math.copysign(depth_offset, best_corner.x)

        target = Vector2D(target_x, target_y)
        direction = (target - shooter_pos).normalize()

        # Power based on distance and shooting ability
        distance = player.state.position.distance_to(goal_pos)
        raw_power = distance * shoot_cfg.power_distance_scale + shoot_cfg.power_base
        power = min(shoot_cfg.power_clamp, raw_power)
        power *= shoot_cfg.power_accuracy_base + accuracy * shoot_cfg.power_accuracy_scale

        ball.kick(
            direction,
            power,
            player.player_id,
            current_time,
            kicker_position=player.state.position,
        )

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
        ball: Optional["BallState"] = None,
        sprint: bool = False,
        intent: Optional[str] = None,
    ) -> None:
        """Move player towards target position with role-specific pacing."""
        movement_cfg = ENGINE_CONFIG.player_movement
        profile = movement_cfg.role_profiles.get(player.player_role, movement_cfg.role_profiles["default"])

        attr_ratio = max(0.0, min(1.0, speed_attr / 100))
        speed_scale = movement_cfg.speed_scale_min + (
            movement_cfg.speed_scale_max - movement_cfg.speed_scale_min
        ) * attr_ratio
        acceleration_scale = movement_cfg.acceleration_scale_min + (
            movement_cfg.acceleration_scale_max - movement_cfg.acceleration_scale_min
        ) * attr_ratio
        deceleration_scale = movement_cfg.deceleration_scale_min + (
            movement_cfg.deceleration_scale_max - movement_cfg.deceleration_scale_min
        ) * attr_ratio

        jog_speed = profile.jog_speed * speed_scale
        run_speed = profile.run_speed * speed_scale
        sprint_speed = profile.sprint_speed * speed_scale
        base_acceleration = profile.acceleration * acceleration_scale
        base_deceleration = profile.deceleration * deceleration_scale

        resolved_intent = intent.lower() if intent else ("press" if sprint else "support")

        if resolved_intent in {"press", "tackle", "chase"}:
            role_speed = sprint_speed
            acceleration = base_acceleration * movement_cfg.intent_press_accel_scale
            deceleration = base_deceleration * movement_cfg.intent_press_decel_scale
            arrive_radius = movement_cfg.arrive_radius * movement_cfg.intent_press_arrive_scale
        elif resolved_intent == "mark":
            role_speed = run_speed
            acceleration = base_acceleration * movement_cfg.intent_mark_accel_scale
            deceleration = base_deceleration * movement_cfg.intent_mark_decel_scale
            arrive_radius = movement_cfg.arrive_radius * movement_cfg.intent_mark_arrive_scale
        elif resolved_intent in {"maintain", "shape", "hold"}:
            role_speed = jog_speed
            acceleration = base_acceleration * movement_cfg.intent_shape_accel_scale
            deceleration = base_deceleration * movement_cfg.intent_shape_decel_scale
            arrive_radius = movement_cfg.arrive_radius * movement_cfg.intent_shape_arrive_scale
        else:  # support, drift, default fallback
            blend = max(0.0, min(1.0, movement_cfg.intent_support_speed_blend))
            role_speed = jog_speed + (run_speed - jog_speed) * blend
            acceleration = base_acceleration * movement_cfg.intent_support_accel_scale
            deceleration = base_deceleration * movement_cfg.intent_support_decel_scale
            arrive_radius = movement_cfg.arrive_radius * movement_cfg.intent_support_arrive_scale

        max_speed = role_speed

        # Apply light lane preservation and teammate spacing for outfield players
        from touchline.engine.physics import Vector2D

        adjusted_target = Vector2D(target.x, target.y)

        if getattr(player, "player_role", "") != "GK":
            adjusted_target = self._apply_lane_spacing(player, adjusted_target)

        if ball is not None:
            adjusted_target = self._apply_possession_support(player, adjusted_target, ball)

        player.current_target = adjusted_target

        if not player.state.is_with_ball:
            player.off_ball_state = resolved_intent

        player.state.move_towards(adjusted_target, dt, max_speed, acceleration, deceleration, arrive_radius)

    def _apply_possession_support(
        self,
        player: "PlayerMatchState",
        target: "Vector2D",
        ball: "BallState",
    ) -> "Vector2D":
        """Push teammates forward when their side is in possession."""
        if player.state.is_with_ball:
            return target

        possessor: Optional["PlayerMatchState"] = None

        if ball.last_touched_by is not None and self._current_all_players:
            possessor = next(
                (p for p in self._current_all_players if p.player_id == ball.last_touched_by),
                None,
            )

        if possessor is None or possessor.team != player.team:
            return target

        # Goal direction is positive X for home, negative for away.
        goal_dir = 1.0 if player.is_home_team else -1.0
        relative_target = target.x * goal_dir
        relative_ball = ball.position.x * goal_dir
        relative_possessor = possessor.state.position.x * goal_dir

        support_cfg = ENGINE_CONFIG.role.possession_support
        push_distance, trailing_buffer, forward_margin = self._support_profile(player)
        if push_distance <= 0 and forward_margin <= 0:
            return target

        from touchline.engine.physics import Vector2D

        # Encourage players to close the space to the ball while respecting role-based buffers.
        gap_to_possessor = max(0.0, relative_possessor - relative_target)
        desired_relative = relative_target + min(
            push_distance,
            gap_to_possessor * support_cfg.gap_weight + push_distance * support_cfg.push_bias,
        )

        # Clamp relative X within trailing buffer behind the ball and a forward margin ahead of it.
        max_forward = relative_ball + forward_margin
        min_forward = relative_ball - trailing_buffer
        new_relative = max(min(desired_relative, max_forward), min_forward)

        if forward_margin > 0:
            # Once we're moving into the attacking half, bias towards getting in front of the ball.
            ahead_factor = (
                support_cfg.ahead_factor_low
                if relative_ball < support_cfg.ahead_threshold
                else support_cfg.ahead_factor_high
            )
            min_ahead = relative_ball + forward_margin * ahead_factor
            new_relative = max(new_relative, min_ahead)
            new_relative = min(new_relative, max_forward)

        if new_relative <= relative_target + 1e-3:
            return target

        return Vector2D(new_relative * goal_dir, target.y)

    def _support_profile(self, player: "PlayerMatchState") -> tuple[float, float, float]:
        """Return (push_distance, trailing_buffer, forward_margin) for support."""
        profiles = ENGINE_CONFIG.role.support_profiles
        role = player.player_role
        return profiles.get(role, profiles["default"])

    def _apply_lane_spacing(
        self,
        player: "PlayerMatchState",
        target: "Vector2D",
        lane_weight: Optional[float] = None,
        min_spacing: Optional[float] = None,
    ) -> "Vector2D":
        """Blend target with base lane and push away from nearby teammates to avoid crowding."""
        from touchline.engine.physics import Vector2D

        adjusted = Vector2D(target.x, target.y)

        lane_cfg = ENGINE_CONFIG.role.lane_spacing
        lane_weight = lane_cfg.lane_weight if lane_weight is None else lane_weight
        min_spacing = lane_cfg.min_spacing if min_spacing is None else min_spacing
        separation_scale = lane_cfg.separation_scale

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
                    separation = separation + push_dir * (push_strength * min_spacing * separation_scale)

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
        defensive_cfg = ENGINE_CONFIG.role.defensive

        if ball_to_goal_distance > defensive_cfg.far_threshold:
            target_x = base_position.x
        elif ball_to_goal_distance < defensive_cfg.close_threshold:
            close_offset = defensive_cfg.close_offset if own_goal.x < 0 else -defensive_cfg.close_offset
            target_x = own_goal.x + close_offset
        else:
            # Interpolate between base and advanced position
            span = defensive_cfg.far_threshold - defensive_cfg.close_threshold
            t = (defensive_cfg.far_threshold - ball_to_goal_distance) / max(span, 1e-6)
            advanced_offset = defensive_cfg.advanced_offset if own_goal.x < 0 else -defensive_cfg.advanced_offset
            advanced_x = own_goal.x + advanced_offset
            target_x = base_position.x * (1 - t) + advanced_x * t

        # Maintain individual Y position from formation (with slight adjustment for ball)
        # Each player keeps their horizontal spacing
        ball_y_offset = (ball.position.y - base_position.y) * defensive_cfg.y_pull_factor
        target_y = base_position.y + ball_y_offset
        
        return Vector2D(target_x, target_y)

    def should_press(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        stamina_threshold: Optional[float] = None,
        distance_threshold: Optional[float] = None,
    ) -> bool:
        """Decide if player should press the opponent with the ball."""
        press_cfg = ENGINE_CONFIG.role.pressing
        stamina_threshold = press_cfg.stamina_threshold if stamina_threshold is None else stamina_threshold
        distance_threshold = press_cfg.distance_threshold if distance_threshold is None else distance_threshold

        if player.state.stamina < stamina_threshold:
            return False

        distance = self.distance_to_ball(player, ball)

        # Press if reasonably close and ball is with opponent
        if distance < distance_threshold:
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
        search_radius: Optional[float] = None,
    ) -> "Vector2D":
        """Find space away from other players."""
        from touchline.engine.physics import Vector2D

        space_cfg = ENGINE_CONFIG.role.space_finding
        search_radius = space_cfg.search_radius if search_radius is None else search_radius

        # Start with preferred direction
        best_pos = player.state.position + preferred_direction.normalize() * 10

        # Check crowding
        min_crowding = float("inf")

        for angle in range(0, 360, space_cfg.angle_step):
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
