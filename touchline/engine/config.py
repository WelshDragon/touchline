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
    """Physical dimensions and penalty box measurements for the pitch.

    Parameters
    ----------
    width : float, default=105.0
        Total pitch width in metres.
    height : float, default=68.0
        Total pitch height in metres.
    goal_width : float, default=7.32
        Width of the goal mouth.
    penalty_area_width : float, default=40.32
        Width of the penalty box.
    penalty_area_depth : float, default=16.5
        Depth of the penalty box extending from the goal line.
    goal_area_width : float, default=18.32
        Width of the six-yard box.
    goal_area_depth : float, default=5.5
        Depth of the six-yard box from the goal line.
    """

    width: float = 105.0
    height: float = 68.0
    goal_width: float = 7.32
    penalty_area_width: float = 40.32
    penalty_area_depth: float = 16.5
    goal_area_width: float = 18.32
    goal_area_depth: float = 5.5


@dataclass(slots=True)
class SimulationConfig:
    """Timing and speed controls for the main simulation loop.

    Parameters
    ----------
    match_duration : float, default=5400.0
        Total simulated match length in seconds.
    frame_sleep : float, default=0.016
        Delay between frames when running in real time.
    default_speed : float, default=1.0
        Default playback speed multiplier.
    initial_ball_velocity : Tuple[float, float], default=(5.0, 2.0)
        Initial velocity vector applied to the ball when play starts.
    """

    match_duration: float = 90 * 60  # seconds
    frame_sleep: float = 0.016  # 60fps target
    default_speed: float = 1.0
    initial_ball_velocity: Tuple[float, float] = (5.0, 2.0)


@dataclass(slots=True)
class PossessionConfig:
    """Thresholds that determine possession changes and control smoothing.

    Parameters
    ----------
    loose_ball_speed_threshold : float, default=5.0
        Ball speed above which it is considered loose.
    target_radius_min : float, default=1.1
        Minimum radius used when targeting possession control.
    target_radius_max : float, default=1.3
        Maximum radius allowed for possession targeting.
    target_radius_speed_factor : float, default=0.08
        Scaling applied to radius based on ball speed.
    direction_alignment_min : float, default=-0.1
        Minimum alignment between velocity vectors needed to maintain control.
    base_radius : float, default=0.5
        Base radius for close control.
    medium_speed_threshold : float, default=1.5
        Cutoff speed signalling medium-paced movement.
    medium_radius : float, default=0.8
        Radius used when the ball travels at medium speed.
    slow_speed_threshold : float, default=0.3
        Threshold below which the ball is considered slow.
    slow_radius : float, default=1.0
        Radius applied when the ball is slow moving.
    continue_control_offset : float, default=0.45
        Offset applied when continuing existing control.
    continue_velocity_blend : float, default=0.8
        Blend factor between previous and current velocity.
    max_control_distance : float, default=0.6
        Maximum allowable distance for a player to retain control.
    target_receive_leeway : float, default=0.35
        Extra leeway applied to the receiver acceptance radius.
    release_leeway : float, default=0.15
        Buffer applied when releasing the ball.
    target_velocity_gate : float, default=2.0
        Velocity threshold limiting control target updates.
    """

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
    max_control_distance: float = 0.6
    target_receive_leeway: float = 0.35
    release_leeway: float = 0.15
    target_velocity_gate: float = 2.0


