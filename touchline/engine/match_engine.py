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
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from touchline.engine.config import ENGINE_CONFIG
from touchline.engine.events import MatchEvent
from touchline.engine.physics import BallState, Pitch, PlayerState, Vector2D
from touchline.engine.player_state import PlayerMatchState
from touchline.engine.referee import Referee, RefereeDecision
from touchline.models.team import Team
from touchline.utils.debug import MatchDebugger
from touchline.utils.roster import load_teams_from_json


@dataclass
class MatchState:
    home_team: Team
    away_team: Team
    pitch: Pitch = field(default_factory=lambda: Pitch())
    ball: BallState = field(default_factory=lambda: BallState(Vector2D(0, 0), Vector2D(0, 0)))
    player_states: Dict[int, PlayerMatchState] = field(default_factory=dict)
    events: List[MatchEvent] = field(default_factory=list)
    match_time: float = 0.0  # Time in seconds
    home_score: int = 0
    away_score: int = 0
    current_half: int = 1
    halftime_triggered: bool = False
    starting_kickoff_side: str = "home"
    current_kickoff_side: str = "home"

    def __post_init__(self) -> None:
        self._initialize_player_positions()
        self.current_kickoff_side = self.starting_kickoff_side

    def _initialize_player_positions(self) -> None:
        """Set up initial player positions based on formations."""

        def setup_team_positions(team: Team, is_home: bool) -> None:
            direction = -1 if is_home else 1  # Home team starts in negative half
            players = team.players[:11]
            role_counts: Dict[str, int] = defaultdict(int)

            for player in players:
                role_key = player.role
                slot_index = role_counts[role_key]
                role_counts[role_key] += 1
                base_position = self._role_slot_offset(role_key, slot_index)
                position = Vector2D(direction * base_position.x, base_position.y)

                self.player_states[player.player_id] = PlayerMatchState(
                    player_id=player.player_id,
                    team=team,
                    state=PlayerState(position, Vector2D(0, 0), 100.0),
                    role_position=position,
                    is_home_team=(team == self.home_team),
                    player_role=player.role,
                )

        setup_team_positions(self.home_team, True)
        setup_team_positions(self.away_team, False)

    def _role_slot_offset(self, role: str, index: int) -> Vector2D:
        """Return the default formation slot for a given role (home perspective)."""
        role = role.upper()
        formation = ENGINE_CONFIG.formation

        if role == "GK":
            return Vector2D(formation.goalkeeper_x, 0)

        if role in {"RD", "LD"}:
            base_offset = -formation.fullback_base_offset if role == "RD" else formation.fullback_base_offset
            stagger = -formation.fullback_stagger if role == "RD" else formation.fullback_stagger
            y = base_offset + index * stagger
            return Vector2D(formation.fullback_x, y)

        if role == "CD":
            offsets = formation.centreback_offsets
            y = offsets[index] if index < len(offsets) else 0.0
            return Vector2D(formation.centreback_x, y)

        if role in {"RM", "LM"}:
            base_offset = (
                -formation.wide_midfielder_base_offset if role == "RM" else formation.wide_midfielder_base_offset
            )
            stagger = (
                -formation.wide_midfielder_stagger if role == "RM" else formation.wide_midfielder_stagger
            )
            y = base_offset + index * stagger
            return Vector2D(formation.wide_midfielder_x, y)

        if role == "CM":
            offsets = formation.central_midfielder_offsets
            y = offsets[index] if index < len(offsets) else 0.0
            return Vector2D(formation.central_midfielder_x, y)

        if role in {"RCF", "LCF"}:
            base_offset = (
                -formation.wide_forward_base_offset if role == "RCF" else formation.wide_forward_base_offset
            )
            stagger = -formation.wide_forward_stagger if role == "RCF" else formation.wide_forward_stagger
            y = base_offset + index * stagger
            return Vector2D(formation.centre_forward_x, y)

        if role == "CF":
            offsets = formation.centre_forward_offsets
            y = offsets[index] if index < len(offsets) else 0.0
            return Vector2D(formation.centre_forward_x, y)

        # Fallback: treat as central midfielder in absence of explicit mapping
        return Vector2D(formation.central_midfielder_x, 0)


