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
from __future__ import annotations

from typing import Dict, Type

from .base import RoleBehaviour
from .defenders import (
    CentralDefenderRoleBehaviour,
    LeftDefenderRoleBehaviour,
    RightDefenderRoleBehaviour,
)
from .forwards import (
    CentreForwardRoleBehaviour,
    LeftCentreForwardRoleBehaviour,
    RightCentreForwardRoleBehaviour,
)
from .goalkeeper import GoalkeeperRoleBehaviour
from .midfielders import (
    CentralMidfielderRoleBehaviour,
    LeftMidfielderRoleBehaviour,
    RightMidfielderRoleBehaviour,
)

ROLE_BEHAVIOUR_CLASSES: Dict[str, Type[RoleBehaviour]] = {
    "GK": GoalkeeperRoleBehaviour,
    "RD": RightDefenderRoleBehaviour,
    "CD": CentralDefenderRoleBehaviour,
    "LD": LeftDefenderRoleBehaviour,
    "RM": RightMidfielderRoleBehaviour,
    "CM": CentralMidfielderRoleBehaviour,
    "LM": LeftMidfielderRoleBehaviour,
    "CF": CentreForwardRoleBehaviour,
    "LCF": LeftCentreForwardRoleBehaviour,
    "RCF": RightCentreForwardRoleBehaviour,
}


def create_role_behaviour(role: str) -> RoleBehaviour:
    try:
        behaviour_cls = ROLE_BEHAVIOUR_CLASSES[role]
    except KeyError as exc:
        known_roles = ", ".join(sorted(ROLE_BEHAVIOUR_CLASSES))
        raise ValueError(f"Unknown role '{role}'. Known roles: {known_roles}") from exc
    return behaviour_cls()


__all__ = [
    "RoleBehaviour",
    "GoalkeeperRoleBehaviour",
    "RightDefenderRoleBehaviour",
    "CentralDefenderRoleBehaviour",
    "LeftDefenderRoleBehaviour",
    "RightMidfielderRoleBehaviour",
    "CentralMidfielderRoleBehaviour",
    "LeftMidfielderRoleBehaviour",
    "CentreForwardRoleBehaviour",
    "LeftCentreForwardRoleBehaviour",
    "RightCentreForwardRoleBehaviour",
    "ROLE_BEHAVIOUR_CLASSES",
    "create_role_behaviour",
]
