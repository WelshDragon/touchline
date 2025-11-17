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

import random
from typing import TYPE_CHECKING, List, Optional

from touchline.engine.config import ENGINE_CONFIG

from .base import RoleBehaviour

if TYPE_CHECKING:
    from touchline.engine.config import MidfielderConfig
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

            # Attempt interception if ball is loose and moving
            loose_ball = not any(
                self.has_ball_possession(p, ball) for p in all_players
            )
            if loose_ball and ball.velocity.magnitude() > 2.0:
                if self.attempt_interception(player, ball, all_players, speed_attr, dt):
                    return

            # Press opponent if they have ball
            if self.should_press(
                player, ball, all_players, stamina_threshold=mid_cfg.press_stamina_threshold
            ):
                self._log_decision(player, "press_opponent")
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
        """Check if the midfielder's team currently controls the ball.

        Parameters
        ----------
        player : PlayerMatchState
            Midfielder querying team state.
        ball : BallState
            Ball state shared by the simulation.
        all_players : List[PlayerMatchState]
            All players on the pitch.

        Returns
        -------
        bool
            ``True`` when any teammate (including the player) has possession
            or if the ball was last touched by a teammate (includes passes in flight).
        """
        # Check if any teammate currently has the ball
        teammates = self.get_teammates(player, all_players) + [player]

        for teammate in teammates:
            if self.has_ball_possession(teammate, ball):
                return True
        
        # Also check if ball was last touched by a teammate (for passes in flight)
        last_toucher = self._player_by_id(ball.last_touched_by)
        if last_toucher and last_toucher.team == player.team:
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
        """Decide the next action when the midfielder controls the ball.

        Parameters
        ----------
        player : PlayerMatchState
            Ball carrier.
        ball : BallState
            Shared ball state.
        all_players : List[PlayerMatchState]
            All players used for decision making.
        passing_attr : int
            Passing attribute rating (0-100).
        vision_attr : int
            Vision attribute rating (0-100).
        shooting_attr : int
            Shooting attribute rating (0-100).
        dribbling_attr : int
            Dribbling attribute rating (0-100).
        current_time : float
            Simulation timestamp for recorded actions.
        """
        from touchline.models.player import Player

        # First, ensure player is close enough to the ball to perform actions
        player_model: Player = next((p for p in player.team.players if p.player_id == player.player_id), None)
        if player_model and self._move_closer_to_ball(player, ball, player_model.attributes.speed):
            return
        
        # Check if in shooting position
        if self.should_shoot(player, ball, shooting_attr):
            self.execute_shot(player, ball, shooting_attr, current_time)
            return

        opponents = self.get_opponents(player, all_players)
        mid_cfg = ENGINE_CONFIG.role.midfielder
        under_pressure = self._is_under_pressure(player, opponents)
        forced_release = (
            mid_cfg.space_move_patience_loops > 0
            and player.space_probe_loops >= mid_cfg.space_move_patience_loops
        )

        goal_pos = self.get_goal_position(player)
        player_distance_to_goal = player.state.position.distance_to(goal_pos)

        target = self.find_best_pass_target(player, ball, all_players, vision_attr, passing_attr)
        progress_gain = 0.0
        if target:
            progress_gain = player_distance_to_goal - target.state.position.distance_to(goal_pos)

        pass_viable = bool(
            target
            and (
                progress_gain >= mid_cfg.pass_progress_break_threshold
                or under_pressure
                or forced_release
            )
        )

        if player.tempo_hold_until > player.match_time:
            if forced_release:
                self._log_decision(player, "hold_window_cancel", loops=player.space_probe_loops)
                player.tempo_hold_until = 0.0
            elif pass_viable:
                player.tempo_hold_until = 0.0
            else:
                self._log_decision(player, "shield_wait", reason="tempo_hold_active")
                self._reset_space_move(player, reset_history=False)
                self._shield_ball(player, ball)
                return

        if pass_viable and target:
            self._log_decision(
                player,
                "execute_pass",
                target=target.player_id,
                progress=f"{progress_gain:.1f}m",
            )
            self._reset_space_move(player)
            self.execute_pass(player, target, ball, passing_attr, current_time)
            return

        lane_blocked = self._forward_lane_blocked(
            player,
            opponents,
            max_distance=mid_cfg.hold_lane_block_distance,
            half_width=mid_cfg.hold_lane_block_width,
            min_blockers=mid_cfg.hold_blocker_count,
        )

        if not lane_blocked:
            self._log_decision(player, "dribble_lane_clear")
            self._reset_space_move(player)
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
            return

        if under_pressure:
            relief_target = self._find_relief_pass(player, ball, all_players, opponents, vision_attr)
            if relief_target:
                self._log_decision(player, "relief_pass", target=relief_target.player_id)
                self._reset_space_move(player)
                self.execute_pass(player, relief_target, ball, passing_attr, current_time)
                return

            if self._attempt_backpass(player, ball, all_players, opponents, passing_attr, current_time):
                self._reset_space_move(player)
                return

            self._log_decision(player, "dribble_under_pressure")
            self._reset_space_move(player)
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
            return

        if forced_release:
            self._log_decision(
                player,
                "probe_breakout",
                loops=player.space_probe_loops,
            )
            self._reset_space_move(player)
        else:
            if self._move_to_support_space(player, ball, opponents, mid_cfg):
                return

            if self._begin_hold_window(player, ball, mid_cfg):
                return

        if self._attempt_backpass(player, ball, all_players, opponents, passing_attr, current_time):
            self._reset_space_move(player)
            return

        # Dribble forward if no good pass
        self._log_decision(player, "dribble_default", lane_blocked=lane_blocked)
        self._reset_space_move(player)
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
        """Dribble the ball forward when no high-quality pass is available.

        Parameters
        ----------
        player : PlayerMatchState
            Ball carrier.
        ball : BallState
            Shared ball state manipulated by the dribble.
        dribbling_attr : int
            Dribbling attribute rating (0-100).
        passing_attr : int
            Passing attribute rating (0-100) for bailout passes.
        vision_attr : int
            Vision attribute rating (0-100) for relief passes.
        all_players : List[PlayerMatchState]
            All players for evaluating outlets.
        opponents : List[PlayerMatchState]
            Opposing players applying pressure.
        current_time : float
            Simulation timestamp for any fallback passes.
        """
        from touchline.engine.physics import Vector2D

        self._reset_space_move(player)
        goal_pos = self.get_goal_position(player)
        mid_cfg = ENGINE_CONFIG.role.midfielder

        # Check for nearby pressure
        under_pressure = self._is_under_pressure(player, opponents, radius=mid_cfg.pressure_radius)

        if under_pressure and dribbling_attr < mid_cfg.pressure_dribble_threshold:
            relief_target = self._find_relief_pass(player, ball, all_players, opponents, vision_attr)

            if relief_target:
                self._log_decision(player, "relief_pass", target=relief_target.player_id, context="dribble_abort")
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

    def _move_to_support_space(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        opponents: List["PlayerMatchState"],
        mid_cfg: "MidfielderConfig",
    ) -> bool:
        """Glide laterally to open passing windows before initiating a hold.

        Parameters
        ----------
        player : PlayerMatchState
            Midfielder responsible for probing for space.
        ball : BallState
            Ball instance pinned to the player's feet while drifting.
        opponents : List[PlayerMatchState]
            Opponents whose pressure determines whether probing is allowed.
        mid_cfg : MidfielderConfig
            Configuration section providing probe duration and speed.

        Returns
        -------
        bool
            ``True`` when the midfielder continues a lateral move this frame; ``False`` otherwise.
        """
        from touchline.engine.physics import Vector2D

        if self._is_under_pressure(player, opponents, radius=mid_cfg.hold_pressure_release_radius):
            self._reset_space_move(player)
            return False

        if player.space_move_heading and player.space_move_until <= player.match_time:
            # One probe cycle finished – allow callers to transition into hold logic.
            player.space_probe_loops += 1
            self._reset_space_move(player, reset_history=False)
            return False

        if not player.space_move_heading:
            goal_pos = self.get_goal_position(player)
            forward = goal_pos - player.state.position
            if forward.magnitude() <= 1e-5:
                return False

            lateral = Vector2D(-forward.y, forward.x)
            if lateral.magnitude() <= 1e-5:
                return False

            direction = lateral.normalize()
            side = 1 if random.random() < 0.5 else -1
            player.space_move_heading = direction * side
            player.space_move_until = player.match_time + mid_cfg.space_move_duration
            lane = "right" if side > 0 else "left"
            self._log_decision(
                player,
                "probe_space_move",
                side=lane,
                duration=f"{mid_cfg.space_move_duration:.2f}s",
            )

        if not player.space_move_heading:
            return False

        player.state.velocity = player.space_move_heading.normalize() * mid_cfg.space_move_speed
        ball.position = player.state.position
        ball.velocity = Vector2D(0, 0)
        return True

    def _is_under_pressure(
        self,
        player: "PlayerMatchState",
        opponents: List["PlayerMatchState"],
        radius: Optional[float] = None,
    ) -> bool:
        """Detect if any opponent is within pressing distance.

        Parameters
        ----------
        player : PlayerMatchState
            Player being evaluated.
        opponents : List[PlayerMatchState]
            Opposing players to test.
        radius : Optional[float]
            Custom pressure radius override in metres.

        Returns
        -------
        bool
            ``True`` when at least one opponent is within ``radius``.
        """
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
        """Find a nearby safe teammate to recycle possession under pressure.

        Parameters
        ----------
        player : PlayerMatchState
            Ball carrier.
        ball : BallState
            Shared ball state.
        all_players : List[PlayerMatchState]
            All players considered for outlets.
        opponents : List[PlayerMatchState]
            Defensive players applying pressure.
        vision_attr : int
            Vision attribute rating (0-100) scaling awareness.

        Returns
        -------
        Optional[PlayerMatchState]
            Safe outlet teammate, or ``None`` if no candidate meets the threshold.
        """
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

    def _begin_hold_window(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        mid_cfg: "MidfielderConfig",
    ) -> bool:
        """Start or maintain a patient hold to allow teammates to advance.

        Parameters
        ----------
        player : PlayerMatchState
            Player initiating the tempo hold.
        ball : BallState
            Ball state that should be shielded.
        mid_cfg : MidfielderConfig
            Configuration section controlling hold durations.

        Returns
        -------
        bool
            Always ``True`` to indicate the hold window is active.
        """
        started_hold = False
        if player.tempo_hold_until > player.match_time:
            hold_duration = max(0.0, player.tempo_hold_until - player.match_time)
        else:
            if player.match_time < player.tempo_hold_cooldown_until:
                return False

            hold_duration = random.uniform(mid_cfg.hold_min_duration, mid_cfg.hold_max_duration)
            player.tempo_hold_until = player.match_time + hold_duration
            player.tempo_hold_cooldown_until = player.tempo_hold_until + mid_cfg.hold_retry_cooldown
            started_hold = True

        self._reset_space_move(player, reset_history=False)
        self._shield_ball(player, ball, reason="hold_window")
        remaining = max(0.0, player.tempo_hold_until - player.match_time)
        if started_hold:
            self._log_decision(player, "hold_window_start", duration=f"{hold_duration:.2f}s")
        else:
            self._log_decision(player, "hold_window_active", remaining=f"{remaining:.2f}s")
        return True

    def _attempt_backpass(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        opponents: List["PlayerMatchState"],
        passing_attr: int,
        current_time: float,
    ) -> bool:
        """Recycle possession through defenders when forward lanes are blocked.

        Parameters
        ----------
        player : PlayerMatchState
            Midfielder seeking to reset play.
        ball : BallState
            Shared ball state.
        all_players : List[PlayerMatchState]
            All players available for selection.
        opponents : List[PlayerMatchState]
            Opposing players whose positions affect target selection.
        passing_attr : int
            Passing attribute rating (0-100).
        current_time : float
            Simulation timestamp recorded with the pass.

        Returns
        -------
        bool
            ``True`` when a backpass target was found and the pass executed.
        """
        target = self._select_backpass_target(player, all_players, opponents)
        if not target:
            return False

        self.execute_pass(player, target, ball, passing_attr, current_time)
        return True

    def _select_backpass_target(
        self,
        player: "PlayerMatchState",
        all_players: List["PlayerMatchState"],
        opponents: List["PlayerMatchState"],
    ) -> "PlayerMatchState" | None:
        """Pick a suitable teammate for a possession-reset backpass.

        Parameters
        ----------
        player : PlayerMatchState
            Midfielder looking backwards.
        all_players : List[PlayerMatchState]
            Available teammates.
        opponents : List[PlayerMatchState]
            Opponents whose positioning affects safety.

        Returns
        -------
        Optional[PlayerMatchState]
            Preferred backpass target, or ``None`` when no safe option exists.
        """
        teammates = self.get_teammates(player, all_players)
        mid_cfg = ENGINE_CONFIG.role.midfielder

        if not teammates:
            return None

        from touchline.engine.physics import Vector2D

        own_goal = self.get_own_goal_position(player)
        back_direction = (own_goal - player.state.position).normalize()
        lateral_axis = Vector2D(-back_direction.y, back_direction.x)

        best_target: Optional["PlayerMatchState"] = None
        best_score = 0.0

        for teammate in teammates:
            if teammate.player_role not in mid_cfg.backpass_roles:
                continue

            offset = teammate.state.position - player.state.position
            backward_distance = offset.x * back_direction.x + offset.y * back_direction.y
            if backward_distance < mid_cfg.backpass_min_offset or backward_distance > mid_cfg.backpass_max_distance:
                continue

            lateral_offset = abs(offset.x * lateral_axis.x + offset.y * lateral_axis.y)
            if lateral_offset > mid_cfg.hold_lane_block_width * 1.5:
                continue

            lane_quality = self.calculate_pass_lane_quality(player, teammate, opponents)
            nearest_opponent = min(
                (opp.state.position.distance_to(teammate.state.position) for opp in opponents),
                default=mid_cfg.backpass_space_divisor,
            )
            space_score = min(nearest_opponent / mid_cfg.backpass_space_divisor, 1.0)

            distance = player.state.position.distance_to(teammate.state.position)
            distance_score = 1 - min(distance / mid_cfg.backpass_max_distance, 1.0)

            total_score = (
                lane_quality * mid_cfg.backpass_lane_weight
                + space_score * mid_cfg.backpass_space_weight
                + distance_score * mid_cfg.backpass_distance_weight
            )

            if total_score > best_score:
                best_score = total_score
                best_target = teammate

        if best_score < mid_cfg.backpass_score_threshold:
            return None

        return best_target

    def _press_opponent(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        opponents: List["PlayerMatchState"],
        speed_attr: int,
        tackling_attr: int,
        dt: float,
    ) -> None:
        """Press the opponent currently in possession.

        Parameters
        ----------
        player : PlayerMatchState
            Midfielder applying pressure.
        ball : BallState
            Ball state used to confirm possession.
        opponents : List[PlayerMatchState]
            Opposing players who might hold the ball.
        speed_attr : int
            Speed attribute rating (0-100).
        tackling_attr : int
            Tackling attribute rating (0-100).
        dt : float
            Simulation timestep in seconds.
        """
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
        """Move to a supporting attacking lane.

        Parameters
        ----------
        player : PlayerMatchState
            Midfielder making the support run.
        ball : BallState
            Ball location guiding support depth.
        all_players : List[PlayerMatchState]
            Unused but kept for parity; may assist future spacing logic.
        vision_attr : int
            Vision attribute rating (0-100); placeholder for future expansions.
        speed_attr : int
            Speed attribute rating (0-100).
        dt : float
            Simulation timestep in seconds.
        """
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
        """Track back and support the defensive line.

        Parameters
        ----------
        player : PlayerMatchState
            Midfielder contributing defensively.
        ball : BallState
            Ball state guiding depth.
        all_players : List[PlayerMatchState]
            Currently unused; kept for parity with other helpers.
        tackling_attr : int
            Tackling attribute rating (0-100) reused for movement pace.
        dt : float
            Simulation timestep in seconds.
        """
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
        """Adjust support position based on side responsibilities.

        Parameters
        ----------
        player : PlayerMatchState
            Midfielder whose positioning is being tuned.
        position : Vector2D
            Base support location.
        ball : BallState
            Ball position informing any bias.

        Returns
        -------
        Vector2D
            Updated support coordinate.
        """
        return position