@dataclass(slots=True)
class FormationConfig:
    """Reference coordinates for placing players when generating formations.

    Parameters
    ----------
    goalkeeper_x : float, default=45.0
        X coordinate for the goalkeeper reference position.
    fullback_x : float, default=35.0
        X coordinate for the fullback line.
    fullback_base_offset : float, default=12.0
        Base lateral offset applied to fullbacks.
    fullback_stagger : float, default=2.0
        Additional stagger added between fullbacks.
    centreback_x : float, default=35.0
        X coordinate for centre-back positioning.
    centreback_offsets : Tuple[float, ...], default=(-6.0, 6.0, -12.0, 12.0)
        Lateral offsets for multiple centre-backs.
    wide_midfielder_x : float, default=20.0
        X coordinate for wide midfielders.
    wide_midfielder_base_offset : float, default=15.0
        Base lateral offset for wide midfielders.
    wide_midfielder_stagger : float, default=2.0
        Stagger distance applied to wide midfielders.
    central_midfielder_x : float, default=18.0
        X coordinate for central midfielders.
    central_midfielder_offsets : Tuple[float, ...], default=(-8.0, 8.0, 0.0, -14.0, 14.0)
        Lateral offsets for central midfielders.
    centre_forward_x : float, default=8.0
        X coordinate for centre forwards.
    centre_forward_offsets : Tuple[float, ...], default=(0.0, -6.0, 6.0)
        Lateral offsets for centre forwards.
    wide_forward_base_offset : float, default=10.0
        Base lateral offset for wide forwards.
    wide_forward_stagger : float, default=2.0
        Stagger applied to wide forwards.
    """

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
    """Coefficients that govern ball flight, bounces, and friction.

    Parameters
    ----------
    friction : float, default=0.95
        Per-timestep friction multiplier applied to the ball.
    stop_threshold : float, default=0.1
        Velocity threshold below which the ball is treated as stationary.
    ground_drag : float, default=0.18
        Linear drag coefficient applied while rolling.
    bounce_damping : float, default=0.55
        Multiplier reducing velocity after a bounce.
    bounce_stop_speed : float, default=1.1
        Minimum speed required for additional bounces to occur.
    airborne_speed_threshold : float, default=14.0
        Speed above which the ball is considered airborne.
    airborne_time_scale : float, default=0.05
        Scaling factor controlling hang time while airborne.
    airborne_time_max : float, default=1.4
        Cap on maximum airborne duration in seconds.
    """

    friction: float = 0.95
    stop_threshold: float = 0.1
    ground_drag: float = 0.18
    bounce_damping: float = 0.55
    bounce_stop_speed: float = 1.1
    airborne_speed_threshold: float = 14.0
    airborne_time_scale: float = 0.05
    airborne_time_max: float = 1.4


@dataclass(slots=True)
class RoleSpeedProfile:
    """Per-role movement capabilities expressed as jogging, running, and sprinting.

    Parameters
    ----------
    jog_speed : float
        Baseline jogging speed in metres per second.
    run_speed : float
        Sustained running speed in metres per second.
    sprint_speed : float
        Maximum sprint speed in metres per second.
    acceleration : float
        Acceleration capability per second.
    deceleration : float
        Deceleration capability per second.
    """

    jog_speed: float
    run_speed: float
    sprint_speed: float
    acceleration: float
    deceleration: float


