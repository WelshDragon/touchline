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
import argparse
import re
from pathlib import Path
from typing import Optional, Tuple

from touchline.engine.match_engine import RealTimeMatchEngine
from touchline.engine.physics import Vector2D
from touchline.utils.roster import load_teams_from_json

# Defaults: try the newer log the user attached
LOG_FILE = Path("debug_logs/match_debug_20251106_143758.txt")
# If KICK_LINE is None the script will auto-search the log for a kick by
# player 110 to recipient 109 and use that occurrence.
KICK_LINE: Optional[int] = 15655


def parse_player_state_line(line: str) -> Optional[tuple]:
    m = re.search(
        r"PLAYER_STATE: Time: [\d\.]+s \| Player (\d+) .* Pos: "
        r"\(([^,]+), ([^)]+)\) \| Has Ball: (True|False)",
        line,
    )
    if not m:
        return None
    pid = int(m.group(1))
    x = float(m.group(2))
    y = float(m.group(3))
    has_ball = m.group(4) == "True"
    return pid, Vector2D(x, y), has_ball


def parse_ball_state_line(line: str) -> Optional[tuple]:
    m = re.search(r"BALL_STATE: Time: [\d\.]+s \| Pos: \(([^,]+), ([^)]+)\) \| Vel: \(([^,]+), ([^)]+)\)", line)
    if not m:
        return None
    x = float(m.group(1))
    y = float(m.group(2))
    vx = float(m.group(3))
    vy = float(m.group(4))
    return Vector2D(x, y), Vector2D(vx, vy)


def parse_kick_line(line: str) -> Optional[tuple]:
    # Example:
    # MATCH_EVENT: Time: 49.0s | Event: kick | Details: Kick: player 110 power=15.0
    # recipient=109 -> vel=(5.91,-13.79)
    m = re.search(
        r"MATCH_EVENT: Time: ([\d\.]+)s .*Kick: player (\d+) power=([\d\.]+) "
        r"recipient=(\d+) -> vel=\(([^,]+),([^)]+)\)",
        line,
    )
    if not m:
        return None
    t = float(m.group(1))
    player_id = int(m.group(2))
    power = float(m.group(3))
    recipient = int(m.group(4))
    vx = float(m.group(5))
    vy = float(m.group(6))
    return t, player_id, power, recipient, Vector2D(vx, vy)


