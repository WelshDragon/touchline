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


class MidfielderBaseBehaviour(RoleBehaviour):
    """Base midfielder AI with shared behaviors for linking play."""

    def decide_action(
        self,
        player: "PlayerMatchState",
        ball: "BallState",
        all_players: List["PlayerMatchState"],
        dt: float,
    ) -> None:
        """Main midfielder decision-making logic."""
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
            if self.should_press(player, ball, all_players, stamina_threshold=25):
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

        # Look for forward pass
        target = self.find_best_pass_target(player, ball, all_players, vision_attr, passing_attr)

        if target:
            # Check if pass is progressive
            goal_pos = self.get_goal_position(player)
            target_closer = target.state.position.distance_to(goal_pos) < player.state.position.distance_to(goal_pos)

            if target_closer or vision_attr > 70:  # High vision players can see all passes
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

        # Check for nearby pressure
        under_pressure = self._is_under_pressure(player, opponents)

        if under_pressure and dribbling_attr < 60:
            relief_target = self._find_relief_pass(player, ball, all_players, opponents, vision_attr)

            if relief_target:
                self.execute_pass(player, relief_target, ball, passing_attr, current_time)
            else:
                # Shield the ball but add small backpedal to avoid freezing in place
                retreat_dir = (player.state.position - goal_pos).normalize()
                player.state.velocity = retreat_dir * 2.0
                ball.position = player.state.position
                ball.velocity = Vector2D(0, 0)
        else:
            # Dribble towards goal or find space
            direction = (goal_pos - player.state.position).normalize()

            # Calculate speed based on dribbling ability (slower than running without ball)
            dribble_speed = 3 + (dribbling_attr / 100) * 2  # 3-5 m/s

            # Update player velocity to dribble forward
            player.state.velocity = direction * dribble_speed

            # Keep ball at player's feet (stick to player position)
            ball.position = player.state.position
            ball.velocity = Vector2D(0, 0)

    def _is_under_pressure(
        self, player: "PlayerMatchState", opponents: List["PlayerMatchState"], radius: float = 4.0
    ) -> bool:
        """Detect if any opponent is within pressing distance."""
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

        for teammate in teammates:
            distance = player.state.position.distance_to(teammate.state.position)

            if distance < 3 or distance > 28:
                continue

            lane_quality = self.calculate_pass_lane_quality(player, teammate, opponents)

            # Prefer teammates with space around them
            nearest_opponent = min(
                (opp.state.position.distance_to(teammate.state.position) for opp in opponents),
                default=10.0,
            )

            space_score = min(nearest_opponent / 6.0, 1.0)

            # Allow backwards passes, but give a small bonus if the pass keeps momentum
            progress = own_goal.distance_to(teammate.state.position) < own_goal.distance_to(player.state.position)
            momentum_score = 0.2 if progress else 0.0

            distance_score = 1 - (distance / 28)
            vision_factor = 0.7 + (vision_attr / 100) * 0.3

            total_score = (
                (lane_quality * 0.4 + space_score * 0.3 + distance_score * 0.1 + momentum_score)
                * vision_factor
            )

            if total_score > best_score:
                best_score = total_score
                best_target = teammate

        return best_target if best_score > 0.25 else None

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
            self.move_to_position(player, target_opp.state.position, speed_attr, dt, ball, sprint=True)

            # Attempt tackle if close
            if player.state.position.distance_to(target_opp.state.position) < 1.5:
                import random

                if random.random() < tackling_attr / 100 * 0.5:
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

        # Find space ahead of the ball
        if ball.position.distance_to(goal_pos) < player.state.position.distance_to(goal_pos):
            # Ball is ahead, support from behind
            support_pos = ball.position - (goal_pos - ball.position).normalize() * 12
        else:
            # Make forward run
            support_pos = ball.position + (goal_pos - ball.position).normalize() * 10

        # Adjust to side based on midfielder type
        support_pos = self._adjust_support_position(player, support_pos, ball)

        # Move to support position
        self.move_to_position(player, support_pos, speed_attr, dt, ball, sprint=False)

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
        adjustment = (self.get_goal_position(player) - own_goal).normalize() * 5

        defensive_pos = defensive_pos + adjustment

        # Move to defensive position
        self.move_to_position(player, defensive_pos, tackling_attr, dt, ball, sprint=False)

    def _adjust_support_position(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Adjust support position based on side (overridden by subclasses)."""
        return position


class RightMidfielderRoleBehaviour(MidfielderBaseBehaviour):
    """Right midfielder / Right winger AI."""

    def __init__(self) -> None:
        super().__init__(role="RM", side="right")

    def _adjust_support_position(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Stay wide on the right flank."""
        from touchline.engine.physics import Vector2D

        # Maintain width on right touchline
        adjusted_y = min(position.y, -12)  # Stay wide right
        return Vector2D(position.x, adjusted_y)


class CentralMidfielderRoleBehaviour(MidfielderBaseBehaviour):
    """Central midfielder AI - box-to-box play."""

    def __init__(self) -> None:
        super().__init__(role="CM", side="central")

    def _adjust_support_position(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Stay central but shift slightly towards ball."""
        from touchline.engine.physics import Vector2D

        # Central but can drift
        shift_y = (ball.position.y - position.y) * 0.3
        adjusted_y = position.y + shift_y

        # Stay within central corridor
        adjusted_y = max(-15, min(15, adjusted_y))
        return Vector2D(position.x, adjusted_y)


class LeftMidfielderRoleBehaviour(MidfielderBaseBehaviour):
    """Left midfielder / Left winger AI."""

    def __init__(self) -> None:
        super().__init__(role="LM", side="left")

    def _adjust_support_position(
        self, player: "PlayerMatchState", position: "Vector2D", ball: "BallState"
    ) -> "Vector2D":
        """Stay wide on the left flank."""
        from touchline.engine.physics import Vector2D

        # Maintain width on left touchline
        adjusted_y = max(position.y, 12)  # Stay wide left
        return Vector2D(position.x, adjusted_y)
