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
"""Tests for restart logic (goal kicks and throw-ins)."""

from __future__ import annotations

from pathlib import Path

from touchline.engine.match_engine import RealTimeMatchEngine
from touchline.engine.physics import Vector2D
from touchline.utils.roster import load_teams_from_json


def _build_engine() -> RealTimeMatchEngine:
    """Create a match engine seeded with fixture data for deterministic tests."""
    data_file = Path(__file__).resolve().parents[1] / "data" / "players.json"
    home, away = load_teams_from_json(str(data_file))
    return RealTimeMatchEngine(home, away)


def test_goal_kick_awarded_to_defending_goalkeeper() -> None:
    """Award a goal kick to the defending side's goalkeeper when the ball exits."""
    engine = _build_engine()
    pitch = engine.state.pitch
    ball = engine.state.ball

    ball.position = Vector2D(-pitch.width / 2 - 0.5, pitch.goal_width / 2 + 1.0)
    ball.velocity = Vector2D(0.0, 0.0)
    last_away = next(p.player_id for p in engine.state.player_states.values() if not p.is_home_team)
    ball.last_touched_by = last_away

    last_touch_side = engine._side_for_player(last_away)  # type: ignore[attr-defined]
    decision = engine.referee.observe_ball(
        ball,
        engine.state.match_time,
        last_touch_side=last_touch_side,
        possession_side=None,
    )
    assert decision.has_restart
    engine._apply_restart(decision)  # type: ignore[attr-defined]

    home_gk = next(p for p in engine.state.player_states.values() if p.is_home_team and p.player_role == "GK")

    assert ball.position.x > -pitch.width / 2
    assert abs(ball.position.y) <= pitch.goal_area_width / 2
    assert home_gk.state.is_with_ball
    assert ball.last_touched_by == home_gk.player_id
    assert ball.velocity.x == 0.0 and ball.velocity.y == 0.0
    assert engine.state.events[-1].event_type == "goal_kick"
    assert engine.state.events[-1].team == engine.state.home_team


def test_throw_in_awarded_to_opponents() -> None:
    """Award a throw-in to the non-touching team and ensure restart state."""
    engine = _build_engine()
    pitch = engine.state.pitch
    ball = engine.state.ball

    ball.position = Vector2D(8.0, pitch.height / 2 + 0.3)
    ball.velocity = Vector2D(0.0, 0.0)
    last_home = next(p.player_id for p in engine.state.player_states.values() if p.is_home_team)
    ball.last_touched_by = last_home

    last_touch_side = engine._side_for_player(last_home)  # type: ignore[attr-defined]
    decision = engine.referee.observe_ball(
        ball,
        engine.state.match_time,
        last_touch_side=last_touch_side,
        possession_side=None,
    )
    assert decision.has_restart
    engine._apply_restart(decision)  # type: ignore[attr-defined]

    possessor = next((p for p in engine.state.player_states.values() if p.state.is_with_ball), None)
    assert possessor is None
    assert ball.last_touched_by is not None
    assert ball.position.y < pitch.height / 2
    assert ball.position.x <= pitch.width / 2
    assert engine.state.events[-1].event_type == "throw_in"
    assert engine.state.events[-1].team == engine.state.away_team

    thrower = engine.state.player_states[ball.last_touched_by]
    assert not thrower.state.is_with_ball
    assert ball.last_kick_recipient is not None
    recipient = engine.state.player_states[ball.last_kick_recipient]
    assert not recipient.is_home_team
    assert ball.velocity.magnitude() > 0.0