"""
STLT Utility Functions
======================
Energy computation and constraint checking utilities for the
on-board adaptive selection algorithm.
"""

import math
from dataclasses import dataclass
from typing import Optional


# ==============================================================================
# GLOBAL CONSTANTS
# ==============================================================================

GAMMA = 0.0    # Switched capacitance constant [F]
F = 0.0        # CPU frequency [Hz]
ALPHA = 0.0    # Computational throughput [FLOPs/cycle]
BETA = 0.0     # Transmission energy coefficient [J/bit]
T_COMP = 0.0   # Computation phase duration [s]
T_COMM = 0.0   # Communication phase duration [s]
R_MAX = 0.0    # Maximum data rate [bits/s]
P_SUN = 0.0    # Direct solar power [W]
E_MAX = 0.0    # Maximum battery energy [J]


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class SplitPoint:
    """Candidate split point from offline analyzer."""
    layer_index: int
    W: float  # Cumulative FLOPs up to layer l
    D: float  # Intermediate output size at layer l [bits]


@dataclass
class SatelliteState:
    """Current satellite state from telemetry."""
    E_current: float        # Current battery energy [J]
    t: float                # Current time in orbit [s]
    theta: float            # Solar incidence angle [radians] (legacy/diagnostic)
    # Forecasted net battery energy change (lets the algorithm "know the future" eclipse schedule).
    # This is NOT raw solar generation; it is the net battery delta (charge/discharge) from telemetry/model.
    delta_E_until_comm_j: float  # Expected net battery energy change from now until comm starts [J]
    delta_E_during_comm_j: float # Expected net battery energy change during comm window [J]
    accumulated_data: float # Accumulated intermediate data [bits]


@dataclass
class AlgorithmResult:
    """Result of the adaptive selection algorithm."""
    selected_split: Optional[SplitPoint]
    E_total: float
    feasible: bool
    reason: str


# ==============================================================================
# ENERGY FUNCTIONS
# ==============================================================================

def compute_computation_energy(W: float) -> float:
    """
    Compute on-board DNN computation energy.
    E_comp = (γ·f²/α) · W(l)
    """
    if ALPHA == 0:
        return float('inf')
    return ((GAMMA * F**2) / ALPHA) * W


def compute_communication_energy(D: float) -> float:
    """
    Compute data transmission energy.
    E_comm = β · D(l)
    """
    return BETA * D


def compute_total_energy(split: SplitPoint) -> float:
    """
    Compute total energy for a split point.
    E = E_comp + E_comm
    """
    return compute_computation_energy(split.W) + compute_communication_energy(split.D)


def compute_solar_power(theta: float) -> float:
    """
    Compute solar power based on incidence angle.
    P_solar = P_sun · cos(θ)
    """
    return P_SUN * math.cos(theta)


def compute_expected_energy(E_current: float, delta_E_until_comm_j: float, E_comp: float) -> float:
    """
    Compute expected battery energy at communication window start.
    E_expected = E_current + delta_E_until_comm - E_comp
    """
    expected = E_current + delta_E_until_comm_j - E_comp
    return min(E_MAX, expected) if E_MAX > 0 else expected


def compute_D_max() -> float:
    """
    Compute maximum transferable data during communication window.
    D_max = T_comm × R_max
    """
    return T_COMM * R_MAX


# ==============================================================================
# CONSTRAINT FUNCTIONS
# ==============================================================================

def check_computation_constraint(E_current: float, split: SplitPoint) -> bool:
    """
    Check if battery has enough energy for computation.
    E_current(t) > (γf²/α) · W(l)
    """
    return E_current > compute_computation_energy(split.W)


def check_data_volume_constraint(accumulated_data: float, split: SplitPoint, D_max: float) -> bool:
    """
    Check if total data doesn't exceed channel capacity.
    Σ D(l_i) ≤ D_max
    """
    return (accumulated_data + split.D) <= D_max


def check_transmission_constraint(
    E_expected: float,
    delta_E_during_comm_j: float,
    accumulated_data: float,
    split: SplitPoint,
) -> bool:
    """
    Check if enough energy exists to transmit accumulated data.
    E_expected + delta_E_during_comm > β · Σ D(l_i)
    """
    available_energy = E_expected + delta_E_during_comm_j
    transmission_energy = BETA * (accumulated_data + split.D)
    return available_energy > transmission_energy