@dataclass(slots=True)
class PlayerMovementConfig:
    """Base locomotion settings and per-intent modifiers for player motion.

    Parameters
    ----------
    base_speed : float, default=6.0
        Baseline movement speed in metres per second.
    base_multiplier : float, default=0.7
        Global multiplier applied to base speed.
    attribute_multiplier : float, default=0.6
        Contribution of the speed attribute to final speed.
    sprint_multiplier : float, default=1.4
        Multiplier applied when sprinting.
    stamina_drain_factor : float, default=0.8
        How quickly stamina drains during exertion.
    recovery_threshold : float, default=1.0
        Stamina level below which recovery behaviour is triggered.
    recovery_rate : float, default=5.0
        Stamina recovered per second when resting.
    arrive_radius : float, default=3.5
        Radius at which arrive steering starts to slow the player.
    speed_scale_min : float, default=0.75
        Minimum multiplier applied via role intent modifiers.
    speed_scale_max : float, default=1.25
        Maximum multiplier applied via role intent modifiers.
    acceleration_scale_min : float, default=0.75
        Minimum acceleration scaling for intent modifiers.
    acceleration_scale_max : float, default=1.25
        Maximum acceleration scaling for intent modifiers.
    deceleration_scale_min : float, default=0.8
        Minimum deceleration scaling for intent modifiers.
    deceleration_scale_max : float, default=1.2
        Maximum deceleration scaling for intent modifiers.
    intent_press_arrive_scale : float, default=0.6
        Arrival radius multiplier while pressing.
    intent_press_accel_scale : float, default=1.0
        Acceleration multiplier while pressing.
    intent_press_decel_scale : float, default=1.0
        Deceleration multiplier while pressing.
    intent_mark_arrive_scale : float, default=1.0
        Arrival radius multiplier while marking.
    intent_mark_accel_scale : float, default=1.0
        Acceleration multiplier while marking.
    intent_mark_decel_scale : float, default=1.0
        Deceleration multiplier while marking.
    intent_shape_arrive_scale : float, default=1.2
        Arrival radius multiplier for defensive shape.
    intent_shape_accel_scale : float, default=0.7
        Acceleration multiplier for defensive shape.
    intent_shape_decel_scale : float, default=0.85
        Deceleration multiplier for defensive shape.
    intent_support_arrive_scale : float, default=1.0
        Arrival radius multiplier while supporting.
    intent_support_accel_scale : float, default=0.85
        Acceleration multiplier while supporting.
    intent_support_decel_scale : float, default=0.95
        Deceleration multiplier while supporting.
    intent_support_speed_blend : float, default=0.5
        Blend between support and base speed.
    role_profiles : Dict[str, RoleSpeedProfile]
        Mapping of role codes to their movement profiles.
    """

    base_speed: float = 6.0
    base_multiplier: float = 0.7
    attribute_multiplier: float = 0.6
    sprint_multiplier: float = 1.4
    stamina_drain_factor: float = 0.8
    recovery_threshold: float = 1.0
    recovery_rate: float = 5.0
    arrive_radius: float = 3.5
    speed_scale_min: float = 0.75
    speed_scale_max: float = 1.25
    acceleration_scale_min: float = 0.75
    acceleration_scale_max: float = 1.25
    deceleration_scale_min: float = 0.8
    deceleration_scale_max: float = 1.2
    intent_press_arrive_scale: float = 0.6
    intent_press_accel_scale: float = 1.0
    intent_press_decel_scale: float = 1.0
    intent_mark_arrive_scale: float = 1.0
    intent_mark_accel_scale: float = 1.0
    intent_mark_decel_scale: float = 1.0
    intent_shape_arrive_scale: float = 1.2
    intent_shape_accel_scale: float = 0.7
    intent_shape_decel_scale: float = 0.85
    intent_support_arrive_scale: float = 1.0
    intent_support_accel_scale: float = 0.85
    intent_support_decel_scale: float = 0.95
    intent_support_speed_blend: float = 0.5
    role_profiles: Dict[str, RoleSpeedProfile] = field(
        default_factory=lambda: {
            "GK": RoleSpeedProfile(
                jog_speed=3.4,
                run_speed=4.8,
                sprint_speed=5.6,
                acceleration=7.2,
                deceleration=9.5,
            ),
            "CD": RoleSpeedProfile(
                jog_speed=4.1,
                run_speed=5.6,
                sprint_speed=6.6,
                acceleration=8.6,
                deceleration=11.2,
            ),
            "LD": RoleSpeedProfile(
                jog_speed=4.4,
                run_speed=6.1,
                sprint_speed=7.4,
                acceleration=9.4,
                deceleration=12.0,
            ),
            "RD": RoleSpeedProfile(
                jog_speed=4.4,
                run_speed=6.1,
                sprint_speed=7.4,
                acceleration=9.4,
                deceleration=12.0,
            ),
            "CM": RoleSpeedProfile(
                jog_speed=4.5,
                run_speed=6.3,
                sprint_speed=7.5,
                acceleration=9.6,
                deceleration=12.4,
            ),
            "LM": RoleSpeedProfile(
                jog_speed=4.6,
                run_speed=6.6,
                sprint_speed=7.8,
                acceleration=9.9,
                deceleration=12.8,
            ),
            "RM": RoleSpeedProfile(
                jog_speed=4.6,
                run_speed=6.6,
                sprint_speed=7.8,
                acceleration=9.9,
                deceleration=12.8,
            ),
            "CF": RoleSpeedProfile(
                jog_speed=4.7,
                run_speed=6.7,
                sprint_speed=7.9,
                acceleration=10.0,
                deceleration=13.0,
            ),
            "LCF": RoleSpeedProfile(
                jog_speed=4.7,
                run_speed=6.7,
                sprint_speed=7.9,
                acceleration=10.0,
                deceleration=13.0,
            ),
            "RCF": RoleSpeedProfile(
                jog_speed=4.7,
                run_speed=6.7,
                sprint_speed=7.9,
                acceleration=10.0,
                deceleration=13.0,
            ),
            "default": RoleSpeedProfile(
                jog_speed=4.4,
                run_speed=6.0,
                sprint_speed=7.2,
                acceleration=9.0,
                deceleration=11.5,
            ),
        }
    )


