def calculate_activity_rate(current_timestamp: float, previous_timestamp: float) -> float:
    """
    Calculates the activity rate r_t = 3600 / (t_current - t_last)
    Timestamps are expected in seconds.
    The minimum elapsed time is capped at 1 second (approx 0.000278 hours)
    to prevent division by zero or infinite bursts.
    """
    elapsed_seconds = current_timestamp - previous_timestamp
    
    # Cap at 1 second minimum
    if elapsed_seconds < 1.0:
        elapsed_seconds = 1.0
        
    return 3600.0 / elapsed_seconds
