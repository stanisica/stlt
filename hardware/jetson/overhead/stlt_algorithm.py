"""
STLT On-board Adaptive Selection Algorithm
==========================================
Selects optimal DNN split point based on current satellite telemetry.
"""

from typing import List, Tuple
from stlt_utils import (
    SplitPoint,
    SatelliteState, 
    AlgorithmResult,
    compute_computation_energy,
    compute_total_energy,
    compute_expected_energy,
    compute_D_max,
    check_computation_constraint,
    check_data_volume_constraint,
    check_transmission_constraint
)


# ==============================================================================
# MAIN ALGORITHM
# ==============================================================================

def adaptive_selection_algorithm(L_star: List[SplitPoint], state: SatelliteState) -> AlgorithmResult:
    """
    Select optimal split point from pre-computed set L* based on satellite telemetry.
    
    Steps:
        1. Preparation: Calculate D_max
        2. Basic Filtration: Filter by computation energy and data volume
        3. Adaptability: Filter by transmission feasibility
        4. Selection: Choose point minimizing total energy
    """
    D_max = compute_D_max()
    feasible_points: List[Tuple[SplitPoint, float]] = []
    
    for split in L_star:
        # Constraint 1: Battery sufficient for computation
        if not check_computation_constraint(state.E_current, split):
            continue
        
        # Constraint 2: Data volume within channel capacity    
        if not check_data_volume_constraint(state.accumulated_data, split, D_max):
            continue
        
        # Constraint 3: Transmission feasibility
        E_comp = compute_computation_energy(split.W)
        E_expected = compute_expected_energy(
            state.E_current,
            state.delta_E_until_comm_j,
            E_comp,
        )
        
        if not check_transmission_constraint(
            E_expected,
            state.delta_E_during_comm_j,
            state.accumulated_data,
            split,
        ):
            continue
        
        feasible_points.append((split, compute_total_energy(split)))
    
    if not feasible_points:
        return AlgorithmResult(
            selected_split=None,
            E_total=float('inf'),
            feasible=False,
            reason="No split point satisfies all constraints"
        )
    
    best_split, best_energy = min(feasible_points, key=lambda x: x[1])
    
    return AlgorithmResult(
        selected_split=best_split,
        E_total=best_energy,
        feasible=True,
        reason="Optimal split point found"
    )


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================

if __name__ == "__main__":
    import stlt_utils as utils
    
    # Configure constants
    utils.GAMMA = 1e-11
    utils.F = 1.5e9
    utils.ALPHA = 2.0
    utils.BETA = 3.8e-7
    utils.T_COMP = 5100.0
    utils.T_COMM = 600.0
    utils.R_MAX = 100e6
    utils.P_SUN = 40.0
    
    L_star = [
        SplitPoint(layer_index=0, W=0.0, D=50331648.0),
        SplitPoint(layer_index=44, W=1.0e9, D=3211264.0),
        SplitPoint(layer_index=88, W=2.5e9, D=1605632.0),
        SplitPoint(layer_index=182, W=4.1e9, D=32000.0),
    ]
    
    state = SatelliteState(
        E_current=100.0,
        t=1000.0,
        theta=0.5,
        delta_E_until_comm_j=0.0,
        delta_E_during_comm_j=0.0,
        accumulated_data=0.0
    )
    
    result = adaptive_selection_algorithm(L_star, state)
    
    if result.feasible:
        print(f"Selected layer: {result.selected_split.layer_index}")
        print(f"Total energy: {result.E_total:.4f} J")
    else:
        print(f"No feasible solution: {result.reason}")