@dataclass(slots=True)
class ShootingConfig:
    """Shot selection heuristics and power calculations for attackers.

    Parameters
    ----------
    max_distance_base : float, default=25.0
        Baseline maximum shooting distance.
    max_distance_bonus : float, default=15.0
        Additional range unlocked by higher shooting ability.
    long_range_distance : float, default=20.0
        Distance beyond which long-range heuristics apply.
    angle_threshold : float, default=0.3
        Minimum angle quality required for long-range shots.
    probability_scale : float, default=0.2
        Global multiplier shaping shot likelihood.
    goal_offset_range : float, default=3.0
        Maximum lateral offset when aiming for corners.
    corner_depth_bias : float, default=0.8
        Base depth for targeting goal corners.
    corner_depth_spread : float, default=0.6
        Additional depth variability tied to accuracy.
    power_distance_scale : float, default=1.2
        Scaling factor relating distance to shot power.
    power_base : float, default=15.0
        Minimum shot power in metres per second.
    power_clamp : float, default=35.0
        Maximum shot power clamp.
    power_accuracy_base : float, default=0.8
        Base accuracy multiplier applied to power calculations.
    power_accuracy_scale : float, default=0.4
        Additional accuracy scaling derived from shooting ability.
    """

    max_distance_base: float = 25.0
    max_distance_bonus: float = 15.0
    long_range_distance: float = 20.0
    angle_threshold: float = 0.3
    probability_scale: float = 0.2
    goal_offset_range: float = 3.0  # Maximum vertical inset from the post when aiming for corners
    corner_depth_bias: float = 0.8  # How far inside the goal mouth to aim (meters)
    corner_depth_spread: float = 0.6  # Additional depth variation scaled by inaccuracy
    power_distance_scale: float = 1.2
    power_base: float = 15.0
    power_clamp: float = 35.0
    power_accuracy_base: float = 0.8
    power_accuracy_scale: float = 0.4


@dataclass(slots=True)
class PassingConfig:
    """Scoring weights and power clamps that influence pass evaluation.

    Parameters
    ----------
    max_distance_base : float, default=30.0
        Baseline passable distance in metres.
    max_distance_bonus : float, default=30.0
        Extra range unlocked through passing attributes.
    min_distance : float, default=5.0
        Minimum safe pass distance to avoid short touches.
    lane_weight : float, default=0.4
        Weight assigned to lane clearance scoring.
    distance_weight : float, default=0.3
        Weight assigned to distance efficiency scoring.
    progress_weight : float, default=0.3
        Weight assigned to progressive movement scoring.
    score_threshold : float, default=0.3
        Minimum score required to attempt a pass.
    lane_block_distance : float, default=5.0
        Buffer distance used to detect blocked passing lanes.
    power_min_base : float, default=2.8
        Minimum power applied to very short passes.
    power_min_bonus : float, default=2.5
        Additional minimum power unlocked via accuracy.
    power_max_base : float, default=13.0
        Base cap for pass power.
    power_max_bonus : float, default=5.5
        Additional cap scaling with attributes.
    distance_norm : float, default=30.0
        Normalising factor for distance-based easing.
    easing_exponent : float, default=0.5
        Exponent driving the easing curve for pass power.
    inaccuracy_max : float, default=2.0
        Maximum random inaccuracy offset in metres.
    repeat_penalty_base : float, default=0.25
        Penalty applied to immediate repeated passes.
    repeat_penalty_decay : float, default=0.05
        Decay rate for repeated pass penalties.
    immediate_return_penalty : float, default=0.3
        Penalty applied if the pass is immediately returned.
    """

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
    """Search parameters for predicting interception opportunities.

    Parameters
    ----------
    min_ball_speed : float, default=0.2
        Minimum ball speed considered for interception calculations.
    max_time : float, default=3.0
        Maximum prediction horizon in seconds.
    time_step : float, default=0.2
        Step size in seconds for sampling intercept points.
    reaction_buffer : float, default=0.15
        Extra time allowance added for player reaction.
    fallback_fraction : float, default=0.25
        Fraction of prediction path used when falling back to heuristics.
    fallback_cap : float, default=4.5
        Maximum fallback distance in metres.
    """

    min_ball_speed: float = 0.2
    max_time: float = 3.0
    time_step: float = 0.2
    reaction_buffer: float = 0.15
    fallback_fraction: float = 0.25
    fallback_cap: float = 4.5


@dataclass(slots=True)
class ReceivePassConfig:
    """Movement assumptions used while a teammate receives an incoming pass.

    Parameters
    ----------
    player_speed_base : float, default=4.3
        Base speed assumed for the receiving player.
    player_speed_attr_scale : float, default=3.2
        Scaling factor applied from player speed attributes.
    stop_distance : float, default=0.4
        Distance at which the receiver aims to stop relative to the ball.
    move_base_speed : float, default=4.5
        Baseline movement speed while adjusting positioning.
    move_attr_scale : float, default=3.0
        Attribute scaling for movement speed.
    """

    player_speed_base: float = 4.3
    player_speed_attr_scale: float = 3.2
    stop_distance: float = 0.4
    move_base_speed: float = 4.5
    move_attr_scale: float = 3.0


