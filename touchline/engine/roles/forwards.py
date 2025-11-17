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
"""Role behaviours for centre forwards and wide attackers."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, List, Optional

from touchline.engine.config import ENGINE_CONFIG

from .base import RoleBehaviour

if TYPE_CHECKING:
    from touchline.engine.config import ForwardConfig
    from touchline.engine.physics import BallState, Vector2D
    from touchline.engine.player_state import PlayerMatchState


class ForwardBaseBehaviour(RoleBehaviour):
    """Base forward AI with attacking and goal-scoring behaviors.

    Parameters
    ----------
    role : str
        Role code assigned to the forward (for example ``"CF"``).
    side : str
        Field side the forward typically occupies (``"left"``, ``"right"``, or ``"central"``).
    """

    def decide_action(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        dt: float,
    ) -> None:
        """Coordinate attacking decisions for the current frame.

        Parameters
        ----------
        player : PlayerMatchState
            Controlled forward whose behaviour is being updated.
        ball : BallState
            Current ball state for the frame.
        all_players : List[PlayerMatchState]
            Snapshot of all player states participating in the match.
        dt : float
            Simulation timestep in seconds since the previous update.
        """
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

        hold_remaining = max(0.0, player.tempo_hold_until - player.match_time)
        player_has_ball = self.has_ball_possession(player, ball)
        team_controls = self._team_has_possession(player, ball, all_players)
        self._log_decision(
            player,
            "decide_action",
            has_ball=player_has_ball,
            team_possession=team_controls,
            hold_remaining=f"{hold_remaining:.2f}s",
        )

        try:
            if self._move_to_receive_pass(player, ball, speed_attr, dt):
                self._log_decision(
                    player,
                    "move_to_receive_pass",
                    target=ball.last_kick_recipient or "unknown",
                )
                return

            if self._pursue_loose_ball(player, ball, all_players, speed_attr):
                self._log_decision(
                    player,
                    "pursue_loose_ball",
                    ball_speed=f"{ball.velocity.magnitude():.2f}mps",
                )
                return

            # If forward has the ball, look to score or pass
            if player_has_ball:
                self._log_decision(player, "attack_with_ball_entry")
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
            if team_controls:
                # Make attacking run
                self._log_decision(player, "make_attacking_run")
                self._make_attacking_run(player, ball, all_players, speed_attr, positioning_attr, dt)
                return

            # Attempt interception only if opponent has ball or it's truly loose
            # Don't intercept during own team's passes (team_controls already checked above)
            loose_ball = not any(
                self.has_ball_possession(p, ball) for p in all_players
            )
            if loose_ball and ball.velocity.magnitude() > 2.0:
                if self.attempt_interception(player, ball, all_players, speed_attr, dt):
                    return

            # Press defenders when out of possession
            if self._should_press_defender(player, ball, all_players):
                self._log_decision(player, "press_defender")
                self._press_defender(player, ball, all_players, speed_attr, dt)
                return

            # Hold position and wait for opportunity
            self._log_decision(player, "hold_position")
            self._hold_position(player, all_players, positioning_attr, speed_attr, dt)
        finally:
            self._current_all_players = None

    def _team_has_possession(
        self, player: "PlayerMatchState", ball: "BallState", all_players: List["PlayerMatchState"]
    ) -> bool:
        """Determine whether the attacking team currently controls the ball.

        Parameters
        ----------
        player : PlayerMatchState
            Forward whose team context is being inspected.
        ball : BallState
            Live ball state for the current frame.
        all_players : List[PlayerMatchState]
            Snapshot of every player on the pitch used to locate ball carriers.

        Returns
        -------
        bool
            ``True`` if player's team has possession (persists during passes).
        """
        # Use the match engine's team possession state which persists during passes
        if ball.possessing_team_side is None:
            return False
        
        player_side = "home" if player.is_home_team else "away"
        return ball.possessing_team_side == player_side

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
        """Resolve the forward's decision tree when they control the ball.

        Parameters
        ----------
        player : PlayerMatchState
            Forward currently in possession.
        ball : BallState
            Shared ball state containing last touch metadata.
        all_players : List[PlayerMatchState]
            All participants on the pitch for spatial queries.
        shooting_attr : int
            Shooter rating guiding whether finishing attempts are viable.
        dribbling_attr : int
            Dribbling attribute controlling carry speed and press resistance.
        passing_attr : int
            Passing quality used when executing passes.
        vision_attr : int
            Vision rating that unlocks progressive or pressure-release passes.
        current_time : float
            Simulation timestamp used for kick timing.
        """
        from touchline.models.player import Player

        # First, ensure player is close enough to the ball to perform actions
        player_model: Player = next((p for p in player.team.players if p.player_id == player.player_id), None)
        if player_model and self._move_closer_to_ball(player, ball, player_model.attributes.speed):
            return
        
        goal_pos = self.get_goal_position(player)
        distance_to_goal = player.state.position.distance_to(goal_pos)

        opponents = self.get_opponents(player, all_players)
        fwd_cfg = ENGINE_CONFIG.role.forward
        under_pressure = self._is_under_pressure(player, opponents)
        hold_remaining = max(0.0, player.tempo_hold_until - player.match_time)
        forced_release = (
            fwd_cfg.space_move_patience_loops > 0
            and player.space_probe_loops >= fwd_cfg.space_move_patience_loops
        )
        self._log_decision(
            player,
            "attack_with_ball_state",
            dist_goal=f"{distance_to_goal:.1f}m",
            pressure=under_pressure,
            hold_remaining=f"{hold_remaining:.2f}s",
        )

        # Prioritize shooting if in good position
        if distance_to_goal < fwd_cfg.shoot_distance_threshold:
            if self.should_shoot(player, ball, shooting_attr):
                self._log_decision(player, "shoot_attempt", dist_goal=f"{distance_to_goal:.1f}m")
                self._reset_space_move(player)
                self.execute_shot(player, ball, shooting_attr, current_time)
                return
        else:
            self._log_decision(player, "skip_shoot_check", 
                             dist=f"{distance_to_goal:.1f}m", 
                             threshold=f"{fwd_cfg.shoot_distance_threshold:.1f}m")

        # Look for best pass option
        best_target = self.find_best_pass_target(
            player,
            ball,
            all_players,
            vision_attr,
            passing_attr,
        )

        progress_gain = 0.0
        if best_target:
            progress_gain = distance_to_goal - best_target.state.position.distance_to(goal_pos)

        if best_target:
            self._log_decision(
                player,
                "pass_option",
                target=best_target.player_id,
                progress=f"{progress_gain:.1f}m",
                under_pressure=under_pressure,
            )

        hold_release_window = bool(
            best_target
            and player.tempo_hold_until > player.match_time
            and fwd_cfg.hold_force_release_time > 0
            and hold_remaining <= fwd_cfg.hold_force_release_time
            and progress_gain >= fwd_cfg.hold_force_release_progress
        )

        pass_viable = bool(
            best_target
            and (
                progress_gain >= fwd_cfg.pass_progress_break_threshold
                or (
                    under_pressure
                    and vision_attr >= fwd_cfg.vision_pressure_release_threshold
                )
                or forced_release
                or hold_release_window
            )
        )

        if player.tempo_hold_until > player.match_time:
            if forced_release or hold_release_window:
                cancel_reason = "probe_patience" if forced_release else "hold_patience"
                log_payload = {"reason": cancel_reason}
                if forced_release:
                    log_payload["loops"] = player.space_probe_loops
                self._log_decision(player, "hold_window_cancel", **log_payload)
                player.tempo_hold_until = 0.0
                reset_history = forced_release
                self._reset_space_move(player, reset_history=reset_history)
            elif pass_viable:
                player.tempo_hold_until = 0.0
            else:
                self._log_decision(player, "shield_wait", reason="tempo_hold_active")
                self._reset_space_move(player, reset_history=False)
                self._shield_ball(player, ball, reason="tempo_hold_active")
                return

        if pass_viable and best_target:
            self._log_decision(
                player,
                "execute_pass",
                target=best_target.player_id,
                progress=f"{progress_gain:.1f}m",
            )
            self._reset_space_move(player)
            self.execute_pass(player, best_target, ball, passing_attr, current_time)
            return

        lane_blocked = self._forward_lane_blocked(
            player,
            opponents,
            max_distance=fwd_cfg.hold_lane_block_distance,
            half_width=fwd_cfg.hold_lane_block_width,
            min_blockers=fwd_cfg.hold_blocker_count,
        )

        if not lane_blocked:
            self._log_decision(player, "dribble_lane_clear")
            self._reset_space_move(player)
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
            return

        if under_pressure:
            relief_target = self._find_relief_pass(
                player,
                ball,
                all_players,
                opponents,
                vision_attr,
            )

            if relief_target:
                self._log_decision(player, "relief_pass", target=relief_target.player_id)
                self._reset_space_move(player)
                self.execute_pass(player, relief_target, ball, passing_attr, current_time)
                return

            if self._attempt_backpass(player, ball, all_players, opponents, passing_attr, current_time):
                self._reset_space_move(player)
                return

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
            return

        if self._move_to_support_space(player, ball, opponents, fwd_cfg):
            return

        if self._begin_hold_window(player, ball, fwd_cfg):
            return

        if self._attempt_backpass(player, ball, all_players, opponents, passing_attr, current_time):
            self._reset_space_move(player)
            return

        # Try to recycle possession if being swarmed
        relief_target = None
        if under_pressure:
            relief_target = self._find_relief_pass(
                player,
                ball,
                all_players,
                opponents,
                vision_attr,
            )

        if relief_target:
            self._log_decision(player, "relief_pass", target=relief_target.player_id)
            self._reset_space_move(player)
            self.execute_pass(player, relief_target, ball, passing_attr, current_time)
            return

        # Dribble towards goal
        self._log_decision(player, "dribble_default", lane_blocked=lane_blocked)
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
        """Carry the ball toward goal or recycle if pressure is overwhelming.

        Parameters
        ----------
        player : PlayerMatchState
            Ball-carrying forward.
        ball : BallState
            Shared ball state to update while dribbling.
        dribbling_attr : int
            Attribute influencing dribble velocity and pressure escapes.
        passing_attr : int
            Passing rating applied if the dribble is aborted.
        vision_attr : int
            Vision level used when searching for relief passes.
        all_players : List[PlayerMatchState]
            Full player set used for teammate/opponent lookups.
        opponents : List[PlayerMatchState]
            Opposing players applying pressure.
        current_time : float
            Simulation timestamp for pass execution.
        """
        from touchline.engine.physics import Vector2D

        self._reset_space_move(player)
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
                self._log_decision(player, "relief_pass", target=relief_target.player_id, context="dribble_pressure")
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
            self._log_decision(player, "dribble_escape", speed=f"{dribble_speed:.2f}")
        else:
            # Dribble directly at goal
            direction = (goal_pos - player.state.position).normalize()
            dribble_speed = (
                fwd_cfg.dribble_speed_base
                + (dribbling_attr / 100) * fwd_cfg.dribble_speed_attr_scale
            )
            player.state.velocity = direction * dribble_speed
            self._log_decision(player, "dribble_goal", speed=f"{dribble_speed:.2f}")

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
        """Sample headings to find the path with the lowest opponent pressure.

        Parameters
        ----------
        player : PlayerMatchState
            Forward attempting to break pressure.
        opponents : List[PlayerMatchState]
            Nearby defenders considered when measuring congestion.

        Returns
        -------
        Vector2D
            Unit vector pointing toward the most open space.
        """
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

    def _move_to_support_space(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        opponents: List["PlayerMatchState"],
        fwd_cfg: "ForwardConfig",
    ) -> bool:
        """Drift laterally to manufacture a passing angle before holding.

        Parameters
        ----------
        player : PlayerMatchState
            Forward currently in possession of the ball.
        ball : BallState
            Shared ball state kept under control during the probe.
        opponents : List[PlayerMatchState]
            Nearby defenders whose pressure cancels the probe.
        fwd_cfg : ForwardConfig
            Configuration values for lateral space moves.

        Returns
        -------
        bool
            ``True`` when the player moves laterally this frame; otherwise ``False``.
        """
        from touchline.engine.physics import Vector2D

        if self._is_under_pressure(player, opponents, radius=fwd_cfg.hold_pressure_release_radius):
            self._reset_space_move(player)
            return False

        if player.space_move_heading and player.space_move_until <= player.match_time:
            # Probe finished; track loops so patience logic can trigger forced releases.
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
            player.space_move_until = player.match_time + fwd_cfg.space_move_duration
            lane = "right" if side > 0 else "left"
            self._log_decision(
                player,
                "probe_space_move",
                side=lane,
                duration=f"{fwd_cfg.space_move_duration:.2f}s",
            )

        if not player.space_move_heading:
            return False

        player.state.velocity = player.space_move_heading.normalize() * fwd_cfg.space_move_speed
        ball.position = player.state.position
        ball.velocity = Vector2D(0, 0)
        return True


    def _begin_hold_window(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        fwd_cfg: "ForwardConfig",
    ) -> bool:
        """Initiate a temporary hold period so runners can advance.

        Parameters
        ----------
        player : PlayerMatchState
            Ball carrier initiating the hold.
        ball : BallState
            Ball instance that should be pinned to the player's feet.
        fwd_cfg : ForwardConfig
            Forward configuration supplying hold timing values.

        Returns
        -------
        bool
            Always ``True`` once the hold window is started to signal the caller to exit.
        """
        started_hold = False
        if player.tempo_hold_until > player.match_time:
            hold_duration = max(0.0, player.tempo_hold_until - player.match_time)
        else:
            if player.match_time < player.tempo_hold_cooldown_until:
                return False

            hold_duration = random.uniform(fwd_cfg.hold_min_duration, fwd_cfg.hold_max_duration)
            player.tempo_hold_until = player.match_time + hold_duration
            player.tempo_hold_cooldown_until = player.tempo_hold_until + fwd_cfg.hold_retry_cooldown
            started_hold = True

        self._reset_space_move(player)
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
        """Play a recycling pass to a deeper teammate when possible.

        Parameters
        ----------
        player : PlayerMatchState
            Forward relinquishing the ball.
        ball : BallState
            Ball to kick toward the recycling target.
        all_players : List[PlayerMatchState]
            Squad list used to locate qualifying teammates.
        opponents : List[PlayerMatchState]
            Defenders used when scoring passing lanes.
        passing_attr : int
            Passing quality that influences pass execution.
        current_time : float
            Simulation timestamp for the pass animation.

        Returns
        -------
        bool
            ``True`` if a back-pass was executed, otherwise ``False`` to continue evaluation.
        """
        target = self._select_backpass_target(player, all_players, opponents)
        if not target:
            self._log_decision(player, "backpass_unavailable")
            return False

        self._log_decision(player, "backpass_execute", target=target.player_id)
        self.execute_pass(player, target, ball, passing_attr, current_time)
        return True

    def _select_backpass_target(
        self,
        player: "PlayerMatchState",
        all_players: List["PlayerMatchState"],
        opponents: List["PlayerMatchState"],
    ) -> "PlayerMatchState" | None:
        """Score defenders and midfielders to identify the safest recycling target.

        Parameters
        ----------
        player : PlayerMatchState
            Forward under pressure.
        all_players : List[PlayerMatchState]
            All active players used to filter teammates.
        opponents : List[PlayerMatchState]
            Opposing players affecting lane and space scores.

        Returns
        -------
        PlayerMatchState | None
            Best back-pass recipient or ``None`` when no safe outlet exists.
        """
        teammates = self.get_teammates(player, all_players)
        fwd_cfg = ENGINE_CONFIG.role.forward

        if not teammates:
            return None

        from touchline.engine.physics import Vector2D

        own_goal = self.get_own_goal_position(player)
        back_direction = (own_goal - player.state.position).normalize()
        lateral_axis = Vector2D(-back_direction.y, back_direction.x)

        best_target: Optional["PlayerMatchState"] = None
        best_score = 0.0

        trace_enabled = self._player_debugger(player) is not None
        trace_candidates: list[tuple[int, float, float, float]] = []

        for teammate in teammates:
            if teammate.player_role not in fwd_cfg.backpass_roles:
                continue

            offset = teammate.state.position - player.state.position
            backward_distance = offset.x * back_direction.x + offset.y * back_direction.y
            if backward_distance < fwd_cfg.backpass_min_offset or backward_distance > fwd_cfg.backpass_max_distance:
                continue

            lateral = abs(offset.x * lateral_axis.x + offset.y * lateral_axis.y)
            if lateral > fwd_cfg.hold_lane_block_width * 1.5:
                continue

            lane_quality = self.calculate_pass_lane_quality(player, teammate, opponents)
            nearest_opponent = min(
                (opp.state.position.distance_to(teammate.state.position) for opp in opponents),
                default=fwd_cfg.backpass_space_divisor,
            )
            space_score = min(nearest_opponent / fwd_cfg.backpass_space_divisor, 1.0)

            distance = player.state.position.distance_to(teammate.state.position)
            distance_score = 1 - min(distance / fwd_cfg.backpass_max_distance, 1.0)

            total_score = (
                lane_quality * fwd_cfg.backpass_lane_weight
                + space_score * fwd_cfg.backpass_space_weight
                + distance_score * fwd_cfg.backpass_distance_weight
            )

            if total_score > best_score:
                best_score = total_score
                best_target = teammate

            if trace_enabled:
                trace_candidates.append((teammate.player_id, total_score, lane_quality, space_score))

        if best_score < fwd_cfg.backpass_score_threshold:
            if trace_enabled and trace_candidates:
                preview = ", ".join(
                    f"#{pid} s={score:.2f} lane={lane:.2f} space={space:.2f}"
                    for pid, score, lane, space in sorted(trace_candidates, key=lambda item: item[1], reverse=True)[:3]
                )
                self._log_player_event(
                    player,
                    "decision",
                    f"backpass_candidates best=none score={best_score:.2f} opts=[{preview}]",
                )
            return None

        if trace_enabled and trace_candidates:
            preview = ", ".join(
                f"#{pid} s={score:.2f} lane={lane:.2f} space={space:.2f}"
                for pid, score, lane, space in sorted(trace_candidates, key=lambda item: item[1], reverse=True)[:3]
            )
            best_label = f"#{best_target.player_id}" if best_target else "none"
            self._log_player_event(
                player,
                "decision",
                f"backpass_candidates best={best_label} score={best_score:.2f} opts=[{preview}]",
            )

        return best_target

    def _make_attacking_run(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        speed_attr: int,
        positioning_attr: int,
        dt: float,
    ) -> None:
        """Guide the forward's movement while teammates build play.

        Parameters
        ----------
        player : PlayerMatchState
            Forward making the run.
        ball : BallState
            Current ball state to assess teammates in possession.
        all_players : List[PlayerMatchState]
            All player states for spacing and support logic.
        speed_attr : int
            Speed attribute controlling run pace.
        positioning_attr : int
            Positioning rating used when choosing run targets.
        dt : float
            Frame delta time for motion integration.
        """
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

        upcoming_recipient: Optional["PlayerMatchState"] = None
        if ball.last_kick_recipient is not None:
            upcoming_recipient = next(
                (p for p in all_players if p.player_id == ball.last_kick_recipient),
                None,
            )

        # Encourage earlier commitment if the ball is already on its way
        sprint = False
        if ball_carrier:
            distance_to_carrier = ball_carrier.state.position.distance_to(player.state.position)
            if distance_to_carrier < fwd_cfg.run_ballcarrier_distance:
                sprint = True

        if upcoming_recipient and upcoming_recipient.team == player.team:
            if upcoming_recipient.player_id == player.player_id:
                sprint = True
            else:
                distance_to_recipient = upcoming_recipient.state.position.distance_to(player.state.position)
                if distance_to_recipient < fwd_cfg.run_ballcarrier_distance * 0.8:
                    sprint = True

        # Adjust run target based on forward type
        run_target = self._adjust_attacking_run(player, run_target, ball, goal_pos)

        intent = "press" if sprint and ball_carrier else "support"
        self.move_to_position(
            player,
            run_target,
            speed_attr,
            dt,
            ball,
            sprint=bool(sprint),
            intent=intent,
        )

    def _find_attacking_space(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        goal_pos: "Vector2D",
        opponents: List["PlayerMatchState"],
        positioning_attr: int,
    ) -> "Vector2D":
        """Select a run destination that exploits gaps near the goal.

        Parameters
        ----------
        player : PlayerMatchState
            Forward making the supporting run.
        ball : BallState
            Ball state used to bias runs relative to possession.
        goal_pos : Vector2D
            Coordinates of the opponent goal mouth.
        opponents : List[PlayerMatchState]
            Defenders whose spacing determines viable channels.
        positioning_attr : int
            Positioning attribute influencing how aggressively to attack gaps.

        Returns
        -------
        Vector2D
            Target location for the player's next movement command.
        """
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

        # Clamp to pitch boundaries to prevent running off the pitch
        pitch_cfg = ENGINE_CONFIG.pitch
        max_x = pitch_cfg.width / 2 - 2.0  # 2m margin from edge
        max_y = pitch_cfg.height / 2 - 2.0
        
        # Log if clamping is needed
        unclamped_x = target_x
        target_x = max(-max_x, min(max_x, target_x))
        target_y = max(-max_y, min(max_y, target_y))
        
        if abs(unclamped_x - target_x) > 0.1:
            self._log_decision(
                player,
                "clamp_run_target",
                unclamped=f"{unclamped_x:.1f}",
                clamped=f"{target_x:.1f}",
                max_x=f"{max_x:.1f}"
            )

        return Vector2D(target_x, target_y)

    def _adjust_attacking_run(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState", goal_pos: "Vector2D"
    ) -> "Vector2D":
        """Tweak the baseline run target based on the forward's archetype.

        Parameters
        ----------
        player : PlayerMatchState
            Forward whose stylistic adjustments are being applied.
        position : Vector2D
            Initial run destination before the adjustment.
        ball : BallState
            Ball context that can influence lateral bias.
        goal_pos : Vector2D
            Opponent goal location used for centering logic.

        Returns
        -------
        Vector2D
            Adjusted run destination; subclasses override to customize behaviour.
        """
        return position

    def _should_press_defender(
        self, player: "PlayerMatchState", ball: "BallState", all_players: List["PlayerMatchState"]
    ) -> bool:
        """Check if the forward should trigger a press on a defender in possession.

        Parameters
        ----------
        player : PlayerMatchState
            Forward considering a press.
        ball : BallState
            Ball state used to see which opponent controls it.
        all_players : List[PlayerMatchState]
            All players used to locate defenders.

        Returns
        -------
        bool
            ``True`` when a nearby defender has the ball within the pressing radius.
        """
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
        """Move toward the defender in possession to apply pressure.

        Parameters
        ----------
        player : PlayerMatchState
            Forward executing the press.
        ball : BallState
            Ball state used to locate the current carrier.
        all_players : List[PlayerMatchState]
            List of players to identify the pressing target.
        speed_attr : int
            Speed rating used to determine closing velocity.
        dt : float
            Frame delta time for the chase movement.
        """
        opponents = self.get_opponents(player, all_players)

        for opp in opponents:
            if self.has_ball_possession(opp, ball):
                # Sprint towards opponent
                self.move_to_position(player, opp.state.position, speed_attr, dt, ball, sprint=True, intent="press")
                break

    def _add_position_variation(
        self, position: "Vector2D", magnitude: float = 0.5
    ) -> "Vector2D":
        """Add small random offset to avoid perfectly symmetrical positioning.

        Parameters
        ----------
        position : Vector2D
            Base target position.
        magnitude : float, default=0.5
            Maximum offset in metres.

        Returns
        -------
        Vector2D
            Position with random offset applied.
        """
        from touchline.engine.physics import Vector2D
        
        offset_x = random.uniform(-magnitude, magnitude)
        offset_y = random.uniform(-magnitude, magnitude)
        return Vector2D(position.x + offset_x, position.y + offset_y)

    def _hold_position(
        self,
        player: "PlayerMatchState",
        all_players: List["PlayerMatchState"],
        positioning_attr: int,
        speed_attr: int,
        dt: float,
    ) -> None:
        """Maintain attacking shape when no immediate action is required.

        Parameters
        ----------
        player : PlayerMatchState
            Forward being repositioned.
        all_players : List[PlayerMatchState]
            All players for context.
        positioning_attr : int
            Attribute influencing how aggressively to adjust toward ideal lanes.
        speed_attr : int
            Speed attribute for movement.
        dt : float
            Frame delta time for smoothing player motion.
        """
        from touchline.engine.physics import BallState
        
        # Get ball from match state (use dummy ball for movement)
        ball = BallState(player.state.position, player.state.velocity)

        # Stay high up the pitch with variation to prevent symmetry
        hold_position = self._add_position_variation(player.role_position, magnitude=0.8)

        self.move_to_position(player, hold_position, positioning_attr, dt, ball, sprint=False, intent="shape")

    def _is_under_pressure(
        self,
        player: "PlayerMatchState",
        opponents: List["PlayerMatchState"],
        radius: Optional[float] = None,
    ) -> bool:
        """Determine whether opponents are within a configurable pressure radius.

        Parameters
        ----------
        player : PlayerMatchState
            Forward being evaluated.
        opponents : List[PlayerMatchState]
            Opposing players to measure distances against.
        radius : Optional[float]
            Optional override for the pressure radius measured in metres.

        Returns
        -------
        bool
            ``True`` when at least one opponent is inside the radius.
        """
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
        """Identify a teammate who can relieve pressure when the forward is trapped.

        Parameters
        ----------
        player : PlayerMatchState
            Forward under pressure searching for help.
        ball : BallState
            Ball state to read recent recipients and context.
        all_players : List[PlayerMatchState]
            All player states used to evaluate candidates.
        opponents : List[PlayerMatchState]
            Defenders whose spacing informs lane safety.
        vision_attr : int
            Vision rating scaling the pass scoring weights.

        Returns
        -------
        PlayerMatchState | None
            Relief target if one exceeds the configured score threshold.
        """
        teammates = self.get_teammates(player, all_players)

        if not teammates:
            return None

        best_target = None
        best_score = 0.0
        goal_pos = self.get_goal_position(player)
        fwd_cfg = ENGINE_CONFIG.role.forward

        trace_enabled = self._player_debugger(player) is not None
        candidate_records: list[tuple[int, float, float, float]] = []

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

            if trace_enabled:
                candidate_records.append(
                    (
                        teammate.player_id,
                        total_score,
                        lane_quality,
                        space_score,
                    )
                )

        passes_threshold = best_score > fwd_cfg.relief_score_threshold

        if trace_enabled and candidate_records:
            preview = ", ".join(
                f"#{pid} s={score:.2f} lane={lane:.2f} space={space:.2f}"
                for pid, score, lane, space in sorted(candidate_records, key=lambda item: item[1], reverse=True)[:3]
            )
            best_label = f"#{best_target.player_id}" if best_target else "none"
            self._log_player_event(
                player,
                "decision",
                (
                    f"relief_candidates best={best_label} score={best_score:.2f} "
                    f"thresh={fwd_cfg.relief_score_threshold:.2f} opts=[{preview}]"
                ),
            )

        return best_target if passes_threshold else None


class CentreForwardRoleBehaviour(ForwardBaseBehaviour):
    """Central striker AI - main goal threat."""

    def __init__(self) -> None:
        """Instantiate the central striker behaviour."""
        super().__init__(role="CF", side="central")

    def _adjust_attacking_run(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState", goal_pos: "Vector2D"
    ) -> "Vector2D":
        """Keep central forwards narrow to threaten the middle channel.

        Parameters
        ----------
        player : PlayerMatchState
            Central forward executing the run.
        position : Vector2D
            Baseline run target before stylistic tweaks.
        ball : BallState
            Ball location influencing lateral drift.
        goal_pos : Vector2D
            Opponent goal position for reference.

        Returns
        -------
        Vector2D
            Adjusted run destination constrained near the centre.
        """
        from touchline.engine.physics import Vector2D

        # Stay in central channel
        fwd_cfg = ENGINE_CONFIG.role.forward
        adjusted_y = position.y * fwd_cfg.centre_adjust_factor  # Drift slightly but stay central
        adjusted_y = max(-fwd_cfg.centre_max_width, min(fwd_cfg.centre_max_width, adjusted_y))

        return Vector2D(position.x, adjusted_y)


class LeftCentreForwardRoleBehaviour(ForwardBaseBehaviour):
    """Left forward / Left winger AI."""

    def __init__(self) -> None:
        """Instantiate the left-sided forward behaviour."""
        super().__init__(role="LCF", side="left")

    def _adjust_attacking_run(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState", goal_pos: "Vector2D"
    ) -> "Vector2D":
        """Encourage diagonal runs that originate from the left touchline.

        Parameters
        ----------
        player : PlayerMatchState
            Left-sided forward.
        position : Vector2D
            Proposed run destination before adjustment.
        ball : BallState
            Ball position impacting whether to stay wide or cut inside.
        goal_pos : Vector2D
            Goal location to bias diagonal cuts.

        Returns
        -------
        Vector2D
            Updated run point tailored for a left winger archetype.
        """
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
        """Instantiate the right-sided forward behaviour."""
        super().__init__(role="RCF", side="right")

    def _adjust_attacking_run(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState", goal_pos: "Vector2D"
    ) -> "Vector2D":
        """Steer runs for right-sided forwards to balance width and cut-ins.

        Parameters
        ----------
        player : PlayerMatchState
            Right-sided forward.
        position : Vector2D
            Initial run target before stylistic tweaks.
        ball : BallState
            Ball location guiding whether to hug the touchline.
        goal_pos : Vector2D
            Goal coordinates for determining when to cut inside.

        Returns
        -------
        Vector2D
            Adjusted run destination suited for right-flank behaviour.
        """
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
