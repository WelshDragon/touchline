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
"""Role behaviours focused on defensive duties."""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from touchline.engine.config import ENGINE_CONFIG

from .base import RoleBehaviour

if TYPE_CHECKING:
    from touchline.engine.physics import BallState, Vector2D
    from touchline.engine.player_state import PlayerMatchState


class DefenderBaseBehaviour(RoleBehaviour):
    """Base defender AI with shared defensive behaviors.

    Parameters
    ----------
    role : str
        Defensive role code controlled by the behaviour instance.
    side : str
        Pitch side ordinarily occupied by the defender (``"left"``, ``"right"``, or ``"central"``).
    """

    def decide_action(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        dt: float,
    ) -> None:
        """Coordinate the defender's decision-making logic for this frame.

        Parameters
        ----------
        player : PlayerMatchState
            Controlled defender whose behaviour is being updated.
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
        tackling_attr = player_model.attributes.tackling
        speed_attr = player_model.attributes.speed
        positioning_attr = player_model.attributes.positioning
        passing_attr = player_model.attributes.passing
        vision_attr = player_model.attributes.vision

        teammates = self.get_teammates(player, all_players)
        opponents = self.get_opponents(player, all_players)

        try:
            if self._move_to_receive_pass(player, ball, speed_attr, dt):
                return

            if self._pursue_loose_ball(player, ball, all_players, speed_attr):
                return

            # If defender has the ball, look to pass
            if self.has_ball_possession(player, ball):
                self._play_out_from_back(player, ball, all_players, passing_attr, vision_attr, player.match_time)
                return

            # Try to win the ball if close
            if self._should_tackle(player, ball, opponents, tackling_attr):
                self._attempt_tackle(player, ball, tackling_attr, speed_attr, dt, player.match_time)
                return

            # Mark nearest opponent or intercept
            if self._should_intercept(player, ball, speed_attr):
                self._attempt_intercept(player, ball, speed_attr, dt)
                return

            # Mark opponent
            threat = self._find_biggest_threat(player, ball, opponents, teammates)
            if threat:
                self._mark_opponent(player, threat, ball, positioning_attr, dt)
                return

            # Default: maintain defensive shape
            self._maintain_defensive_position(player, ball, positioning_attr, dt)
        finally:
            self._current_all_players = None

    def _should_tackle(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        opponents: List["PlayerMatchState"],
        tackling_attr: int,
    ) -> bool:
        """Decide if should attempt tackle."""
        def_cfg = ENGINE_CONFIG.role.defender

        if self.distance_to_ball(player, ball) > def_cfg.tackle_ball_distance:
            return False

        # Check if opponent has ball
        for opp in opponents:
            if self.has_ball_possession(opp, ball):
                distance = player.state.position.distance_to(opp.state.position)
                # Better tacklers attempt from further
                max_tackle_distance = (
                    def_cfg.tackle_range_base
                    + (tackling_attr / 100) * def_cfg.tackle_range_attr_scale
                )
                return distance < max_tackle_distance

        return False

    def _attempt_tackle(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        tackling_attr: int,
        speed_attr: int,
        dt: float,
        current_time: float,
    ) -> None:
        """Attempt to tackle and win the ball."""
        # Move towards ball aggressively
        self.move_to_position(player, ball.position, speed_attr, dt, ball, sprint=True, intent="press")

        # If very close, can win ball
        def_cfg = ENGINE_CONFIG.role.defender

        if self.distance_to_ball(player, ball) < def_cfg.tackle_success_distance:
            # Success based on tackling attribute
            import random

            success_chance = (tackling_attr / 100) * def_cfg.tackle_success_scale

            if random.random() < success_chance:
                # Won the ball! Clear it
                own_goal = self.get_own_goal_position(player)
                clear_direction = (ball.position - own_goal).normalize()

                # Clear upfield
                if self._can_kick_ball(player, ball):
                    ball.kick(
                        clear_direction,
                        def_cfg.clear_power,
                        player.player_id,
                        current_time,
                        kicker_position=player.state.position,
                    )

    def _should_intercept(self, player: "PlayerMatchState", ball: "BallState", speed_attr: int) -> bool:
        """Decide if should attempt to intercept a pass."""
        # Ball must be moving
        def_cfg = ENGINE_CONFIG.role.defender

        if ball.velocity.magnitude() < def_cfg.intercept_ball_speed_min:
            return False

        # Calculate if can reach ball's trajectory
        distance_to_ball = self.distance_to_ball(player, ball)

        if distance_to_ball > def_cfg.intercept_distance_limit:
            return False

        # Project ball position
        speed_factor = max(speed_attr / 100, 0.01)
        time_to_reach = distance_to_ball / (speed_factor * def_cfg.intercept_speed_scale)
        ball_future_pos = ball.position + ball.velocity * time_to_reach

        future_distance = player.state.position.distance_to(ball_future_pos)

        # Can intercept if future position is closer
        return future_distance < distance_to_ball * def_cfg.intercept_improvement_factor

    def _attempt_intercept(self, player: "PlayerMatchState", ball: "BallState", speed_attr: int, dt: float) -> None:
        """Move to intercept the ball."""
        # Predict where ball will be
        distance = self.distance_to_ball(player, ball)
        def_cfg = ENGINE_CONFIG.role.defender
        player_speed = max((speed_attr / 100) * def_cfg.intercept_speed_scale, 0.1)

        time_to_reach = distance / player_speed
        intercept_pos = ball.position + ball.velocity * time_to_reach

        # Sprint to intercept position
        self.move_to_position(player, intercept_pos, speed_attr, dt, ball, sprint=True, intent="press")

    def _find_biggest_threat(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        opponents: List["PlayerMatchState"],
        teammates: List["PlayerMatchState"],
    ) -> Optional["PlayerMatchState"]:
        """Find the most dangerous opponent to mark."""
        own_goal = self.get_own_goal_position(player)
        max_threat = -1
        biggest_threat = None
        def_cfg = ENGINE_CONFIG.role.defender

        for opp in opponents:
            # Skip goalkeeper
            if opp.player_role == "GK":
                continue

            # Threat factors: proximity to ball, proximity to goal, if marked
            distance_to_ball = opp.state.position.distance_to(ball.position)
            distance_to_goal = opp.state.position.distance_to(own_goal)
            distance_to_me = player.state.position.distance_to(opp.state.position)

            # Only consider opponents within reasonable range
            if distance_to_me > def_cfg.threat_marking_range:
                continue

            # Check if already marked by teammate (stricter check)
            is_marked = any(
                t.state.position.distance_to(opp.state.position) < def_cfg.threat_marked_distance
                for t in teammates
                if t != player
            )

            # Calculate threat score
            ball_threat = max(0, 1 - distance_to_ball / def_cfg.threat_ball_distance)
            goal_threat = max(0, 1 - distance_to_goal / def_cfg.threat_goal_distance)
            marking_bonus = 0 if is_marked else def_cfg.threat_unmarked_bonus

            # Strong preference for opponents closest to this defender (prevents crowding)
            proximity_score = max(0, 1 - distance_to_me / def_cfg.threat_proximity_distance)

            threat_score = (
                ball_threat * def_cfg.threat_ball_weight
                + goal_threat * def_cfg.threat_goal_weight
                + marking_bonus * def_cfg.threat_marking_weight
                + proximity_score * def_cfg.threat_proximity_weight
            )

            if threat_score > max_threat:
                max_threat = threat_score
                biggest_threat = opp

        return biggest_threat

    def _mark_opponent(
        self,
        player: "PlayerMatchState",
        opponent: "PlayerMatchState",
        ball: "BallState",
        positioning_attr: int,
        dt: float,
    ) -> None:
        """Mark an opponent."""
        own_goal = self.get_own_goal_position(player)

        # Position between opponent and goal
        opp_to_goal = (own_goal - opponent.state.position).normalize()
        def_cfg = ENGINE_CONFIG.role.defender
        marking_distance = (
            def_cfg.marking_distance_base
            + (positioning_attr / 100) * def_cfg.marking_distance_attr_scale
        )

        marking_pos = opponent.state.position + opp_to_goal * marking_distance

        # Adjust towards ball if it's nearby
        if ball.position.distance_to(opponent.state.position) < def_cfg.marking_ball_distance:
            ball_to_opp = (opponent.state.position - ball.position).normalize()
            marking_pos = marking_pos + ball_to_opp * def_cfg.marking_ball_adjustment

        # Move to marking position
        self.move_to_position(player, marking_pos, def_cfg.marking_speed_attr, dt, ball, sprint=False, intent="mark")

    def _maintain_defensive_position(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        positioning_attr: int,
        dt: float,
    ) -> None:
        """Maintain defensive shape."""
        # Get defensive position relative to ball
        defensive_pos = self.get_defensive_position(player, ball, player.role_position)

        # Adjust based on side (fullbacks wider, center backs central)
        defensive_pos = self._adjust_for_side(player, defensive_pos, ball)

        # Move to position
        self.move_to_position(player, defensive_pos, positioning_attr, dt, ball, sprint=False, intent="shape")

    def _adjust_for_side(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Adjust position based on defender side (overridden by subclasses)."""
        return position

    def _play_out_from_back(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        passing_attr: int,
        vision_attr: int,
        current_time: float,
    ) -> None:
        """Play ball out from defensive position."""
        # Look for progressive pass
        target = self.find_best_pass_target(player, ball, all_players, vision_attr, passing_attr)

        if target:
            self.execute_pass(player, target, ball, passing_attr, current_time)
            player.state.is_with_ball = False
        else:
            # If no pass available, carry ball forward slightly
            from touchline.engine.physics import Vector2D

            goal_pos = self.get_goal_position(player)
            direction = (goal_pos - player.state.position).normalize()

            # Dribble forward slowly
            dribble_speed = ENGINE_CONFIG.role.defender.dribble_speed
            player.state.velocity = direction * dribble_speed

            # Keep ball with player
            ball.position = player.state.position
            ball.velocity = Vector2D(0, 0)


