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
from time import sleep

from touchline.engine.match_engine import RealTimeMatchEngine
from touchline.models.player import Player, PlayerAttributes
from touchline.models.team import Formation, Team


# Helper to create N players with sequential ids starting at base_id
def make_players(base_id, team_name):
    players = []
    role_order = ["GK", "RD", "CD", "CD", "LD", "RM", "CM", "CM", "LM", "RCF", "LCF"]
    for i in range(11):
        pid = base_id + i
        attrs = PlayerAttributes(
            passing=50,
            shooting=50,
            dribbling=60,
            tackling=40,
            heading=40,
            speed=60,
            stamina=80,
            strength=60,
            vision=50,
            positioning=50,
            decisions=50,
        )
        role = role_order[i]
        players.append(
            Player(
                player_id=pid,
                name=f"{team_name} Player {pid}",
                age=25,
                role=role,
                attributes=attrs,
            )
        )
    return players


home_players = make_players(1, "Home")
away_players = make_players(100, "Away")
formation = Formation(
    name="4-4-2",
    role_counts={"RD": 1, "CD": 2, "LD": 1, "RM": 1, "CM": 2, "LM": 1, "RCF": 1, "LCF": 1},
)
home = Team(1, "Home FC", home_players, formation)
away = Team(2, "Away FC", away_players, formation)

engine = RealTimeMatchEngine(home, away)

# Run 2400 steps of 0.05s (~120 seconds simulated)
for _ in range(2400):
    engine._update(0.05)

# Stop and close debugger
engine.stop_match()
print("Done running short engine")