class RealTimeMatchEngine:
    def __init__(self, home_team: Team, away_team: Team, players_json: Optional[str] = None) -> None:
        # If a players JSON file is provided (or a default data/players.json
        # exists in the repo), load teams from that file to ensure deterministic
        # player attributes across runs. Otherwise fall back to the provided
        # Team objects.
        state_home = home_team
        state_away = away_team

        json_path: Optional[Path] = None
        if players_json:
            json_path = Path(players_json)
        else:
            candidate = Path.cwd() / "data" / "players.json"
            if candidate.exists():
                json_path = candidate
            else:
                # Also try relative to repository root (two levels up from this file)
                candidate2 = Path(__file__).resolve().parents[2] / "data" / "players.json"
                if candidate2.exists():
                    json_path = candidate2

        if json_path:
            try:
                h, a = load_teams_from_json(str(json_path))
                state_home, state_away = h, a
            except Exception as e:
                # Don't crash if loading fails; fall back to supplied teams.
                print(f"Warning: failed to load players JSON {json_path}: {e}")

        self.state = MatchState(state_home, state_away)
        self.simulation_speed = ENGINE_CONFIG.simulation.default_speed  # 1.0 = real-time, 2.0 = 2x speed, etc.
        self.is_running = False
        self.debugger = MatchDebugger()
        # Attach the engine debugger to the shared ball so BallState.kick can log kicks
        self.state.ball.debugger = self.debugger
        # Inject debugger reference into each PlayerMatchState so player code
        # can optionally write debug events when they modify the ball.
        for ps in self.state.player_states.values():
            ps.debugger = self.debugger
        self.referee = Referee(self.state.pitch, self.debugger)
        self._prepare_kickoff(self.state.current_kickoff_side, reset_players=False, log_reason="First half kickoff")

    def start_match(self) -> None:
        """Start the match simulation."""
        self.is_running = True
        last_update = time.time()

        while self.is_running and self.state.match_time < ENGINE_CONFIG.simulation.match_duration:
            current_time = time.time()
            dt = (current_time - last_update) * self.simulation_speed
            self._update(dt)
            last_update = current_time

            # Small sleep to prevent excessive CPU usage
            time.sleep(ENGINE_CONFIG.simulation.frame_sleep)

    def _update(self, dt: float) -> None:
        """Update match state for the given time step."""
        half_time_mark = ENGINE_CONFIG.simulation.match_duration / 2
        if not self.state.halftime_triggered and self.state.match_time >= half_time_mark:
            self._start_second_half(half_time_mark)
            return

        # Update ball physics
        self.state.ball.update(dt)

        # Let the referee adjudicate key match events (goal, out of play, etc.)
        last_touch_side = self._side_for_player(self.state.ball.last_touched_by)
        possession_side = None
        for ps in self.state.player_states.values():
            if ps.state.is_with_ball:
                possession_side = "home" if ps.is_home_team else "away"
                break

        decision = self.referee.observe_ball(
            self.state.ball,
            self.state.match_time,
            last_touch_side=last_touch_side,
            possession_side=possession_side,
        )
        if decision.is_goal and decision.team:
            self._handle_goal(decision.team)
        elif decision.has_restart:
            self._apply_restart(decision)

        # Update all players and track ball possession
        all_players = list(self.state.player_states.values())

        self.state.match_time += dt
        # Keep per-player match clock aligned with global clock so role logic
        # that depends on time (e.g. kick cooldowns) sees real match seconds.
        for player_state in all_players:
            player_state.match_time = self.state.match_time

        # Update ball possession - player closest to slow ball gets possession
        ball_speed = self.state.ball.velocity.magnitude()
        possession_cfg = ENGINE_CONFIG.possession

        def assign_possession(new_player: PlayerMatchState) -> None:
            previous_possessor = next((p for p in all_players if p.state.is_with_ball), None)
            already_possessing = previous_possessor == new_player

            for p in all_players:
                p.state.is_with_ball = False

            new_player.state.is_with_ball = True
            self.state.ball.last_touched_by = new_player.player_id
            self.state.ball.last_touched_time = self.state.match_time
            self.state.ball.last_kick_recipient = None

            # Log possession change
            if not already_possessing:
                self.debugger.log_match_event(
                    self.state.match_time,
                    "possession",
                    (
                        f"Player {new_player.player_id} ({new_player.team.name}, "
                        f"{new_player.player_role}) gains possession"
                    ),
                )

            if not already_possessing:
                # Carry the ball at the player's pace rather than freezing it on first touch.
                self.state.ball.velocity = new_player.state.velocity
                self.state.ball.position = new_player.state.position
            else:
                # When continuing possession, keep the ball nudged ahead of the dribbler so
                # tackles remain possible and we avoid the glued-to-foot effect.
                control_direction = None
                if new_player.state.velocity.magnitude() > 0:
                    control_direction = new_player.state.velocity.normalize()
                control_offset = possession_cfg.continue_control_offset
                blend = possession_cfg.continue_velocity_blend

                if control_direction:
                    desired_position = new_player.state.position + control_direction * control_offset
                    # Ease toward the desired spot to stop jittering when players zig-zag.
                    self.state.ball.position = Vector2D(
                        self.state.ball.position.x + (desired_position.x - self.state.ball.position.x) * 0.5,
                        self.state.ball.position.y + (desired_position.y - self.state.ball.position.y) * 0.5,
                    )
                    self.state.ball.velocity = new_player.state.velocity * blend
                else:
                    self.state.ball.position = new_player.state.position
                    self.state.ball.velocity = Vector2D(0, 0)

        possession_acquired = False

        target_id = self.state.ball.last_kick_recipient
        if target_id is not None:
            target_player = self.state.player_states.get(target_id)
            if target_player:
                to_target = target_player.state.position - self.state.ball.position
                distance_to_target = to_target.magnitude()

                if distance_to_target > 0:
                    base_radius = possession_cfg.target_radius_min
                    catch_radius = max(
                        base_radius,
                        min(
                            possession_cfg.target_radius_max,
                            base_radius + ball_speed * possession_cfg.target_radius_speed_factor,
                        ),
                    )

                    direction_alignment = 1.0
                    if ball_speed > 0.1:
                        to_target_norm = to_target.normalize()
                        velocity_norm = self.state.ball.velocity.normalize()
                        direction_alignment = velocity_norm.x * to_target_norm.x + velocity_norm.y * to_target_norm.y

                    if (
                        distance_to_target < catch_radius
                        and direction_alignment > possession_cfg.direction_alignment_min
                    ):
                        assign_possession(target_player)
                        possession_acquired = True

        if possession_acquired:
            # Intended recipient already caught the ball; keep possession state untouched.
            pass
        elif ball_speed < possession_cfg.loose_ball_speed_threshold:
            closest_player = min(all_players, key=lambda p: p.state.position.distance_to(self.state.ball.position))
            closest_distance = closest_player.state.position.distance_to(self.state.ball.position)

            possession_radius = possession_cfg.base_radius
            if ball_speed < possession_cfg.medium_speed_threshold:
                possession_radius = max(possession_radius, possession_cfg.medium_radius)
            if ball_speed < possession_cfg.slow_speed_threshold:
                possession_radius = max(possession_radius, possession_cfg.slow_radius)

            if closest_distance < possession_radius:
                assign_possession(closest_player)
                possession_acquired = True
            else:
                # No one close enough to possess
                for p in all_players:
                    p.state.is_with_ball = False
        else:
            # Ball is moving fast, no one has possession
            for p in all_players:
                p.state.is_with_ball = False

        # Update AI for all players
        for player_state in all_players:
            # Call role-specific AI
            player_state.role_behaviour.decide_action(player_state, self.state.ball, all_players, dt)

            # Update player position based on velocity (for dribbling, movement, etc.)
            player_state.state.position = player_state.state.position + player_state.state.velocity * dt

            # Recover stamina when not sprinting
            player_state.state.recover_stamina(dt)

        # Determine ball possession for logging
        ball_possession_team = None
        for player_state in all_players:
            if player_state.state.is_with_ball:
                ball_possession_team = player_state.team.name
                break

        # Log ball state
        self.debugger.log_ball_state(
            self.state.match_time,
            (self.state.ball.position.x, self.state.ball.position.y),
            (self.state.ball.velocity.x, self.state.ball.velocity.y),
            ball_possession_team,
        )

        # Log player states every time we log the ball state so logs are
        # synchronized and it's easy to correlate ball <-> player changes.
        for player_state in all_players:
            target_tuple = None
            if player_state.current_target:
                target_tuple = (player_state.current_target.x, player_state.current_target.y)

                velocity_vec = player_state.state.velocity
                velocity_tuple = (velocity_vec.x, velocity_vec.y)
                speed = velocity_vec.magnitude()

                self.debugger.log_player_state(
                    self.state.match_time,
                    player_state.player_id,
                    player_state.team.name,
                    (player_state.state.position.x, player_state.state.position.y),
                    player_state.state.is_with_ball,
                    player_state.state.stamina,
                    velocity=velocity_tuple,
                    speed=speed,
                    target=target_tuple,
                    player_role=player_state.player_role,
                )

    def _handle_goal(self, scoring_team: str) -> None:
        """Handle goal scored."""
        if scoring_team == "home":
            self.state.home_score += 1
            team = self.state.home_team
        else:
            self.state.away_score += 1
            team = self.state.away_team

        event = MatchEvent(self.state.match_time, "goal", team, f"GOAL! Scored by {team.name}")
        self.state.events.append(event)
        self.debugger.log_match_event(
            self.state.match_time, "goal", f"GOAL! Score: {self.state.home_score}-{self.state.away_score}"
        )

        # Restart with the conceding team taking the kickoff.
        next_kickoff_side = "away" if scoring_team == "home" else "home"
        self._prepare_kickoff(next_kickoff_side, reset_players=True, log_reason="Kickoff after goal")

    def _apply_restart(self, decision: RefereeDecision) -> None:
        """Carry out the restart the referee selected."""
        restart_type = decision.restart_type
        awarded_side = decision.awarded_side
        restart_spot = decision.restart_spot or self.state.ball.position

        if restart_type == "goal_kick" and awarded_side:
            self._restart_goal_kick(awarded_side, restart_spot)
        elif restart_type == "throw_in" and awarded_side:
            self._restart_throw_in(awarded_side, restart_spot)
        elif restart_type == "corner":
            # Corner routines not yet implemented; keep behaviour predictable.
            self.state.ball.position = self.state.pitch.constrain_to_bounds(restart_spot)
            self.state.ball.velocity = Vector2D(0, 0)
            self.debugger.log_match_event(
                self.state.match_time,
                "restart",
                "Corner kick handling not implemented; resetting ball in play",
            )
        else:
            # Unknown restart; fall back to clamping the ball.
            self.state.ball.position = self.state.pitch.constrain_to_bounds(restart_spot)
            self.state.ball.velocity = Vector2D(0, 0)

    def _start_second_half(self, half_time_mark: float) -> None:
        """Trigger the second-half kickoff sequence."""
        self.state.halftime_triggered = True
        self.state.current_half = 2
        self.state.match_time = half_time_mark
        second_half_side = "away" if self.state.starting_kickoff_side == "home" else "home"
        self._prepare_kickoff(second_half_side, reset_players=True, log_reason="Second half kickoff")

    def _prepare_kickoff(self, kicking_side: str, *, reset_players: bool, log_reason: str) -> None:
        """Center the ball and assign possession for the next kickoff."""
        if reset_players:
            self._reset_player_states()
        else:
            for ps in self.state.player_states.values():
                ps.state.is_with_ball = False
                ps.state.velocity = Vector2D(0, 0)

        self.state.current_kickoff_side = kicking_side
        self._reset_ball_state()

        team_players = self._get_team_players(kicking_side)
        kicker = self._select_kickoff_player(team_players)

        support_player = None
        if kicker:
            kickoff_position = Vector2D(0, 0)
            kicker.state.position = kickoff_position
            kicker.state.velocity = Vector2D(0, 0)
            kicker.state.is_with_ball = True
            kicker.current_target = None
            self.state.ball.position = kickoff_position
            self.state.ball.last_touched_by = kicker.player_id
            self.state.ball.last_touched_time = self.state.match_time

            support_player = self._select_support_player(team_players, kicker)

            if support_player:
                direction = 1 if support_player.is_home_team else -1
                support_position = Vector2D(direction * 1.0, 0)
                support_player.state.position = support_position
                support_player.state.velocity = Vector2D(0, 0)
                support_player.state.is_with_ball = False
                support_player.current_target = None
                self.state.ball.last_kick_recipient = support_player.player_id
            else:
                self.state.ball.last_kick_recipient = None
        else:
            self.state.ball.position = Vector2D(0, 0)
            self.state.ball.last_touched_by = None
            self.state.ball.last_touched_time = self.state.match_time
            self.state.ball.last_kick_recipient = None

        self.debugger.log_match_event(
            self.state.match_time,
            "kickoff",
            f"{log_reason} - {kicking_side} team to start",
        )

    def _reset_player_states(self) -> None:
        """Recreate player state objects for a fresh restart."""
        self.state.player_states.clear()
        self.state._initialize_player_positions()
        for ps in self.state.player_states.values():
            ps.debugger = self.debugger
            ps.match_time = self.state.match_time
            ps.state.is_with_ball = False
            ps.state.velocity = Vector2D(0, 0)

    def _reset_ball_state(self) -> None:
        """Return the ball to the center spot without residual motion."""
        self.state.ball.debugger = self.debugger
        self.state.ball.velocity = Vector2D(0, 0)
        self.state.ball.position = Vector2D(0, 0)
        self.state.ball.last_touched_by = None
        self.state.ball.last_touched_time = self.state.match_time
        self.state.ball.last_kick_recipient = None
        if hasattr(self.state.ball, "recent_pass_pairs"):
            self.state.ball.recent_pass_pairs.clear()
        if hasattr(self.state.ball, "ground"):
            self.state.ball.ground()

    def force_goal_kick(self, defending_side: str) -> None:
        """Tests can call this to immediately restart with a goal kick."""
        goal_line_x = -self.state.pitch.width / 2 if defending_side == "home" else self.state.pitch.width / 2
        mock_position = Vector2D(goal_line_x, 0.0)
        self._restart_goal_kick(defending_side, mock_position)

    def force_throw_in(self, awarding_side: str, y_hint: float = 0.0) -> None:
        """Tests can call this to immediately restart with a throw-in."""
        mock_position = Vector2D(0.0, y_hint)
        self._restart_throw_in(awarding_side, mock_position)

    def _get_team_players(self, side: str) -> List[PlayerMatchState]:
        """Return players belonging to the requested side."""
        return [
            ps
            for ps in self.state.player_states.values()
            if (ps.is_home_team and side == "home") or (not ps.is_home_team and side == "away")
        ]

    def _select_kickoff_player(self, candidates: List[PlayerMatchState]) -> Optional[PlayerMatchState]:
        """Pick the player who will take the kickoff for the given side."""
        if not candidates:
            return None

        role_priority = (
            "CF",
            "ST",
            "RCF",
            "LCF",
            "CAM",
            "AM",
            "CM",
            "RM",
            "LM",
        )

        for role in role_priority:
            for player in candidates:
                if player.player_role.upper() == role:
                    return player

        # Fall back to the player closest to the centre spot.
        return min(candidates, key=lambda p: abs(p.state.position.x) + abs(p.state.position.y))

    def _select_support_player(
        self, candidates: List[PlayerMatchState], kicker: PlayerMatchState
    ) -> Optional[PlayerMatchState]:
        """Choose a second player to receive the kickoff tap."""
        others = [p for p in candidates if p.player_id != kicker.player_id]
        if not others:
            return None

        return min(others, key=lambda p: abs(p.state.position.x) + abs(p.state.position.y))

    def _select_throw_in_recipient(
        self, candidates: List[PlayerMatchState], thrower: PlayerMatchState
    ) -> Optional[PlayerMatchState]:
        """Pick a teammate to receive the throw-in."""
        others = [p for p in candidates if p.player_id != thrower.player_id]
        if not others:
            return None

        return min(others, key=lambda p: p.state.position.distance_to(thrower.state.position))

    def _side_for_player(self, player_id: Optional[int]) -> Optional[str]:
        """Return which side ('home' or 'away') a player belongs to."""
        if player_id is None:
            return None

        player_state = self.state.player_states.get(player_id)
        if not player_state:
            return None

        return "home" if player_state.is_home_team else "away"

    def _team_for_side(self, side: str) -> Team:
        return self.state.home_team if side == "home" else self.state.away_team

    def _clear_possession(self) -> None:
        """Remove possession flags so a restart can be set up cleanly."""
        for ps in self.state.player_states.values():
            ps.state.is_with_ball = False
            ps.state.velocity = Vector2D(0, 0)
            ps.current_target = None

    def _restart_goal_kick(self, defending_side: str, out_position: Vector2D) -> None:
        """Place the ball for a goal kick and give it to the defending goalkeeper."""
        self._clear_possession()

        team_players = self._get_team_players(defending_side)
        if not team_players:
            return

        kicker = next((p for p in team_players if p.player_role == "GK"), None)
        if kicker is None:
            kicker = min(team_players, key=lambda p: p.state.position.distance_to(out_position))

        pitch = self.state.pitch
        half_width = pitch.width / 2
        goal_line_x = -half_width if defending_side == "home" else half_width
        depth = pitch.goal_area_depth
        inside_offset = max(depth - 0.5, depth * 0.5)

        if defending_side == "home":
            restart_x = goal_line_x + inside_offset
        else:
            restart_x = goal_line_x - inside_offset

        lateral_limit = max(pitch.goal_area_width / 2 - 0.5, pitch.goal_area_width / 2)
        restart_y = max(-lateral_limit, min(lateral_limit, out_position.y))

        ball_position = Vector2D(restart_x, restart_y)

        kicker.state.position = ball_position
        kicker.state.velocity = Vector2D(0, 0)
        kicker.state.is_with_ball = True
        kicker.current_target = None

        ball = self.state.ball
        ball.position = ball_position
        ball.velocity = Vector2D(0, 0)
        ball.last_touched_by = kicker.player_id
        ball.last_touched_time = self.state.match_time
        ball.last_kick_recipient = None
        ball.recent_pass_pairs.clear()
        if hasattr(ball, "ground"):
            ball.ground()

        team = self._team_for_side(defending_side)
        description = f"Goal kick awarded to {team.name}."
        self.state.events.append(MatchEvent(self.state.match_time, "goal_kick", team, description))
        self.debugger.log_match_event(self.state.match_time, "restart", description)

    def _restart_throw_in(self, awarding_side: str, out_position: Vector2D) -> None:
        """Award a throw-in and place the ball just inside the touchline."""
        self._clear_possession()

        team_players = self._get_team_players(awarding_side)
        if not team_players:
            return

        pitch = self.state.pitch
        half_width = pitch.width / 2
        half_height = pitch.height / 2

        line_y = half_height if out_position.y >= 0 else -half_height
        inset = 0.2
        restart_y = line_y - inset if line_y > 0 else line_y + inset
        restart_x = max(-half_width + 0.5, min(half_width - 0.5, out_position.x))
        ball_position = Vector2D(restart_x, restart_y)

        thrower = min(team_players, key=lambda p: p.state.position.distance_to(ball_position))
        recipient = self._select_throw_in_recipient(team_players, thrower)

        thrower.state.position = ball_position
        thrower.state.velocity = Vector2D(0, 0)
        thrower.state.is_with_ball = False
        thrower.current_target = None

        ball = self.state.ball
        ball.position = ball_position
        ball.last_touched_by = thrower.player_id
        ball.last_touched_time = self.state.match_time
        ball.last_kick_recipient = None
        ball.recent_pass_pairs.clear()

        if recipient:
            direction = recipient.state.position - ball_position
            if direction.magnitude() > 0:
                ball.velocity = direction.normalize() * 8.0
                ball.last_kick_recipient = recipient.player_id
                ball.recent_pass_pairs.append((thrower.player_id, recipient.player_id))
            else:
                ball.velocity = Vector2D(0, 0)
        else:
            ball.velocity = Vector2D(0, 0)

        if hasattr(ball, "ground"):
            ball.ground()

        team = self._team_for_side(awarding_side)
        if recipient:
            description = (
                f"Throw-in awarded to {team.name}. Thrower #{thrower.player_id} targeting #{recipient.player_id}."
            )
        else:
            description = f"Throw-in awarded to {team.name}."
        self.state.events.append(MatchEvent(self.state.match_time, "throw_in", team, description))
        self.debugger.log_match_event(self.state.match_time, "restart", description)

    def stop_match(self) -> None:
        """Stop the match simulation."""
        self.is_running = False
        self.debugger.close()