class RightDefenderRoleBehaviour(DefenderBaseBehaviour):
    """Right back / Right defender AI."""

    def __init__(self) -> None:
        """Instantiate the right-sided fullback behaviour."""
        super().__init__(role="RD", side="right")

    def _adjust_for_side(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Stay wider on the right flank."""
        from touchline.engine.physics import Vector2D

        # Maintain width on right side
        min_width = ENGINE_CONFIG.role.defender.fullback_min_width
        adjusted_y = max(position.y, -min_width)  # Stay at least configured distance right of center
        return Vector2D(position.x, adjusted_y)


class CentralDefenderRoleBehaviour(DefenderBaseBehaviour):
    """Center back AI - stays central and reads the game."""

    def __init__(self) -> None:
        """Instantiate the central defender behaviour."""
        super().__init__(role="CD", side="central")

    def _adjust_for_side(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Stay central with slight adjustment towards ball."""
        from touchline.engine.physics import Vector2D

        # Use the player's role_position to maintain individual spacing
        # This prevents multiple CBs from converging to the same spot
        base_y_offset = player.role_position.y

        # Stay relatively central but maintain formation width
        # Shift slightly towards ball but preserve individual positioning
        def_cfg = ENGINE_CONFIG.role.defender
        shift_y = (ball.position.y - position.y) * def_cfg.centreback_shift_factor
        adjusted_y = base_y_offset + shift_y

        # Constrain to central area
        adjusted_y = max(-def_cfg.centreback_max_width, min(def_cfg.centreback_max_width, adjusted_y))
        return Vector2D(position.x, adjusted_y)


class LeftDefenderRoleBehaviour(DefenderBaseBehaviour):
    """Left back / Left defender AI."""

    def __init__(self) -> None:
        """Instantiate the left-sided fullback behaviour."""
        super().__init__(role="LD", side="left")

    def _adjust_for_side(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Stay wider on the left flank."""
        from touchline.engine.physics import Vector2D

        # Maintain width on left side
        min_width = ENGINE_CONFIG.role.defender.fullback_min_width
        adjusted_y = min(position.y, min_width)  # Stay at least configured distance left of center
        return Vector2D(position.x, adjusted_y)
