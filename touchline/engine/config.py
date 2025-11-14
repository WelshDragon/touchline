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
"""Central configuration for engine tuning parameters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(slots=True)
class PitchConfig:
    width: float = 105.0
    height: float = 68.0
    goal_width: float = 7.32
    penalty_area_width: float = 40.32
    penalty_area_depth: float = 16.5
    goal_area_width: float = 18.32
    goal_area_depth: float = 5.5


@dataclass(slots=True)
class SimulationConfig:
    match_duration: float = 90 * 60  # seconds
    frame_sleep: float = 0.016  # 60fps target
    default_speed: float = 1.0
    initial_ball_velocity: Tuple[float, float] = (5.0, 2.0)


@dataclass(slots=True)
class PossessionConfig:
    loose_ball_speed_threshold: float = 5.0
    target_radius_min: float = 1.1
    target_radius_max: float = 1.3
    target_radius_speed_factor: float = 0.08
    direction_alignment_min: float = -0.1
    base_radius: float = 0.5
    medium_speed_threshold: float = 1.5
    medium_radius: float = 0.8
    slow_speed_threshold: float = 0.3
    slow_radius: float = 1.0
    continue_control_offset: float = 0.45
    continue_velocity_blend: float = 0.8


@dataclass(slots=True)
class FormationConfig:
    goalkeeper_x: float = 45.0
    fullback_x: float = 35.0
    fullback_base_offset: float = 12.0
    fullback_stagger: float = 2.0
    centreback_x: float = 35.0
    centreback_offsets: Tuple[float, ...] = (-6.0, 6.0, -12.0, 12.0)
    wide_midfielder_x: float = 20.0
    wide_midfielder_base_offset: float = 15.0
    wide_midfielder_stagger: float = 2.0
    central_midfielder_x: float = 18.0
    central_midfielder_offsets: Tuple[float, ...] = (-8.0, 8.0, 0.0, -14.0, 14.0)
    centre_forward_x: float = 8.0
    centre_forward_offsets: Tuple[float, ...] = (0.0, -6.0, 6.0)
    wide_forward_base_offset: float = 10.0
    wide_forward_stagger: float = 2.0


@dataclass(slots=True)
class BallPhysicsConfig:
    friction: float = 0.95
    stop_threshold: float = 0.1


@dataclass(slots=True)
class PlayerMovementConfig:
    base_speed: float = 6.0
    base_multiplier: float = 0.7
    attribute_multiplier: float = 0.6
    sprint_multiplier: float = 1.4
    stamina_drain_factor: float = 0.8
    recovery_threshold: float = 1.0
    recovery_rate: float = 5.0


@dataclass(slots=True)
class ShootingConfig:
    max_distance_base: float = 25.0
    max_distance_bonus: float = 15.0
    long_range_distance: float = 20.0
    angle_threshold: float = 0.3
    probability_scale: float = 0.2
    goal_offset_range: float = 3.0
    power_distance_scale: float = 1.2
    power_base: float = 15.0
    power_clamp: float = 35.0
    power_accuracy_base: float = 0.8
    power_accuracy_scale: float = 0.4


@dataclass(slots=True)
class PassingConfig:
    max_distance_base: float = 30.0
    max_distance_bonus: float = 30.0
    min_distance: float = 5.0
    lane_weight: float = 0.4
    distance_weight: float = 0.3
    progress_weight: float = 0.3
    score_threshold: float = 0.3
    lane_block_distance: float = 5.0
    power_min_base: float = 2.8
    power_min_bonus: float = 2.5
    power_max_base: float = 13.0
    power_max_bonus: float = 5.5
    distance_norm: float = 30.0
    easing_exponent: float = 0.5
    inaccuracy_max: float = 2.0
    repeat_penalty_base: float = 0.25
    repeat_penalty_decay: float = 0.05
    immediate_return_penalty: float = 0.3


@dataclass(slots=True)
class InterceptConfig:
    min_ball_speed: float = 0.2
    max_time: float = 3.0
    time_step: float = 0.2
    reaction_buffer: float = 0.15
    fallback_fraction: float = 0.25
    fallback_cap: float = 4.5


@dataclass(slots=True)
class ReceivePassConfig:
    player_speed_base: float = 4.3
    player_speed_attr_scale: float = 3.2
    stop_distance: float = 0.4
    move_base_speed: float = 4.5
    move_attr_scale: float = 3.0


@dataclass(slots=True)
class LooseBallConfig:
    player_speed_base: float = 4.6
    player_speed_attr_scale: float = 3.4
    intercept_max_time: float = 3.2
    intercept_reaction_buffer: float = 0.18
    intercept_fallback_fraction: float = 0.18
    intercept_fallback_cap: float = 4.5
    stop_distance: float = 0.35
    move_base_speed: float = 5.0
    move_attr_scale: float = 3.2


@dataclass(slots=True)
class PossessionSupportConfig:
    gap_weight: float = 0.8
    push_bias: float = 0.3
    ahead_threshold: float = 15.0
    ahead_factor_low: float = 0.4
    ahead_factor_high: float = 0.7


@dataclass(slots=True)
class LaneSpacingConfig:
    lane_weight: float = 0.25
    min_spacing: float = 6.0
    separation_scale: float = 0.5


@dataclass(slots=True)
class DefensiveLineConfig:
    far_threshold: float = 40.0
    close_threshold: float = 20.0
    close_offset: float = 15.0
    advanced_offset: float = 25.0
    y_pull_factor: float = 0.2


@dataclass(slots=True)
class PressingConfig:
    stamina_threshold: float = 30.0
    distance_threshold: float = 15.0


@dataclass(slots=True)
class SpaceFindingConfig:
    search_radius: float = 15.0
    angle_step: int = 30


@dataclass(slots=True)
class DefenderConfig:
    tackle_ball_distance: float = 3.0
    tackle_range_base: float = 1.5
    tackle_range_attr_scale: float = 1.0
    tackle_success_distance: float = 1.2
    tackle_success_scale: float = 0.7
    clear_power: float = 20.0
    intercept_ball_speed_min: float = 3.0
    intercept_distance_limit: float = 15.0
    intercept_speed_scale: float = 7.0
    intercept_improvement_factor: float = 0.8
    threat_marking_range: float = 25.0
    threat_marked_distance: float = 3.0
    threat_ball_distance: float = 30.0
    threat_goal_distance: float = 50.0
    threat_unmarked_bonus: float = 0.3
    threat_ball_weight: float = 0.2
    threat_goal_weight: float = 0.2
    threat_marking_weight: float = 0.2
    threat_proximity_weight: float = 0.4
    threat_proximity_distance: float = 25.0
    marking_distance_base: float = 2.0
    marking_distance_attr_scale: float = 1.0
    marking_ball_distance: float = 10.0
    marking_ball_adjustment: float = 1.0
    marking_speed_attr: int = 70
    dribble_speed: float = 3.0
    fullback_min_width: float = 8.0
    centreback_shift_factor: float = 0.15
    centreback_max_width: float = 12.0


@dataclass(slots=True)
class MidfielderConfig:
    press_stamina_threshold: float = 25.0
    pressure_radius: float = 4.0
    pressure_dribble_threshold: int = 60
    retreat_speed: float = 2.0
    dribble_speed_base: float = 3.0
    dribble_speed_attr_scale: float = 2.0
    dribble_pressure_base: float = 2.0
    dribble_pressure_attr_scale: float = 2.0
    relief_min_distance: float = 3.0
    relief_max_distance: float = 28.0
    relief_lane_weight: float = 0.4
    relief_space_weight: float = 0.3
    relief_distance_weight: float = 0.1
    relief_progress_bonus: float = 0.2
    relief_score_threshold: float = 0.25
    relief_space_divisor: float = 6.0
    relief_nearest_default: float = 10.0
    relief_vision_base: float = 0.7
    relief_vision_scale: float = 0.3
    progressive_pass_vision_threshold: int = 70
    press_success_distance: float = 1.5
    press_success_scale: float = 0.5
    support_trail_distance: float = 12.0
    support_forward_distance: float = 10.0
    support_defense_push: float = 5.0
    right_width: float = 12.0
    left_width: float = 12.0
    central_shift_factor: float = 0.3
    central_max_width: float = 15.0


@dataclass(slots=True)
class ForwardConfig:
    shoot_distance_threshold: float = 25.0
    pressure_radius: float = 3.0
    pressure_dribble_threshold: int = 70
    vision_progressive_threshold: int = 70
    vision_pressure_release_threshold: int = 50
    dribble_speed_base: float = 3.5
    dribble_speed_attr_scale: float = 2.5
    dribble_pressure_base: float = 2.0
    dribble_pressure_attr_scale: float = 2.0
    dribble_control_offset: float = 0.65
    dribble_velocity_blend: float = 0.85
    escape_angle_step: int = 45
    escape_base_space: float = 10.0
    escape_opponent_scale: float = 10.0
    relief_min_distance: float = 3.0
    relief_max_distance: float = 25.0
    relief_lane_weight: float = 0.45
    relief_space_weight: float = 0.25
    relief_distance_weight: float = 0.1
    relief_progress_bonus: float = 0.2
    relief_support_bonus: float = 0.05
    relief_score_threshold: float = 0.25
    relief_space_divisor: float = 5.0
    relief_nearest_default: float = 10.0
    relief_vision_base: float = 0.6
    relief_vision_scale: float = 0.4
    pressing_distance: float = 20.0
    run_ballcarrier_distance: float = 30.0
    run_goal_weight: float = 0.7
    run_ball_weight: float = 0.3
    onside_margin: float = 2.0
    hold_position_adjustment: float = 5.0
    centre_adjust_factor: float = 0.3
    centre_max_width: float = 8.0
    wide_min_offset: float = 5.0
    wide_max_width: float = 15.0
    cut_inside_factor: float = 0.7


@dataclass(slots=True)
class GoalkeeperConfig:
    save_min_ball_speed: float = 3.0
    save_forward_speed_threshold: float = 0.3
    save_plane_buffer: float = 0.3
    save_time_horizon: float = 1.05
    save_post_buffer: float = 1.4
    save_box_buffer: float = 1.5
    reach_reaction_buffer: float = 0.05
    reach_distance_buffer: float = 0.35
    success_distance: float = 1.5
    success_eta_threshold: float = 0.25
    log_eta_threshold: float = 0.2
    collect_speed_threshold: float = 5.0
    collect_safe_distance_base: float = 8.0
    collect_safe_distance_attr_scale: float = 5.0
    collect_success_distance: float = 1.5
    positioning_distance_base: float = 2.0
    positioning_distance_attr_scale: float = 2.0
    positioning_min_offset: float = 0.8
    positioning_angle_factor: float = 0.3
    positioning_max_lateral: float = 3.0
    positioning_speed_attr: int = 50


@dataclass(slots=True)
class RoleBehaviourConfig:
    shooting: ShootingConfig = field(default_factory=ShootingConfig)
    passing: PassingConfig = field(default_factory=PassingConfig)
    intercept: InterceptConfig = field(default_factory=InterceptConfig)
    receive_pass: ReceivePassConfig = field(default_factory=ReceivePassConfig)
    loose_ball: LooseBallConfig = field(default_factory=LooseBallConfig)
    possession_support: PossessionSupportConfig = field(default_factory=PossessionSupportConfig)
    lane_spacing: LaneSpacingConfig = field(default_factory=LaneSpacingConfig)
    defensive: DefensiveLineConfig = field(default_factory=DefensiveLineConfig)
    pressing: PressingConfig = field(default_factory=PressingConfig)
    space_finding: SpaceFindingConfig = field(default_factory=SpaceFindingConfig)
    defender: DefenderConfig = field(default_factory=DefenderConfig)
    midfielder: MidfielderConfig = field(default_factory=MidfielderConfig)
    forward: ForwardConfig = field(default_factory=ForwardConfig)
    goalkeeper: GoalkeeperConfig = field(default_factory=GoalkeeperConfig)
    support_profiles: Dict[str, Tuple[float, float, float]] = field(
        default_factory=lambda: {
            "GK": (0.0, 12.0, 0.0),
            "CD": (8.0, 14.0, 4.0),
            "LD": (8.0, 14.0, 4.0),
            "RD": (8.0, 14.0, 4.0),
            "CM": (14.0, 8.0, 12.0),
            "RM": (14.0, 8.0, 12.0),
            "LM": (14.0, 8.0, 12.0),
            "CF": (9.0, 5.0, 10.0),
            "LCF": (9.0, 5.0, 10.0),
            "RCF": (9.0, 5.0, 10.0),
            "default": (7.0, 10.0, 8.0),
        }
    )


@dataclass(slots=True)
class EngineConfig:
    pitch: PitchConfig = field(default_factory=PitchConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    possession: PossessionConfig = field(default_factory=PossessionConfig)
    formation: FormationConfig = field(default_factory=FormationConfig)
    ball_physics: BallPhysicsConfig = field(default_factory=BallPhysicsConfig)
    player_movement: PlayerMovementConfig = field(default_factory=PlayerMovementConfig)
    role: RoleBehaviourConfig = field(default_factory=RoleBehaviourConfig)


ENGINE_CONFIG = EngineConfig()
"""Singleton-style access to the engine configuration."""