@dataclass(slots=True)
class LooseBallConfig:
    """Fallback heuristics when both teams chase an uncontrolled ball.

    Parameters
    ----------
    player_speed_base : float, default=4.6
        Base chasing speed for loose ball situations.
    player_speed_attr_scale : float, default=3.4
        Attribute scaling applied to chasing speed.
    intercept_max_time : float, default=3.2
        Maximum prediction time used for interceptions.
    intercept_reaction_buffer : float, default=0.18
        Additional time allowance for reaction delays.
    intercept_fallback_fraction : float, default=0.18
        Fraction of trajectory used when heuristic fallback triggers.
    intercept_fallback_cap : float, default=4.5
        Maximum fallback distance applied.
    stop_distance : float, default=0.35
        Distance at which a player stops when winning the ball.
    move_base_speed : float, default=5.0
        Baseline movement speed toward the intercept point.
    move_attr_scale : float, default=3.2
        Attribute scaling for pursuit speed.
    """

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
    """Weighting for how supporting players position themselves around the ball.

    Parameters
    ----------
    gap_weight : float, default=0.8
        Weight applied to spatial gaps between defenders.
    push_bias : float, default=0.3
        Bias encouraging players to push forward.
    ahead_threshold : float, default=15.0
        Distance threshold determining if a teammate is ahead of the ball.
    ahead_factor_low : float, default=0.4
        Support weighting when only slightly ahead of the ball.
    ahead_factor_high : float, default=0.7
        Support weighting when well ahead of the ball.
    """

    gap_weight: float = 0.8
    push_bias: float = 0.3
    ahead_threshold: float = 15.0
    ahead_factor_low: float = 0.4
    ahead_factor_high: float = 0.7


@dataclass(slots=True)
class LaneSpacingConfig:
    """Spacing parameters that keep teammates from crowding passing lanes.

    Parameters
    ----------
    lane_weight : float, default=0.25
        Weight applied to lane spacing penalties.
    min_spacing : float, default=6.0
        Minimum desired distance between players sharing a lane.
    separation_scale : float, default=0.5
        Scale factor controlling additional separation.
    """

    lane_weight: float = 0.25
    min_spacing: float = 6.0
    separation_scale: float = 0.5


@dataclass(slots=True)
class DefensiveLineConfig:
    """Preferred distances that control the team's defensive line height.

    Parameters
    ----------
    far_threshold : float, default=40.0
        Distance indicating the opposition is far from goal.
    close_threshold : float, default=20.0
        Distance indicating the opposition is close to goal.
    close_offset : float, default=15.0
        Offset applied when the ball is nearby.
    advanced_offset : float, default=25.0
        Offset applied for advanced defensive positioning.
    y_pull_factor : float, default=0.2
        Weight pulling defenders toward the ball vertically.
    """

    far_threshold: float = 40.0
    close_threshold: float = 20.0
    close_offset: float = 15.0
    advanced_offset: float = 25.0
    y_pull_factor: float = 0.2


@dataclass(slots=True)
class PressingConfig:
    """Stamina and proximity thresholds for initiating a press.

    Parameters
    ----------
    stamina_threshold : float, default=30.0
        Minimum stamina percentage required to initiate a press.
    distance_threshold : float, default=15.0
        Maximum distance to the ball-carrier for press attempts.
    """

    stamina_threshold: float = 30.0
    distance_threshold: float = 15.0


@dataclass(slots=True)
class SpaceFindingConfig:
    """Search grid resolution for locating unoccupied space.

    Parameters
    ----------
    search_radius : float, default=15.0
        Radius in metres around the player to scan for space.
    angle_step : int, default=30
        Angular step in degrees between search rays.
    """

    search_radius: float = 15.0
    angle_step: int = 30


