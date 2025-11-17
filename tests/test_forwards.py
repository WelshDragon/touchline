"""Regression tests for forward patience and recycling behaviour."""
from types import SimpleNamespace
from typing import Optional, Protocol

from touchline.engine.config import ENGINE_CONFIG, ForwardConfig
from touchline.engine.physics import BallState, PlayerState, Vector2D
from touchline.engine.roles.forwards import ForwardBaseBehaviour


class ForwardPlayerLike(Protocol):
    """Protocol describing the player shape required for forward tests."""

    player_id: int
    team: object
    state: PlayerState
    match_time: float
    tempo_hold_until: float
    tempo_hold_cooldown_until: float
    space_move_until: float
    space_move_heading: Optional[Vector2D]
    space_probe_loops: int
    current_target: Optional[Vector2D]
    player_role: str
    is_home_team: bool
    role_position: Vector2D
    debugger: object | None
    off_ball_state: str


class StubForwardBehaviour(ForwardBaseBehaviour):
    """Test double that exposes pass execution state."""

    def __init__(self) -> None:
        super().__init__(role="CF", side="central")
        self.pass_target: Optional[ForwardPlayerLike] = None
        self.executed_targets: list[int] = []
        self.dribble_called = False

    def find_best_pass_target(  # type: ignore[override]
        self,
        player: ForwardPlayerLike,
        ball: BallState,
        all_players: list[ForwardPlayerLike],
        vision_attr: int,
        passing_attr: int,
    ) -> Optional[ForwardPlayerLike]:
        """Return the preselected teammate so tests can control outcomes."""
        return self.pass_target

    def execute_pass(  # type: ignore[override]
        self,
        player: ForwardPlayerLike,
        target: ForwardPlayerLike,
        ball: BallState,
        passing_attr: int,
        current_time: float,
    ) -> None:
        """Record each executed pass for later assertions."""
        self.executed_targets.append(target.player_id)

    def _forward_lane_blocked(  # type: ignore[override]
        self,
        player: ForwardPlayerLike,
        opponents: list[ForwardPlayerLike],
        *,
        max_distance: float,
        half_width: float,
        min_blockers: int = 1,
    ) -> bool:
        return True

    def _move_to_support_space(  # type: ignore[override]
        self,
        player: ForwardPlayerLike,
        ball: BallState,
        opponents: list[ForwardPlayerLike],
        fwd_cfg: ForwardConfig,
    ) -> bool:
        return False

    def _begin_hold_window(  # type: ignore[override]
        self,
        player: ForwardPlayerLike,
        ball: BallState,
        fwd_cfg: ForwardConfig,
    ) -> bool:
        return False

    def _attempt_backpass(  # type: ignore[override]
        self,
        player: ForwardPlayerLike,
        ball: BallState,
        all_players: list[ForwardPlayerLike],
        opponents: list[ForwardPlayerLike],
        passing_attr: int,
        current_time: float,
    ) -> bool:
        return False

    def _dribble_at_goal(  # type: ignore[override]
        self,
        player: ForwardPlayerLike,
        ball: BallState,
        dribbling_attr: int,
        passing_attr: int,
        vision_attr: int,
        all_players: list[ForwardPlayerLike],
        opponents: list[ForwardPlayerLike],
        current_time: float,
    ) -> None:
        self.dribble_called = True


def make_forward(
    player_id: int,
    team: object,
    position_x: float,
    position_y: float,
    *,
    with_ball: bool = False,
    role: str = "CF",
) -> ForwardPlayerLike:
    """Build a lightweight player namespace satisfying the required protocol."""
    state = PlayerState(
        position=Vector2D(position_x, position_y),
        velocity=Vector2D(0.0, 0.0),
        stamina=95.0,
        is_with_ball=with_ball,
    )
    return SimpleNamespace(
        player_id=player_id,
        team=team,
        state=state,
        match_time=18.3,
        tempo_hold_until=0.0,
        tempo_hold_cooldown_until=0.0,
        space_move_until=0.0,
        space_move_heading=None,
        space_probe_loops=0,
        current_target=None,
        player_role=role,
        is_home_team=True,
        role_position=Vector2D(position_x, position_y),
        debugger=None,
        off_ball_state="idle",
    )


def test_forward_recycles_when_hold_window_nearly_elapsed() -> None:
    """Ensure forwards release the ball once the patience window expires with a safe pass."""
    behaviour = StubForwardBehaviour()
    home_team = SimpleNamespace(name="Manchester United")
    away_team = SimpleNamespace(name="Liverpool FC")

    carrier = make_forward(8, home_team, 3.0, 8.4, with_ball=True)
    teammate = make_forward(3, home_team, 8.0, 7.8)
    opponent = make_forward(102, away_team, 25.0, 0.0)
    opponent.team = away_team

    all_players = [carrier, teammate, opponent]
    behaviour.pass_target = teammate

    ball = BallState(position=Vector2D(3.0, 8.4), velocity=Vector2D(0.0, 0.0))

    fwd_cfg = ENGINE_CONFIG.role.forward
    carrier.tempo_hold_until = carrier.match_time + max(0.05, fwd_cfg.hold_force_release_time * 0.5)

    behaviour._attack_with_ball(
        carrier,
        ball,
        all_players,
        shooting_attr=50,
        dribbling_attr=55,
        passing_attr=70,
        vision_attr=65,
        current_time=carrier.match_time,
    )

    assert behaviour.executed_targets == [teammate.player_id]
    assert carrier.tempo_hold_until == 0.0
    assert behaviour.dribble_called is False
