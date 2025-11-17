"""Tests covering midfielder patience and recycling behaviours."""
from types import SimpleNamespace
from typing import Optional, Protocol

from touchline.engine.config import ENGINE_CONFIG
from touchline.engine.physics import BallState, PlayerState, Vector2D
from touchline.engine.roles.midfielders import MidfielderBaseBehaviour


class PlayerLike(Protocol):
    """Protocol capturing the minimal player attributes required by the tests."""

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


class StubMidfielderBehaviour(MidfielderBaseBehaviour):
    """Test double that records pass execution targets."""

    def __init__(self) -> None:
        super().__init__(role="CM")
        self.pass_target: Optional[PlayerLike] = None
        self.executed_targets: list[int] = []

    def find_best_pass_target(  # type: ignore[override]
        self,
        player: PlayerLike,
        ball: BallState,
        all_players: list[PlayerLike],
        vision_attr: int,
        passing_attr: int,
    ) -> Optional[PlayerLike]:
        """Return the preselected teammate so we can control pass outcomes."""
        return self.pass_target

    def execute_pass(  # type: ignore[override]
        self,
        player: PlayerLike,
        target: PlayerLike,
        ball: BallState,
        passing_attr: int,
        current_time: float,
    ) -> None:
        """Record each execution so assertions can verify the recipient."""
        self.executed_targets.append(target.player_id)


def make_player(
    player_id: int,
    team: object,
    position_x: float,
    role: str = "CM",
    *,
    with_ball: bool = False,
) -> PlayerLike:
    """Create a lightweight player stub that satisfies the PlayerLike protocol."""
    state = PlayerState(
        position=Vector2D(position_x, 0.0),
        velocity=Vector2D(0.0, 0.0),
        stamina=90.0,
        is_with_ball=with_ball,
    )
    return SimpleNamespace(
        player_id=player_id,
        team=team,
        state=state,
        match_time=12.0,
        tempo_hold_until=0.0,
        tempo_hold_cooldown_until=0.0,
        space_move_until=0.0,
        space_move_heading=None,
        space_probe_loops=0,
        current_target=None,
        player_role=role,
        is_home_team=True,
        role_position=Vector2D(position_x, 0.0),
        debugger=None,
        off_ball_state="idle",
    )


def test_midfielder_forced_release_recycles_ball() -> None:
    """Ensure forced release logic immediately plays a recycling pass."""
    behaviour = StubMidfielderBehaviour()
    home_team = SimpleNamespace(name="Home FC")
    away_team = SimpleNamespace(name="Away FC")

    player = make_player(7, home_team, -5.0, with_ball=True)
    loops_required = ENGINE_CONFIG.role.midfielder.space_move_patience_loops
    player.space_probe_loops = loops_required

    defender = make_player(4, home_team, -20.0, role="CD")
    opponent = make_player(20, away_team, -2.0, role="CF")
    opponent.team = away_team

    all_players = [player, defender, opponent]
    ball = BallState(position=Vector2D(-5.0, 0.0), velocity=Vector2D(0.0, 0.0))

    behaviour.pass_target = defender

    behaviour._play_with_ball(
        player,
        ball,
        all_players,
        passing_attr=70,
        vision_attr=60,
        shooting_attr=40,
        dribbling_attr=50,
        current_time=player.match_time,
    )

    assert behaviour.executed_targets == [defender.player_id]