@dataclass(slots=True)
class DefenderConfig:
    """Behaviour tuning for defensive roles when marking and tackling.

    Parameters
    ----------
    tackle_ball_distance : float, default=3.0
        Distance at which defenders consider tackling the ball.
    tackle_range_base : float, default=1.5
        Base tackling range in metres.
    tackle_range_attr_scale : float, default=1.0
        Additional tackling range derived from attributes.
    tackle_success_distance : float, default=1.2
        Distance threshold for successful tackle resolution.
    tackle_success_scale : float, default=0.7
        Attribute scaling for tackle success probability.
    clear_power : float, default=20.0
        Power applied when clearing the ball.
    intercept_ball_speed_min : float, default=3.0
        Minimum ball speed to trigger interception logic.
    intercept_distance_limit : float, default=15.0
        Maximum interception distance.
    intercept_speed_scale : float, default=7.0
        Scaling factor for interception speed estimation.
    intercept_improvement_factor : float, default=0.8
        Bonus applied when defensive positioning improves interception odds.
    threat_marking_range : float, default=25.0
        Range in metres for marking threat evaluation.
    threat_marked_distance : float, default=3.0
        Distance within which an opponent is considered marked.
    threat_ball_distance : float, default=30.0
        Distance weighting threat relative to ball proximity.
    threat_goal_distance : float, default=50.0
        Distance weighting threat relative to goal proximity.
    threat_unmarked_bonus : float, default=0.3
        Threat bonus applied to unmarked opponents.
    threat_ball_weight : float, default=0.2
        Weight assigned to ball distance in threat scoring.
    threat_goal_weight : float, default=0.2
        Weight assigned to goal distance in threat scoring.
    threat_marking_weight : float, default=0.2
        Weight assigned to marking status in threat scoring.
    threat_proximity_weight : float, default=0.4
        Weight assigned to opponent proximity.
    threat_proximity_distance : float, default=25.0
        Maximum distance considered for proximity weighting.
    marking_distance_base : float, default=2.0
        Base distance defenders maintain when marking.
    marking_distance_attr_scale : float, default=1.0
        Attribute scaling for marking distance.
    marking_ball_distance : float, default=10.0
        Ball distance used to adjust marking.
    marking_ball_adjustment : float, default=1.0
        Adjustment applied according to ball distance.
    marking_speed_attr : int, default=70
        Speed attribute reference for marking decisions.
    dribble_speed : float, default=3.0
        Dribbling speed when defenders carry the ball.
    fullback_min_width : float, default=8.0
        Minimum lateral width maintained by fullbacks.
    centreback_shift_factor : float, default=0.15
        Rate at which centre-backs shift laterally toward the ball.
    centreback_max_width : float, default=12.0
        Maximum lateral spread for centre-backs.
    """

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
    """Midfielder-specific heuristics for pressing, support, and relief runs.

    Parameters
    ----------
    press_stamina_threshold : float, default=25.0
        Minimum stamina required to initiate a press.
    pressure_radius : float, default=4.0
        Radius used to determine whether a midfielder is under pressure.
    pressure_dribble_threshold : int, default=60
        Minimum dribbling attribute for confident pressured dribbles.
    retreat_speed : float, default=2.0
        Backpedal speed when shielding the ball.
    dribble_speed_base : float, default=3.0
        Baseline dribble speed.
    dribble_speed_attr_scale : float, default=2.0
        Attribute-derived speed scaling.
    dribble_pressure_base : float, default=2.0
        Dribble speed when under pressure.
    dribble_pressure_attr_scale : float, default=2.0
        Attribute scaling for pressured dribbling.
    relief_min_distance : float, default=3.0
        Minimum pass distance considered for relief options.
    relief_max_distance : float, default=28.0
        Maximum relief pass distance.
    relief_lane_weight : float, default=0.4
        Weight applied to passing lane quality in relief scoring.
    relief_space_weight : float, default=0.3
        Weight applied to available space around the target.
    relief_distance_weight : float, default=0.1
        Weight applied to pass distance for relief passes.
    relief_progress_bonus : float, default=0.2
        Bonus applied when the relief pass advances play.
    relief_score_threshold : float, default=0.25
        Minimum score required to attempt a relief pass.
    relief_space_divisor : float, default=6.0
        Divisor controlling how space maps to a 0-1 score.
    relief_nearest_default : float, default=10.0
        Default nearest-opponent distance when none is found.
    relief_vision_base : float, default=0.7
        Base scaling factor derived from vision.
    relief_vision_scale : float, default=0.3
        Additional scaling applied from vision attributes.
    progressive_pass_vision_threshold : int, default=70
        Vision value required to force progressive passes.
    press_success_distance : float, default=1.5
        Distance threshold for successful pressing tackles.
    press_success_scale : float, default=0.5
        Scaling factor for press success probability.
    support_trail_distance : float, default=12.0
        Distance the midfielder maintains behind the ball while supporting.
    support_forward_distance : float, default=10.0
        Distance the midfielder advances ahead to support.
    support_defense_push : float, default=5.0
        Offset applied when supporting the defensive line.
    right_width : float, default=12.0
        Width target for right-sided midfielders.
    left_width : float, default=12.0
        Width target for left-sided midfielders.
    central_shift_factor : float, default=0.3
        Factor controlling how central midfielders adjust laterally.
    central_max_width : float, default=15.0
        Maximum lateral range for central midfielders.
    """

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
    """Forward logic for attacking runs, pressing, and dribbling choices.

    Parameters
    ----------
    shoot_distance_threshold : float, default=25.0
        Distance within which forwards consider shooting.
    pressure_radius : float, default=3.0
        Radius used to decide if a forward is under pressure.
    pressure_dribble_threshold : int, default=70
        Minimum dribbling ability for pressured dribbles.
    vision_progressive_threshold : int, default=70
        Vision value required to force progressive passes.
    vision_pressure_release_threshold : int, default=50
        Vision level required to find pressure-release passes.
    dribble_speed_base : float, default=3.5
        Baseline dribbling speed for forwards.
    dribble_speed_attr_scale : float, default=2.5
        Attribute scaling for dribbling speed.
    dribble_pressure_base : float, default=2.0
        Dribble speed under pressure.
    dribble_pressure_attr_scale : float, default=2.0
        Attribute scaling for pressured dribbling.
    dribble_control_offset : float, default=0.65
        Offset keeping the ball close while dribbling.
    dribble_velocity_blend : float, default=0.85
        Blend factor between player velocity and dribble direction.
    escape_angle_step : int, default=45
        Increment in degrees when sampling escape routes.
    escape_base_space : float, default=10.0
        Base spacing considered safe for escape runs.
    escape_opponent_scale : float, default=10.0
        Scaling applied per nearby opponent.
    relief_min_distance : float, default=3.0
        Minimum distance for relief passes.
    relief_max_distance : float, default=25.0
        Maximum distance for relief passes.
    relief_lane_weight : float, default=0.45
        Weight assigned to lane quality for relief passes.
    relief_space_weight : float, default=0.25
        Weight assigned to space around the target.
    relief_distance_weight : float, default=0.1
        Weight assigned to pass distance.
    relief_progress_bonus : float, default=0.2
        Bonus for passes that advance play.
    relief_support_bonus : float, default=0.05
        Bonus for passes that support teammates.
    relief_score_threshold : float, default=0.25
        Minimum relief score required to pass.
    relief_space_divisor : float, default=5.0
        Divisor mapping opponent spacing to a score.
    relief_nearest_default : float, default=10.0
        Default nearest opponent distance when unspecified.
    relief_vision_base : float, default=0.6
        Base scaling factor derived from vision.
    relief_vision_scale : float, default=0.4
        Additional scaling applied from vision attributes.
    pressing_distance : float, default=20.0
        Distance at which forwards start pressing defenders.
    run_ballcarrier_distance : float, default=30.0
        Distance that triggers support runs for the ball carrier.
    run_goal_weight : float, default=0.7
        Weight applied to goal-oriented run scoring.
    run_ball_weight : float, default=0.3
        Weight applied to ball-oriented run scoring.
    onside_margin : float, default=2.0
        Margin kept to remain onside.
    hold_position_adjustment : float, default=5.0
        Adjustment encouraging forwards to hold their lane.
    centre_adjust_factor : float, default=0.3
        Factor pulling central forwards toward the middle.
    centre_max_width : float, default=8.0
        Maximum lateral width for central forwards.
    wide_min_offset : float, default=5.0
        Minimum lateral offset for wide forwards.
    wide_max_width : float, default=15.0
        Maximum lateral range for wide forwards.
    cut_inside_factor : float, default=0.7
        Weight encouraging wide forwards to cut inside.
    """

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
    """Shot-stopping, collection, and positioning settings for goalkeepers.

    Parameters
    ----------
    save_min_ball_speed : float, default=3.0
        Minimum shot speed considered for a save attempt.
    save_forward_speed_threshold : float, default=0.3
        Forward speed threshold distinguishing rolling and driven shots.
    save_plane_buffer : float, default=0.3
        Buffer applied to the save plane around the goal line.
    save_time_horizon : float, default=1.05
        Prediction horizon for anticipated saves.
    save_post_buffer : float, default=1.4
        Buffer around the posts to avoid clipping animations.
    save_box_buffer : float, default=1.5
        Buffer for the six-yard box boundaries.
    reach_reaction_buffer : float, default=0.05
        Time buffer representing reaction delay before diving.
    reach_distance_buffer : float, default=0.35
        Extra reach distance representing goalkeeper stretch.
    success_distance : float, default=1.5
        Distance threshold for successful interventions.
    success_eta_threshold : float, default=0.25
        Time-to-arrival threshold for claiming the ball.
    log_eta_threshold : float, default=0.2
        Threshold for logging close-call saves.
    collect_speed_threshold : float, default=5.0
        Ball speed threshold to attempt catches instead of parries.
    collect_safe_distance_base : float, default=8.0
        Base distance required for safe collection.
    collect_safe_distance_attr_scale : float, default=5.0
        Attribute scaling applied to safe collection distance.
    collect_success_distance : float, default=1.5
        Distance within which a collection succeeds.
    positioning_distance_base : float, default=2.0
        Base positioning offset from the goal line.
    positioning_distance_attr_scale : float, default=2.0
        Attribute scaling for positional adjustment.
    positioning_min_offset : float, default=0.8
        Minimum lateral offset kept when centring.
    positioning_angle_factor : float, default=0.3
        Factor weighting shot angle in positioning decisions.
    positioning_max_lateral : float, default=3.0
        Maximum allowed lateral shift from goal centre.
    positioning_speed_attr : int, default=50
        Attribute baseline for movement speed adjustments.
    """

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
    """Aggregates per-role configuration blocks for quick lookup by behaviour.

    Parameters
    ----------
    shooting : ShootingConfig, default=ShootingConfig()
        Configuration used for shot selection heuristics.
    passing : PassingConfig, default=PassingConfig()
        Configuration controlling pass evaluation and power.
    intercept : InterceptConfig, default=InterceptConfig()
        Interception prediction parameters.
    receive_pass : ReceivePassConfig, default=ReceivePassConfig()
        Settings applied when receiving passes.
    loose_ball : LooseBallConfig, default=LooseBallConfig()
        Heuristics for loose ball chases.
    possession_support : PossessionSupportConfig, default=PossessionSupportConfig()
        Support positioning weights while in possession.
    lane_spacing : LaneSpacingConfig, default=LaneSpacingConfig()
        Parameters preventing lane crowding.
    defensive : DefensiveLineConfig, default=DefensiveLineConfig()
        Defensive line positioning settings.
    pressing : PressingConfig, default=PressingConfig()
        Pressing thresholds used across roles.
    space_finding : SpaceFindingConfig, default=SpaceFindingConfig()
        Parameters guiding space-finding behaviour.
    defender : DefenderConfig, default=DefenderConfig()
        Specialised configuration for defenders.
    midfielder : MidfielderConfig, default=MidfielderConfig()
        Specialised configuration for midfielders.
    forward : ForwardConfig, default=ForwardConfig()
        Specialised configuration for forwards.
    goalkeeper : GoalkeeperConfig, default=GoalkeeperConfig()
        Specialised configuration for goalkeepers.
    support_profiles : Dict[str, Tuple[float, float, float]]
        Support lane preferences mapped by role code.
    """

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
    """Top-level container for all engine tuning structures.

    Parameters
    ----------
    pitch : PitchConfig, default=PitchConfig()
        Pitch dimension configuration.
    simulation : SimulationConfig, default=SimulationConfig()
        Simulation timing parameters.
    possession : PossessionConfig, default=PossessionConfig()
        Ball possession heuristics.
    formation : FormationConfig, default=FormationConfig()
        Formation placement references.
    ball_physics : BallPhysicsConfig, default=BallPhysicsConfig()
        Ball physics tuning.
    player_movement : PlayerMovementConfig, default=PlayerMovementConfig()
        Movement and locomotion settings.
    role : RoleBehaviourConfig, default=RoleBehaviourConfig()
        Aggregated role behaviour configurations.
    """

    pitch: PitchConfig = field(default_factory=PitchConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    possession: PossessionConfig = field(default_factory=PossessionConfig)
    formation: FormationConfig = field(default_factory=FormationConfig)
    ball_physics: BallPhysicsConfig = field(default_factory=BallPhysicsConfig)
    player_movement: PlayerMovementConfig = field(default_factory=PlayerMovementConfig)
    role: RoleBehaviourConfig = field(default_factory=RoleBehaviourConfig)


ENGINE_CONFIG = EngineConfig()
"""Singleton-style access to the engine configuration."""