def find_states_from_log(
    log_path: Path,
    kick_line_no: int,
) -> Tuple[
    Optional[tuple],
    Optional[Vector2D],
    Optional[Vector2D],
    dict[int, tuple[Vector2D, bool]],
]:
    lines = log_path.read_text(encoding="utf-8").splitlines()
    # If a specific line number was provided, prefer that. Otherwise try to
    # locate a kick by player 110 to recipient 109 in the file and use that
    # occurrence.
    kick_info = None
    idx = 0
    if kick_line_no is not None and 0 <= kick_line_no - 1 < len(lines):
        idx = kick_line_no - 1
        kick_info = parse_kick_line(lines[idx])

    if not kick_info:
        # Search entire file for an explicit kick from 110 to 109, prefer the
        # first match from the given start index forward, otherwise last match.
        match_indices = []
        for i, line in enumerate(lines):
            if "Event: kick" in line and "player 110" in line and "recipient=109" in line:
                match_indices.append(i)
        if match_indices:
            # prefer the first match (chronological)
            idx = match_indices[0]
            kick_info = parse_kick_line(lines[idx])
        else:
            # fallback: find any kick event near the center of file
            for i, line in enumerate(lines):
                if "Event: kick" in line:
                    kick_info = parse_kick_line(line)
                    if kick_info:
                        idx = i
                        break

    # Get kick info from the target line if possible, else search nearby
    kick_info = None
    if idx < len(lines):
        kick_info = parse_kick_line(lines[idx])

    if not kick_info:
        # search +/- 50 lines
        for i in range(max(0, idx - 50), min(len(lines), idx + 50)):
            if "Event: kick" in lines[i]:
                kick_info = parse_kick_line(lines[i])
                if kick_info:
                    idx = i
                    break

    # Find the nearest BALL_STATE and PLAYER_STATE entries before the kick line
    ball_pos = None
    ball_vel = None
    player_positions: dict[int, tuple[Vector2D, bool]] = {}

    # Search backwards from idx for relevant states
    for i in range(idx, max(0, idx - 200), -1):
        line = lines[i]
        if ball_pos is None and "BALL_STATE" in line:
            bs = parse_ball_state_line(line)
            if bs:
                ball_pos, ball_vel = bs
        # Parse all player states
        if "PLAYER_STATE" in line:
            ps = parse_player_state_line(line)
            if ps:
                pid, pos, has_ball = ps
                if pid not in player_positions:
                    player_positions[pid] = (pos, has_ball)
        # Stop once we have ball and all 22 players (11 per team)
        if ball_pos and len(player_positions) >= 22:
            break

    return kick_info, ball_pos, ball_vel, player_positions


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproducer for a specific pass/kick from debug log")
    parser.add_argument("--log", type=str, default=str(LOG_FILE), help="Path to debug log file")
    parser.add_argument("--line", type=int, default=KICK_LINE, help="1-based line number where kick occurs (optional)")
    args = parser.parse_args()

    # Load teams from JSON roster
    home, away = load_teams_from_json("data/players.json")

    engine = RealTimeMatchEngine(home, away)
    state = engine.state

    # Parse log to extract pre-kick positions
    kick_info, ball_pos, ball_vel, player_positions = find_states_from_log(Path(args.log), args.line)

    if kick_info:
        kick_time, kicker_id, power, recipient_id, logged_vel = kick_info
        print(f"Found kick at t={kick_time}, kicker={kicker_id}, recipient={recipient_id}, power={power}")
    else:
        print("Kick not found in log; falling back to defaults")
        kick_time = 49.0
        kicker_id = 110
        recipient_id = 109
        power = 15.0

    # Apply parsed positions (fallback to conservative defaults if parsing failed)
    if ball_pos:
        state.ball.position = ball_pos
    else:
        state.ball.position = Vector2D(-0.07, 3.61)

    if ball_vel:
        state.ball.velocity = ball_vel
    else:
        state.ball.velocity = Vector2D(-1.18, -0.09)

    # Apply all player positions from the log
    print(f"Applying {len(player_positions)} player states from log...")
    for pid, (pos, has_ball) in player_positions.items():
        if pid in state.player_states:
            state.player_states[pid].state.position = pos
            state.player_states[pid].state.is_with_ball = has_ball

    # Ensure player states exist
    if kicker_id not in state.player_states or recipient_id not in state.player_states:
        raise RuntimeError(f"Expected player IDs {kicker_id} and {recipient_id} in match state")

    kicker = state.player_states[kicker_id]
    recipient = state.player_states[recipient_id]

    # Mark ball owner on kicker just before kick
    kicker.state.is_with_ball = True
    state.ball.last_touched_by = kicker.player_id
    # Ensure last_touched_time is sufficiently in the past to allow the kick
    state.ball.last_touched_time = kick_time - 1.0

    # Sync match time to the kick time so AI logic sees timing similar to the log
    state.match_time = kick_time

    # Perform the kick using the engine's ball.kick API at the same kick_time
    direction = (recipient.state.position - state.ball.position).normalize()
    engine_kick_time = kick_time
    state.ball.kick(direction, power, kicker.player_id, engine_kick_time, recipient_id=recipient.player_id)

    # The engine's player AI normally clears the kicker's possession flag
    # when they perform a kick. Because this reproducer calls BallState.kick
    # directly, we must also clear the kicker's `is_with_ball` flag so the
    # player does not continue to 'dribble' the ball and overwrite ball
    # position/velocity in the next update.
    kicker.state.is_with_ball = False

    print(f"Kicked ball: vel=({state.ball.velocity.x:.2f}, {state.ball.velocity.y:.2f}) at t={engine_kick_time}")
    print(
        f"Initial: Ball@({state.ball.position.x:.1f},{state.ball.position.y:.1f}) Kicker {kicker_id}@({kicker.state.position.x:.1f},{kicker.state.position.y:.1f}) Recipient {recipient_id}@({recipient.state.position.x:.1f},{recipient.state.position.y:.1f})"
    )

    # Step the engine in small increments until pickup or timeout
    picked_up = False
    closest_distance = float("inf")
    closest_time = 0.0
    for step_num in range(5000):
        engine._update(0.01)  # 10ms steps

        # Track closest approach
        dist = recipient.state.position.distance_to(state.ball.position)
        if dist < closest_distance:
            closest_distance = dist
            closest_time = state.match_time

        # Log every 100ms for diagnostic
        if step_num % 10 == 0:
            # Check recipient flag
            is_recipient = state.ball.last_kick_recipient == recipient.player_id
            print(
                f"t={state.match_time:.1f}s: Ball@({state.ball.position.x:.1f},{state.ball.position.y:.1f}) "
                f"Recipient {recipient_id}@({recipient.state.position.x:.1f},{recipient.state.position.y:.1f}) dist={dist:.2f}m "
                f"ballVel={state.ball.velocity.magnitude():.1f} recipient_flag={is_recipient} "
                f"last_kick_recipient={state.ball.last_kick_recipient}"
            )

        if state.player_states[recipient_id].state.is_with_ball:
            picked_up = True
            print(f"\n✓ Recipient {recipient_id} picked up ball at match_time={state.match_time:.3f}")
            break
        if state.ball.velocity.magnitude() < 0.01:
            print(
                f"\n✗ Ball stopped (or out-of-bounds) at match_time={state.match_time:.3f}, "
                f"pos=({state.ball.position.x:.1f},{state.ball.position.y:.1f})"
            )
            break

    if not picked_up:
        print(f"\n✗ Recipient did not pick up the ball.")
        print(f"   Closest approach: {closest_distance:.2f}m at t={closest_time:.1f}s")

    # Close the debugger to flush the debug log
    engine.stop_match()
    print("Reproducer finished. Check debug_logs for the new session file.")


if __name__ == "__main__":
    main()
