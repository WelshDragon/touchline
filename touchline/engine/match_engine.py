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

    def __post_init__(self) -> None:
        self._initialize_player_positions()
        # Add initial ball movement
        initial_vx, initial_vy = ENGINE_CONFIG.simulation.initial_ball_velocity
        self.ball.velocity = Vector2D(initial_vx, initial_vy)  # Start with some motion

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
        # Update ball physics
        self.state.ball.update(dt)

        # Check if ball is in bounds
        if not self.state.pitch.is_in_bounds(self.state.ball.position):
            # Check for goal
            is_goal, team = self.state.pitch.is_goal(self.state.ball.position)
            if is_goal:
                self._handle_goal(team)
            else:
                self._handle_out_of_bounds()

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

            for p in all_players:
                p.state.is_with_ball = False

            new_player.state.is_with_ball = True
            self.state.ball.last_touched_by = new_player.player_id
            self.state.ball.last_touched_time = self.state.match_time
            self.state.ball.last_kick_recipient = None

            # Log possession change
            if previous_possessor != new_player:
                self.debugger.log_match_event(
                    self.state.match_time,
                    "possession",
                    (
                        f"Player {new_player.player_id} ({new_player.team.name}, "
                        f"{new_player.player_role}) gains possession"
                    ),
                )

            # Stop ball completely when possessed - AI will handle dribbling
            self.state.ball.velocity = Vector2D(0, 0)
            self.state.ball.position = new_player.state.position

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

        if not possession_acquired and ball_speed < possession_cfg.loose_ball_speed_threshold:
            closest_player = min(all_players, key=lambda p: p.state.position.distance_to(self.state.ball.position))
            closest_distance = closest_player.state.position.distance_to(self.state.ball.position)

            possession_radius = possession_cfg.base_radius
            if ball_speed < possession_cfg.medium_speed_threshold:
                possession_radius = max(possession_radius, possession_cfg.medium_radius)
            if ball_speed < possession_cfg.slow_speed_threshold:
                possession_radius = max(possession_radius, possession_cfg.slow_radius)

            if closest_distance < possession_radius:
                assign_possession(closest_player)
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

            self.debugger.log_player_state(
                self.state.match_time,
                player_state.player_id,
                player_state.team.name,
                (player_state.state.position.x, player_state.state.position.y),
                player_state.state.is_with_ball,
                player_state.state.stamina,
                target_tuple,
                player_state.player_role,
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

        # Reset positions
        self.state._initialize_player_positions()
        self.state.ball = BallState(Vector2D(0, 0), Vector2D(0, 0))

    def _handle_out_of_bounds(self) -> None:
        """Handle ball going out of bounds."""
        # Simple implementation: just bring ball back in bounds
        self.state.ball.position = self.state.pitch.constrain_to_bounds(self.state.ball.position)
        self.state.ball.velocity = Vector2D(0, 0)

    def stop_match(self) -> None:
        """Stop the match simulation."""
        self.is_running = False
        self.debugger.close()
