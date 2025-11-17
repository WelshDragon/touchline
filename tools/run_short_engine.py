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
"""Run a short match simulation using teams from players.json."""
from pathlib import Path

from touchline.engine.match_engine import RealTimeMatchEngine
from touchline.utils.roster import load_teams_from_json


def run_short_simulation(duration_seconds: float = 20.0, timestep: float = 0.05) -> None:
    """Run a short match simulation using direct updates for accuracy.
    
    Parameters
    ----------
    duration_seconds : float
        How long to simulate in match time (default 20 seconds).
    timestep : float
        Physics timestep in seconds (default 0.05 = 50ms, same as main engine).
    """
    # Load teams from players.json
    data_path = Path(__file__).parent.parent / "data" / "players.json"
    home, away = load_teams_from_json(str(data_path))
    
    # Create engine
    engine = RealTimeMatchEngine(home, away)
    
    # Calculate number of steps needed
    num_steps = int(duration_seconds / timestep)
    
    # Run simulation with fixed timestep for accuracy
    for _ in range(num_steps):
        engine._update(timestep)
    
    # Stop and close debugger
    engine.stop_match()
    print(f"Done running {duration_seconds}s simulation ({num_steps} steps)")


if __name__ == "__main__":
    run_short_simulation(180.0)
