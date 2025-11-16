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
"""Entry point for manual match simulations and the optional visualiser."""
import threading
import time
from pathlib import Path

from touchline.engine.match_engine import RealTimeMatchEngine
from touchline.utils.generator import generate_team  # Fallback if no roster file
from touchline.utils.roster import load_teams_from_json  # For loading saved rosters


def print_match_status(engine: RealTimeMatchEngine) -> None:
    """Print ongoing match status in a separate thread.

    Parameters
    ----------
    engine : RealTimeMatchEngine
        Running match engine instance whose state should be logged.
    """
    last_event_count = 0
    last_minute = -1

    while engine.is_running:
        current_minute = int(engine.state.match_time // 60)

        # Print time and score every minute
        if current_minute != last_minute:
            print(f"\nMatch Time: {current_minute:02d}:00")
            score_msg = (
                f"Score: {engine.state.home_team.name} {engine.state.home_score} - "
                f"{engine.state.away_score} {engine.state.away_team.name}"
            )
            print(score_msg)
            last_minute = current_minute

        # Print new events as they happen
        new_events = engine.state.events[last_event_count:]
        for event in new_events:
            if event.event_type in ["goal", "shot"]:
                event_time = int(event.timestamp // 60)
                print(f"{event_time}': {event.description}")
        last_event_count = len(engine.state.events)

        # Update every second
        time.sleep(1.0)


def main() -> None:
    """Spin up a demo match, wiring the engine to optional visual outputs."""
    # Try to load teams from JSON file, fall back to generated teams if not found
    roster_file = Path("data/players.json")
    if roster_file.exists():
        try:
            home_team, away_team = load_teams_from_json(roster_file)
        except Exception as e:
            print(f"Error loading teams from {roster_file}: {e}")
            print("Falling back to generated teams...")
            home_team = generate_team(1, "Manchester United", "4-3-3", starting_player_id=1, side="home")
            away_team = generate_team(2, "Liverpool FC", "4-4-2", starting_player_id=100, side="away")
    else:
        print(f"No roster file found at {roster_file}")
        print("Using generated teams...")
        home_team = generate_team(1, "Manchester United", "4-3-3", starting_player_id=1, side="home")
        away_team = generate_team(2, "Liverpool FC", "4-4-2", starting_player_id=100, side="away")

    # Create real-time match engine
    engine = RealTimeMatchEngine(home_team, away_team)

    # Set simulation speed (optional)
    engine.simulation_speed = 1.0  # 5x speed for moderate simulation

    # We'll start the engine only after the user clicks Start in the visualizer.
    engine_thread = None
    status_thread = None

    def start_engine() -> None:
        nonlocal engine_thread, status_thread
        if engine_thread is None:
            # Create non-daemon engine thread so we can join it for a clean shutdown
            engine_thread = threading.Thread(target=engine.start_match)
            engine_thread.start()
            # Start status printer in a separate thread
            status_thread = threading.Thread(target=print_match_status, args=(engine,))
            # Keep status thread joinable as well
            status_thread.start()
        return engine_thread

    # Try to start visualizer (if pygame is installed). Pass start_engine as callback.
    try:
        from touchline.visualizer.visualizer import start_visualizer

        # Start visualizer as a non-daemon thread so we wait for it to finish
        vis_thread = threading.Thread(
            target=start_visualizer,
            args=(engine,),
            kwargs={"start_callback": start_engine},
        )
        vis_thread.start()
    except Exception:
        # pygame or visualizer not available — continue without graphics
        pass

    print("Visualizer started. Press Start Match in the window to begin the simulation.")

    # Wait for engine to be started and finish, or for the visualizer to exit
    try:
        while True:
            if engine_thread is not None:
                engine_thread.join()
                break
            if "vis_thread" in locals() and not vis_thread.is_alive():
                # Visualizer closed before match started
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nMatch simulation interrupted.")
        engine.stop_match()
        if engine_thread is not None:
            engine_thread.join()
        # Join status and visualizer threads if they exist (allow a little
        # longer for a graceful shutdown)
        if status_thread is not None and status_thread.is_alive():
            status_thread.join(timeout=3.0)
        if "vis_thread" in locals() and vis_thread.is_alive():
            vis_thread.join(timeout=3.0)
    else:
        # Normal exit path: ensure threads are joined cleanly
        if status_thread is not None and status_thread.is_alive():
            status_thread.join()
        if "vis_thread" in locals() and vis_thread.is_alive():
            vis_thread.join()

    # Print final stats
    print(
        f"\nFinal Score: {engine.state.home_team.name} {engine.state.home_score} - "
        f"{engine.state.away_score} {engine.state.away_team.name}"
    )

    # Count total shots
    home_shots = sum(1 for e in engine.state.events if e.event_type == "shot" and e.team == home_team)
    away_shots = sum(1 for e in engine.state.events if e.event_type == "shot" and e.team == away_team)

    print("\nMatch Statistics:")
    print(f"{home_team.name}:")
    print(f"Shots: {home_shots}")

    print(f"\n{away_team.name}:")
    print(f"Shots: {away_shots}")


if __name__ == "__main__":
    main()
