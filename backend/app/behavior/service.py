from app.behavior.schemas import BehaviorAnalysisRequest, AnomalyFindingModel, BehaviorProfileModel
from app.behavior.baseline import get_user_profile, save_user_profile, save_anomaly_finding
from app.behavior.activity_rate import calculate_activity_rate
from app.behavior.ewma import update_all_ewma_windows, initialize_ewma_windows
from app.behavior.anomaly_detector import detect_anomaly
from datetime import datetime, timezone

async def analyze_behavior(request: BehaviorAnalysisRequest) -> AnomalyFindingModel:
    user_id = request.user_id
    current_time = request.timestamp
    
    def get_utc_timestamp(dt: datetime) -> float:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc).timestamp()
        return dt.timestamp()
        
    current_ts = get_utc_timestamp(current_time)
    
    # 1. Load baseline
    profile = await get_user_profile(user_id)
    
    if profile:
        # 2. Calculate rate
        previous_ts = get_utc_timestamp(profile.last_activity_timestamp)
        current_rate = calculate_activity_rate(current_ts, previous_ts)
        
        # 3. Update EWMA
        new_ewma = update_all_ewma_windows(current_rate, profile.ewma)
    else:
        # Cold start
        # Use an initial rate of 1.0 (or something reasonable) since there's no previous event
        current_rate = 1.0
        new_ewma = initialize_ewma_windows(current_rate)
        profile = BehaviorProfileModel(
            user_id=user_id,
            last_activity_timestamp=current_time,
            ewma=new_ewma
        )
        
    # 4. Detect anomaly
    finding = detect_anomaly(
        user_id=user_id,
        event_id=request.event_id,
        timestamp=current_time,
        current_rate=current_rate,
        ewma_dict=profile.ewma # compare against previous EWMA baseline before updating
    )
    
    # 5. Save updated baseline
    profile.last_activity_timestamp = current_time
    profile.ewma = new_ewma
    profile.updated_at = datetime.now(timezone.utc)
    await save_user_profile(profile)
    
    # 6. Save finding if it is an anomaly (or always save to track history as per paper)
    await save_anomaly_finding(finding)
    
    return finding
