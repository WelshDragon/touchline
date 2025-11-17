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
"""Shared role behaviour scaffolding for all positional AI scripts."""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, List, Optional

from touchline.engine.config import ENGINE_CONFIG

if TYPE_CHECKING:
    from touchline.engine.match_engine import MatchState
    from touchline.engine.physics import BallState, Vector2D
    from touchline.engine.player_state import PlayerMatchState
    from touchline.utils.debug import MatchDebugger


class RoleBehaviour:
    """Base AI behaviour framework for all player roles.

    Parameters
    ----------
    role : str
        Positional role code controlled by this behaviour instance.
    side : str
        Field side the role normally occupies (for example ``"left"`` or ``"central"``).
    """

    def __init__(self, role: str, side: str = "central") -> None:
        """Store metadata describing the role being controlled.

        Parameters
        ----------
        role : str
            Positional role code controlled by this behaviour instance.
        side : str
            Field side the role normally occupies.
        """
        self.role = role
        self.side = side
        self._current_all_players: Optional[List["PlayerMatchState"]] = None
        self._match_state: Optional["MatchState"] = None

    def _player_debugger(self, player: "PlayerMatchState") -> Optional["MatchDebugger"]:
        """Return the debugger attached to ``player`` when available.

        Parameters
        ----------
        player : PlayerMatchState
            Player whose debugger reference is being requested.

        Returns
        -------
        Optional[MatchDebugger]
            Debugger bound to ``player`` or ``None`` when absent.
        """
        return getattr(player, "debugger", None)

    def _player_label(self, player: "PlayerMatchState") -> str:
        """Return a compact label used in debug output for the player.

        Parameters
        ----------
        player : PlayerMatchState
            Player whose identifying label should be constructed.

        Returns
        -------
        str
            Human-readable identifier combining id, team, and role.
        """
        team_name = getattr(player.team, "name", "?")
        return f"#{player.player_id} {team_name} {player.player_role}"

    def _log_player_event(self, player: "PlayerMatchState", event_type: str, details: str) -> None:
        """Emit a structured debug line for the provided player.

        Parameters
        ----------
        player : PlayerMatchState
            Player whose action should be recorded in the debug log.
        event_type : str
            Short category label (for example ``"pass"`` or ``"decision"``).
        details : str
            Free-form description that supplies event context.
        """
        debugger = self._player_debugger(player)
        if not debugger:
            return
        prefix = self._player_label(player)
        debugger.log_match_event(player.match_time, event_type, f"{prefix} {details}")

    def _log_decision(self, player: "PlayerMatchState", action: str, **context: object) -> None:
        """Log a role decision along with optional context key-value pairs.

        Parameters
        ----------
        player : PlayerMatchState
            Player making the decision being documented.
        action : str
            Verb summarizing the high-level action, such as ``"dribble"``.
        **context : object
            Keyword arguments containing structured telemetry to append.
        """
        if not context:
            detail = action
        else:
            kv = " ".join(f"{key}={value}" for key, value in context.items())
            detail = f"{action} {kv}"
        self._log_player_event(player, "decision", detail)

    def decide_action(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        dt: float,
    ) -> None:
        """Determine the action to take for the current simulation frame.

        Parameters
        ----------
        player : PlayerMatchState
            The controlled player whose behaviour is being evaluated.
        ball : BallState
            Current ball state for the frame.
        all_players : List[PlayerMatchState]
            Snapshot of all players participating in the match.
        dt : float
            Simulation timestep in seconds since the previous update.
        """
        pass

    # ==================== HELPER METHODS ====================

    def get_teammates(
        self, player: "PlayerMatchState", all_players: List["PlayerMatchState"]
    ) -> List["PlayerMatchState"]:
        """Get all teammates excluding the player.

        Parameters
        ----------
        player : PlayerMatchState
            Player whose teammates should be identified.
        all_players : List[PlayerMatchState]
            Full list of players currently on the pitch.

        Returns
        -------
        List[PlayerMatchState]
            Teammates belonging to the same side as ``player``.
        """
        return [p for p in all_players if p.team == player.team and p.player_id != player.player_id]

    def get_opponents(
        self, player: "PlayerMatchState", all_players: List["PlayerMatchState"]
    ) -> List["PlayerMatchState"]:
        """Get all opponents.

        Parameters
        ----------
        player : PlayerMatchState
            Player used as the reference for team membership.
        all_players : List[PlayerMatchState]
            Full list of players currently on the pitch.

        Returns
        -------
        List[PlayerMatchState]
            Opponents facing the player's team.
        """
        return [p for p in all_players if p.team != player.team]

    def _player_by_id(self, player_id: Optional[int]) -> Optional["PlayerMatchState"]:
        """Lookup helper scoped to the cached player list for the frame.

        Parameters
        ----------
        player_id : Optional[int]
            Identifier belonging to the player of interest.

        Returns
        -------
        Optional[PlayerMatchState]
            Matching player from ``self._current_all_players`` or ``None`` if missing.
        """
        if player_id is None or not self._current_all_players:
            return None

        return next((p for p in self._current_all_players if p.player_id == player_id), None)

    def distance_to_ball(self, player: "PlayerMatchState", ball: "BallState") -> float:
        """Calculate distance from player to ball.

        Parameters
        ----------
        player : PlayerMatchState
            Player whose proximity to the ball is evaluated.
        ball : BallState
            Current ball state.

        Returns
        -------
        float
            Euclidean distance between ``player`` and the ball in metres.
        """
        return player.state.position.distance_to(ball.position)

    def is_closest_to_ball(
        self, player: "PlayerMatchState", ball: "BallState", all_players: List["PlayerMatchState"]
    ) -> bool:
        """Check if this player is closest to the ball on their team.

        Parameters
        ----------
        player : PlayerMatchState
            Candidate player to evaluate.
        ball : BallState
            Current ball state.
        all_players : List[PlayerMatchState]
            Full list of players currently on the pitch.

        Returns
        -------
        bool
            ``True`` when ``player`` is the closest teammate to the ball.
        """
        teammates = self.get_teammates(player, all_players) + [player]
        distances = [p.state.position.distance_to(ball.position) for p in teammates]
        return min(distances) == player.state.position.distance_to(ball.position)

    def has_ball_possession(self, player: "PlayerMatchState", ball: "BallState") -> bool:
        """Check if player has possession of the ball.

        Parameters
        ----------
        player : PlayerMatchState
            Player whose possession status should be queried.
        ball : BallState
            Current ball state.

        Returns
        -------
        bool
            ``True`` when the player has control of the ball.
        """
        # Use the is_with_ball flag set by the match engine
        return player.state.is_with_ball

    def _shield_ball(self, player: "PlayerMatchState", ball: "BallState", reason: Optional[str] = None) -> None:
        """Stabilize the player's movement and keep the ball tight while waiting.

        Parameters
        ----------
        player : PlayerMatchState
            Player who should protect possession.
        ball : BallState
            Ball instance that needs to remain within control range.
        reason : Optional[str], default=None
            Free-form explanation describing why shielding is triggered.
        """
        from touchline.engine.physics import Vector2D

        player.state.velocity = Vector2D(0, 0)
        ball.position = player.state.position
        ball.velocity = Vector2D(0, 0)
        detail_reason = reason or "protect"
        self._log_player_event(
            player,
            "shield",
            (
                f"holding ball reason={detail_reason} "
                f"tempo_hold={max(0.0, player.tempo_hold_until - player.match_time):.2f}s"
            ),
        )

    def _reset_space_move(self, player: "PlayerMatchState", *, reset_history: bool = True) -> None:
        """Clear any active lateral space-making movement for ``player``.

        Parameters
        ----------
        player : PlayerMatchState
            Player whose probing state should be reset.
        reset_history : bool, default=True
            When ``True`` also clears any accumulated probe loop counters.
        """
        player.space_move_until = 0.0
        player.space_move_heading = None
        if reset_history:
            player.space_probe_loops = 0

    def _forward_lane_blocked(
        self,
        player: "PlayerMatchState",
        opponents: List["PlayerMatchState"],
        *,
        max_distance: float,
        half_width: float,
        min_blockers: int = 1,
    ) -> bool:
        """Determine if opponents are clogging the forward lane toward goal.

        Parameters
        ----------
        player : PlayerMatchState
            Ball carrier evaluating space ahead.
        opponents : List[PlayerMatchState]
            Opposing players used to detect obstruction.
        max_distance : float
            Maximum forward distance to inspect for blockers.
        half_width : float
            Half-width of the corridor centred on the player's forward path.
        min_blockers : int, default=1
            Minimum number of opponents required before considering the lane blocked.

        Returns
        -------
        bool
            ``True`` when at least ``min_blockers`` opponents occupy the lane.
        """
        if not opponents or max_distance <= 0 or half_width <= 0:
            return False

        from touchline.engine.physics import Vector2D

        goal_pos = self.get_goal_position(player)
        direction = goal_pos - player.state.position
        if direction.magnitude() <= 1e-5:
            return False

        direction = direction.normalize()
        lateral_axis = Vector2D(-direction.y, direction.x)
        blockers = 0

        for opponent in opponents:
            offset = opponent.state.position - player.state.position
            forward = offset.x * direction.x + offset.y * direction.y
            if forward <= 0 or forward > max_distance:
                continue

            lateral = abs(offset.x * lateral_axis.x + offset.y * lateral_axis.y)
            if lateral > half_width:
                continue

            blockers += 1
            if blockers >= min_blockers:
                return True

        return False

    def _can_kick_ball(self, player: "PlayerMatchState", ball: "BallState") -> bool:
        """Only allow ball strikes when the player is within control range.

        Parameters
        ----------
        player : PlayerMatchState
            Player attempting to interact with the ball.
        ball : BallState
            Ball instance whose proximity is evaluated.

        Returns
        -------
        bool
            ``True`` when the ball sits within the configured control distance.
        """
        control_limit = ENGINE_CONFIG.possession.max_control_distance
        return player.state.position.distance_to(ball.position) <= control_limit

    def _move_closer_to_ball(self, player: "PlayerMatchState", ball: "BallState", speed_attr: int) -> bool:
        """Move player toward the ball if they're too far away to kick it.

        When a player has possession but is beyond max_control_distance from the ball,
        this method makes them move closer before attempting any actions.

        Parameters
        ----------
        player : PlayerMatchState
            Player who needs to approach the ball.
        ball : BallState
            Ball the player should move toward.
        speed_attr : int
            Speed attribute rating (0-100) influencing movement pace.

        Returns
        -------
        bool
            ``True`` if the player needed to move closer, ``False`` if already in range.
        """
        if self._can_kick_ball(player, ball):
            return False

        # Player is too far from the ball, move closer
        from touchline.engine.physics import Vector2D

        direction = (ball.position - player.state.position).normalize()
        
        # Calculate movement speed based on player attributes
        move_cfg = ENGINE_CONFIG.player_movement
        base_speed = move_cfg.base_speed * move_cfg.base_multiplier
        speed_factor = speed_attr / 100.0
        move_speed = base_speed + base_speed * move_cfg.attribute_multiplier * speed_factor
        
        # Set velocity toward the ball
        player.state.velocity = direction * move_speed
        player.current_target = ball.position
        
        distance_to_ball = player.state.position.distance_to(ball.position)
        self._log_decision(
            player,
            "move_to_ball",
            distance=f"{distance_to_ball:.2f}m",
            control_limit=f"{ENGINE_CONFIG.possession.max_control_distance:.2f}m",
        )
        return True

    def get_goal_position(self, player: "PlayerMatchState", pitch_width: Optional[float] = None) -> "Vector2D":
        """Get the opponent's goal position.

        Parameters
        ----------
        player : PlayerMatchState
            Player used to determine which goal is considered the opponent's.
        pitch_width : Optional[float]
            Optional pitch width override in metres.

        Returns
        -------
        Vector2D
            Target coordinates of the opponent goal mouth.
        """
        from touchline.engine.physics import Vector2D

        width = pitch_width if pitch_width is not None else ENGINE_CONFIG.pitch.width
        goal_x = width / 2 if player.is_home_team else -width / 2
        return Vector2D(goal_x, 0)

    def get_own_goal_position(self, player: "PlayerMatchState", pitch_width: Optional[float] = None) -> "Vector2D":
        """Get the player's own goal position.

        Parameters
        ----------
        player : PlayerMatchState
            Player used to determine the defending goal.
        pitch_width : Optional[float]
            Optional pitch width override in metres.

        Returns
        -------
        Vector2D
            Coordinates representing the player's defending goal.
        """
        from touchline.engine.physics import Vector2D

        width = pitch_width if pitch_width is not None else ENGINE_CONFIG.pitch.width
        goal_x = -width / 2 if player.is_home_team else width / 2
        return Vector2D(goal_x, 0)

    def should_shoot(self, player: "PlayerMatchState", ball: "BallState", shooting_attr: int) -> bool:
        """Decide if player should attempt a shot.

        Parameters
        ----------
        player : PlayerMatchState
            Player evaluating whether to shoot.
        ball : BallState
            Current ball state.
        shooting_attr : int
            Shooting attribute rating of the player (0-100).

        Returns
        -------
        bool
            ``True`` when the heuristics favour attempting a shot.
        """
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
        """Calculate quality of shooting angle (0-1).

        Parameters
        ----------
        player : PlayerMatchState
            Player considering a shot on goal.
        goal_pos : Vector2D
            Target goal position to compare angles against.

        Returns
        -------
        float
            Normalised angle quality score between 0 and 1.
        """
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
        """Calculate angle between two targets from a position.

        Parameters
        ----------
        pos : Vector2D
            Origin point used as the vertex.
        target1 : Vector2D
            First vector endpoint.
        target2 : Vector2D
            Second vector endpoint.

        Returns
        -------
        float
            Angle in degrees between the rays ``pos->target1`` and ``pos->target2``.
        """
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
        """Find the best teammate to pass to.

        Parameters
        ----------
        player : PlayerMatchState
            Player currently in possession or evaluating a pass.
        ball : BallState
            Current ball state used to track recent pass pairs.
        all_players : List[PlayerMatchState]
            Full list of players participating in the match.
        vision_attr : int
            Vision attribute rating (0-100) influencing pass selection.
        passing_attr : int
            Passing attribute rating (0-100) impacting pass range and accuracy.

        Returns
        -------
        Optional[PlayerMatchState]
            Chosen teammate if an advantageous pass exists, otherwise ``None``.
        """
        teammates = self.get_teammates(player, all_players)
        opponents = self.get_opponents(player, all_players)

        if not teammates:
            return None

        best_target = None
        best_score = -1

        goal_pos = self.get_goal_position(player)
        pass_cfg = ENGINE_CONFIG.role.passing

        pressure_distance = float("inf")
        if opponents:
            pressure_distance = min(
                opp.state.position.distance_to(player.state.position) for opp in opponents
            )
        under_pressure = pressure_distance <= pass_cfg.under_pressure_radius

        vision_scale = 0.55 + (vision_attr / 100) * 0.45

        trace_enabled = self._player_debugger(player) is not None
        candidate_records: list[tuple[int, float, float, float]] = []

        for teammate in teammates:
            # Skip if too far based on passing ability
            distance = player.state.position.distance_to(teammate.state.position)
            max_pass_distance = pass_cfg.max_distance_base + (passing_attr / 100) * pass_cfg.max_distance_bonus

            if distance > max_pass_distance or distance < pass_cfg.min_distance:
                continue

            # Check if pass lane is clear
            lane_quality = self.calculate_pass_lane_quality(player, teammate, opponents)

            # Prefer passes towards goal but demand meaningful gain when not pressed
            teammate_distance_to_goal = teammate.state.position.distance_to(goal_pos)
            player_distance_to_goal = player.state.position.distance_to(goal_pos)
            progress_gain = max(0.0, player_distance_to_goal - teammate_distance_to_goal)

            receiver_space = float("inf")
            if opponents:
                receiver_space = min(
                    opp.state.position.distance_to(teammate.state.position) for opp in opponents
                )
            has_release_space = receiver_space >= pass_cfg.space_release_threshold

            progress_score = progress_gain / 50.0
            progress_multiplier = 1.0

            if progress_gain <= pass_cfg.progressive_gain_min and not under_pressure:
                progress_multiplier *= 0.35

            if progress_gain > pass_cfg.progressive_gain_min:
                surplus = progress_gain - pass_cfg.progressive_gain_min
                progress_score += (surplus / 25.0) * pass_cfg.progress_bonus_weight

            if not has_release_space:
                progress_multiplier *= 0.5
            elif under_pressure:
                progress_multiplier *= 1.15

            progress_score *= progress_multiplier

            # Weight factors
            distance_score = 1 - (distance / max_pass_distance)

            total_score = (
                lane_quality * pass_cfg.lane_weight
                + distance_score * pass_cfg.distance_weight
                + progress_score * pass_cfg.progress_weight
            ) * vision_scale

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

            if trace_enabled:
                candidate_records.append(
                    (
                        teammate.player_id,
                        total_score,
                        lane_quality,
                        progress_gain,
                    )
                )

        passes_threshold = best_score > pass_cfg.score_threshold

        if trace_enabled and candidate_records:
            preview = ", ".join(
                f"#{pid} s={score:.2f} lane={lane:.2f} prog={prog:.1f}"
                for pid, score, lane, prog in sorted(candidate_records, key=lambda item: item[1], reverse=True)[:3]
            )
            best_label = f"#{best_target.player_id}" if best_target else "none"
            self._log_player_event(
                player,
                "decision",
                (
                    f"pass_candidates best={best_label} score={best_score:.2f} "
                    f"thresh={pass_cfg.score_threshold:.2f} opts=[{preview}]"
                ),
            )

        return best_target if passes_threshold else None

    def calculate_pass_lane_quality(
        self,
        passer: "PlayerMatchState",
        receiver: "PlayerMatchState",
        opponents: List["PlayerMatchState"],
    ) -> float:
        """Calculate how clear the passing lane is (0-1).

        Parameters
        ----------
        passer : PlayerMatchState
            Player attempting the pass.
        receiver : PlayerMatchState
            Intended teammate to receive the ball.
        opponents : List[PlayerMatchState]
            Opposing players whose positions may block the lane.

        Returns
        -------
        float
            Normalised lane quality score where ``1.0`` is unobstructed.
        """
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
        """Predict where the player can meet the ball along its path.

        Parameters
        ----------
        player : PlayerMatchState
            Player chasing the ball.
        ball : BallState
            Ball state used for trajectory projection.
        player_speed : float
            Maximum travel speed in metres per second for the player.
        max_time : Optional[float]
            Maximum future time horizon to consider when scanning intercepts.
        time_step : Optional[float]
            Step size between future samples.
        reaction_buffer : Optional[float]
            Additional preparation time the player needs before moving.
        fallback_fraction : Optional[float]
            Fraction of current ball travel used when estimating a fallback intercept.
        fallback_cap : Optional[float]
            Maximum fallback travel distance.

        Returns
        -------
        Vector2D
            Estimated contact point where the player can reach the ball.
        """
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
        """Guide intended recipient towards the incoming ball to secure the pass.

        Parameters
        ----------
        player : PlayerMatchState
            Intended recipient.
        ball : BallState
            Ball travelling toward the teammate.
        speed_attr : int
            Speed attribute rating (0-100) influencing reaction speed.
        dt : float
            Simulation timestep in seconds.

        Returns
        -------
        bool
            ``True`` when the helper takes control of the player's movement.
        """
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
        """Send the nearest teammate after an unattached ball.

        Parameters
        ----------
        player : PlayerMatchState
            Player evaluating whether to chase the loose ball.
        ball : BallState
            Ball state with trajectory data.
        all_players : List[PlayerMatchState]
            All nearby players used to determine the closest teammate.
        speed_attr : int
            Speed attribute rating (0-100) used for chase speed scaling.

        Returns
        -------
        bool
            ``True`` when the caller becomes the designated chaser.
        """
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
        """Execute a pass to a teammate.

        Parameters
        ----------
        player : PlayerMatchState
            Player initiating the pass.
        target : PlayerMatchState
            Intended teammate to receive the ball.
        ball : BallState
            Shared ball state manipulated by the kick.
        passing_attr : int
            Passing attribute rating (0-100) influencing power and accuracy.
        current_time : float
            Simulation timestamp when the pass occurs.
        """
        distance_to_ball = player.state.position.distance_to(ball.position)
        distance = player.state.position.distance_to(target.state.position)

        if not self._can_kick_ball(player, ball):
            self._log_player_event(
                player,
                "pass",
                (
                    f"blocked target=#{target.player_id} distance_to_ball={distance_to_ball:.2f}m "
                    f"distance={distance:.2f}m"
                ),
            )
            return

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

        self._log_player_event(
            player,
            "pass",
            (
                f"completed target=#{target.player_id} power={power:.1f} "
                f"distance={distance:.1f}m offset=({offset_x:.2f},{offset_y:.2f})"
            ),
        )

    def execute_shot(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        shooting_attr: int,
        current_time: float,
    ) -> None:
        """Execute a shot on goal.

        Parameters
        ----------
        player : PlayerMatchState
            Player attempting the shot.
        ball : BallState
            Shared ball state manipulated by the kick.
        shooting_attr : int
            Shooting attribute rating (0-100) guiding accuracy and power.
        current_time : float
            Simulation timestamp when the shot occurs.
        """
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
        """Move player towards target position with role-specific pacing.

        Parameters
        ----------
        player : PlayerMatchState
            Player whose movement should be updated.
        target : Vector2D
            Desired location the player should approach.
        speed_attr : int
            Speed attribute rating (0-100) influencing locomotion scales.
        dt : float
            Simulation timestep in seconds since the previous update.
        ball : Optional[BallState]
            Optional ball state used for possession-aware adjustments.
        sprint : bool
            When ``True``, biases behaviour toward high-intensity movement.
        intent : Optional[str]
            Behavioural intent hint such as ``"press"`` or ``"support"``.
        """
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

    def _pass_progress_fraction(
        self,
        possessor: Optional["PlayerMatchState"],
        next_recipient: Optional["PlayerMatchState"],
        ball: "BallState",
    ) -> float:
        """Estimate how far an in-flight pass has progressed toward its target.

        Parameters
        ----------
        possessor : Optional[PlayerMatchState]
            Player who initiated the pass, if known.
        next_recipient : Optional[PlayerMatchState]
            Intended recipient of the pass, if known.
        ball : BallState
            Current ball state used to measure remaining distance.

        Returns
        -------
        float
            Normalised progress between ``0`` (just released) and ``1`` (arriving).
        """
        if not possessor or not next_recipient:
            return 0.0

        if possessor.team != next_recipient.team:
            return 0.0

        total_distance = possessor.state.position.distance_to(next_recipient.state.position)
        if total_distance <= 1e-3:
            return 1.0

        remaining = ball.position.distance_to(next_recipient.state.position)
        progress = 1.0 - remaining / total_distance
        return max(0.0, min(1.0, progress))

    def _apply_possession_support(
        self,
        player: "PlayerMatchState",
        target: "Vector2D",
        ball: "BallState",
    ) -> "Vector2D":
        """Push teammates forward when their side is in possession.

        Parameters
        ----------
        player : PlayerMatchState
            Player whose support position is adjusted.
        target : Vector2D
            Original movement target.
        ball : BallState
            Ball state used to check team possession context.

        Returns
        -------
        Vector2D
            Adjusted target factoring in possession-phase support nudges.
        """
        if player.state.is_with_ball:
            return target

        possessor = self._player_by_id(ball.last_touched_by)
        next_recipient = self._player_by_id(ball.last_kick_recipient)

        team_side = "home" if player.is_home_team else "away"
        match_state = self._match_state
        team_flag = match_state.team_in_possession if match_state else None

        anchor_player = possessor if possessor and possessor.team == player.team else None
        team_controls = anchor_player is not None or team_flag == team_side

        if not team_controls:
            return target

        if (anchor_player is None or anchor_player.team != player.team) and match_state:
            fallback = self._player_by_id(match_state.last_possession_player_id)
            if fallback and fallback.team == player.team:
                anchor_player = fallback

        if anchor_player and anchor_player.player_id == player.player_id:
            return target

        phase = self._determine_possession_phase(player, ball, anchor_player, next_recipient)

        # Goal direction is positive X for home, negative for away.
        goal_dir = 1.0 if player.is_home_team else -1.0
        relative_target = target.x * goal_dir
        relative_ball = ball.position.x * goal_dir
        relative_possessor = (
            anchor_player.state.position.x * goal_dir
            if anchor_player is not None
            else relative_ball
        )

        support_cfg = ENGINE_CONFIG.role.possession_support
        recipient_influence = 0.0
        if next_recipient and next_recipient.team == player.team:
            relative_recipient = next_recipient.state.position.x * goal_dir
            progress = self._pass_progress_fraction(anchor_player, next_recipient, ball)
            recipient_influence = support_cfg.release_recipient_window * progress
        else:
            relative_recipient = relative_possessor

        anchor_relative = (
            relative_possessor * (1.0 - recipient_influence) + relative_recipient * recipient_influence
        )

        push_distance, trailing_buffer, forward_margin = self._support_profile(player, phase)
        if push_distance <= 0 and forward_margin <= 0:
            return target

        from touchline.engine.physics import Vector2D

        # Encourage players to close the space to the ball while respecting role-based buffers.
        gap_to_anchor = max(0.0, anchor_relative - relative_target)
        desired_relative = relative_target + min(
            push_distance,
            gap_to_anchor * support_cfg.gap_weight + push_distance * support_cfg.push_bias,
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

    def _support_profile(
        self,
        player: "PlayerMatchState",
        phase: str,
    ) -> tuple[float, float, float]:
        """Return ``(push_distance, trailing_buffer, forward_margin)`` for support.

        Parameters
        ----------
        player : PlayerMatchState
            Player requesting support offsets.
        phase : str
            Possession phase key such as ``"build"`` or ``"final"``.

        Returns
        -------
        tuple[float, float, float]
            The push distance, trailing buffer, and forward margin for the role/phase.
        """
        phase_profiles = ENGINE_CONFIG.role.support_phase_profiles
        role = player.player_role

        role_phase_profiles = phase_profiles.get(role)
        if role_phase_profiles and phase in role_phase_profiles:
            return role_phase_profiles[phase]

        default_phase_profiles = phase_profiles.get("default", {})
        if default_phase_profiles and phase in default_phase_profiles:
            return default_phase_profiles[phase]

        if role_phase_profiles:
            return next(iter(role_phase_profiles.values()))

        if default_phase_profiles:
            return next(iter(default_phase_profiles.values()))

        return (0.0, 0.0, 0.0)

    def _determine_possession_phase(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        possessor: Optional["PlayerMatchState"],
        next_recipient: Optional["PlayerMatchState"] = None,
    ) -> str:
        """Classify the current possession phase for support spacing logic.

        Parameters
        ----------
        player : PlayerMatchState
            Player whose team context should be evaluated.
        ball : BallState
            Ball state currently in play.
        possessor : Optional[PlayerMatchState]
            Player currently in control of the ball, if known.
        next_recipient : Optional[PlayerMatchState], default=None
            Predicted recipient that influences the anchor position.

        Returns
        -------
        str
            Phase label of ``"build"``, ``"mid"``, or ``"final"``.
        """
        support_cfg = ENGINE_CONFIG.role.possession_support
        goal_dir = 1.0 if player.is_home_team else -1.0

        anchor_x = ball.position.x
        if possessor and possessor.team == player.team:
            anchor_x = possessor.state.position.x

        if next_recipient and next_recipient.team == player.team:
            blend = support_cfg.release_recipient_window
            progress = self._pass_progress_fraction(possessor, next_recipient, ball)
            scaled_blend = blend * progress
            anchor_x = anchor_x * (1.0 - scaled_blend) + next_recipient.state.position.x * scaled_blend

        relative_anchor = anchor_x * goal_dir

        if relative_anchor <= support_cfg.build_up_limit:
            return "build"
        if relative_anchor <= support_cfg.midfield_limit:
            return "mid"
        return "final"

    def _apply_lane_spacing(
        self,
        player: "PlayerMatchState",
        target: "Vector2D",
        lane_weight: Optional[float] = None,
        min_spacing: Optional[float] = None,
    ) -> "Vector2D":
        """Blend target with base lane and push away from nearby teammates.

        Parameters
        ----------
        player : PlayerMatchState
            Player whose destination is being adjusted.
        target : Vector2D
            Desired destination before spacing corrections.
        lane_weight : Optional[float]
            Weighting applied when blending between the lane and ``target``.
        min_spacing : Optional[float]
            Minimum distance to maintain from teammates.

        Returns
        -------
        Vector2D
            Adjusted target respecting lane bias and separation rules.
        """
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
        """Calculate defensive position maintaining individual formation positions.

        Parameters
        ----------
        player : PlayerMatchState
            Defender whose target position is being computed.
        ball : BallState
            Current ball state guiding defensive adjustments.
        base_position : Vector2D
            Formation anchor point assigned to the player.

        Returns
        -------
        Vector2D
            Adjusted defensive position respecting formation shape.
        """
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
        """Decide if player should press the opponent with the ball.

        Parameters
        ----------
        player : PlayerMatchState
            Player evaluating whether to initiate a press.
        ball : BallState
            Current ball state.
        all_players : List[PlayerMatchState]
            Full list of players to inspect for possession.
        stamina_threshold : Optional[float]
            Minimum stamina required to attempt a press; defaults to configuration.
        distance_threshold : Optional[float]
            Maximum distance to the ball to trigger a press; defaults to configuration.

        Returns
        -------
        bool
            ``True`` when the player should press the opponent in possession.
        """
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
        """Find space away from other players.

        Parameters
        ----------
        player : PlayerMatchState
            Player seeking open space.
        all_players : List[PlayerMatchState]
            Complete list of players used to evaluate crowding.
        preferred_direction : Vector2D
            Initial direction to bias the search towards.
        search_radius : Optional[float]
            Radius in metres used when sampling candidate positions.

        Returns
        -------
        Vector2D
            Candidate position representing a low-crowding area.
        """
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
