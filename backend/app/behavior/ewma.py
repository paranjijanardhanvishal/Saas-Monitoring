from typing import Dict

# Configuration defaults for lambda smoothing factors
# These are implementation choices as the exact values were not specified
# for each window in the paper.
LAMBDA_CONFIG = {
    "30m": 0.5,
    "1h": 0.4,
    "2h": 0.3,
    "8h": 0.2,
    "1d": 0.1,
    "7d": 0.05,
    "30d": 0.02,
    "90d": 0.01
}

def calculate_new_ewma(current_rate: float, previous_ewma: float, lambda_val: float) -> float:
    """
    Calculates EWMA_new = lambda * current_rate + (1 - lambda) * previous_ewma
    """
    return (lambda_val * current_rate) + ((1.0 - lambda_val) * previous_ewma)

def update_all_ewma_windows(current_rate: float, previous_ewma_dict: Dict[str, float]) -> Dict[str, float]:
    """
    Updates all EWMA windows using the current rate and the configured lambdas.
    """
    new_ewma = {}
    for window, lambda_val in LAMBDA_CONFIG.items():
        prev_val = previous_ewma_dict.get(window, current_rate) # Cold start uses current rate
        new_ewma[window] = calculate_new_ewma(current_rate, prev_val, lambda_val)
    return new_ewma

def initialize_ewma_windows(initial_rate: float) -> Dict[str, float]:
    """
    Initializes EWMA windows for a new user (cold start).
    """
    return {window: initial_rate for window in LAMBDA_CONFIG.keys()}
