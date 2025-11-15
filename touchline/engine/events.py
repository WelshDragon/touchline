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
"""Event domain models for the match engine."""

from __future__ import annotations

from dataclasses import dataclass

from touchline.models.team import Team


@dataclass
class MatchEvent:
    """Snapshot of a noteworthy moment during a simulation.

    Parameters
    ----------
    timestamp : float
        Seconds elapsed since the start of the match when the event occurred.
    event_type : str
        Category of event (for example ``"goal"`` or ``"shot"``).
    team : Team
        Team associated with the event.
    description : str
        Human-readable summary of what happened.
    """

    timestamp: float  # seconds from match start
    event_type: str  # goal, shot, pass, tackle, etc.
    team: Team
    description: str