class RightMidfielderRoleBehaviour(MidfielderBaseBehaviour):
    """Right midfielder / Right winger AI."""

    def __init__(self) -> None:
        """Instantiate the right-sided midfielder behaviour."""
        super().__init__(role="RM", side="right")

    def _adjust_support_position(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Stay wide on the right flank while supporting.

        Parameters
        ----------
        player : PlayerMatchState
            Right-sided midfielder.
        position : Vector2D
            Proposed support coordinate.
        ball : BallState
            Ball state used for slight adjustments.

        Returns
        -------
        Vector2D
            Adjusted position respecting minimum right-side width.
        """
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
        """Stay central but shift slightly towards the ball.

        Parameters
        ----------
        player : PlayerMatchState
            Central midfielder.
        position : Vector2D
            Base support coordinate.
        ball : BallState
            Ball state influencing the lateral shift.

        Returns
        -------
        Vector2D
            Adjusted position constrained to the central corridor.
        """
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
        """Stay wide on the left flank while supporting.

        Parameters
        ----------
        player : PlayerMatchState
            Left-sided midfielder.
        position : Vector2D
            Initial support coordinate.
        ball : BallState
            Ball position for fine tuning.

        Returns
        -------
        Vector2D
            Updated position respecting minimum width on the left flank.
        """
        from touchline.engine.physics import Vector2D

        # Maintain width on left touchline
        mid_cfg = ENGINE_CONFIG.role.midfielder
        adjusted_y = max(position.y, mid_cfg.left_width)  # Stay wide left
        return Vector2D(position.x, adjusted_y)
