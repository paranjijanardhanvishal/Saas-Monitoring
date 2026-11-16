from app.behavior.schemas import BehaviorAnalysisRequest, AnomalyFindingModel, BehaviorProfileModel
from app.behavior.baseline import get_user_profile, save_user_profile, save_anomaly_finding
from app.behavior.activity_rate import calculate_activity_rate
from app.behavior.ewma import update_all_ewma_windows, initialize_ewma_windows
from app.behavior.anomaly_detector import detect_anomaly
from app.behavior.role_analytics import assess_role_activity
from datetime import datetime, timedelta, timezone

async def analyze_behavior(
    request: BehaviorAnalysisRequest,
    business_role: str = "GENERAL",
    event: dict | None = None,
) -> AnomalyFindingModel:
    user_id = request.user_id
    current_time = request.timestamp
    
    def get_utc_timestamp(dt: datetime) -> float:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc).timestamp()
        return dt.timestamp()

    def ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
        
    current_ts = get_utc_timestamp(current_time)
    current_dt_utc = ensure_utc(current_time)
    cutoff_5min = current_dt_utc - timedelta(minutes=5)
    
    # Identify action type from event data or request metadata
    event_data = event or {}
    action_raw = str(
        event_data.get("action")
        or event_data.get("event_type")
        or (event_data.get("metadata") or {}).get("action")
        or (request.metadata or {}).get("action")
        or ""
    ).upper()

    is_download = "DOWNLOAD" in action_raw
    is_delete = "DELETE" in action_raw or "REMOVE" in action_raw

    # 1. Load baseline
    profile = await get_user_profile(user_id)
    
    if profile:
        # Backward compatibility for legacy MongoDB documents lacking new fields
        if not hasattr(profile, "access_count"):
            profile.access_count = 0
        if not hasattr(profile, "download_count"):
            profile.download_count = 0
        if not hasattr(profile, "delete_count"):
            profile.delete_count = 0
        if not hasattr(profile, "recent_downloads") or profile.recent_downloads is None:
            profile.recent_downloads = []

        # 2. Calculate rate
        previous_ts = get_utc_timestamp(profile.last_activity_timestamp)
        current_rate = calculate_activity_rate(current_ts, previous_ts)
        
        # 3. Update EWMA
        new_ewma = update_all_ewma_windows(current_rate, profile.ewma)
    else:
        # Cold start
        # Use an initial rate of 1.0 since there's no previous event
        current_rate = 1.0
        new_ewma = initialize_ewma_windows(current_rate)
        profile = BehaviorProfileModel(
            user_id=user_id,
            last_activity_timestamp=current_time,
            ewma=new_ewma,
            access_count=0,
            download_count=0,
            delete_count=0,
            recent_downloads=[],
        )

    # 4. Filter rolling 5-minute download window and update action counters
    valid_downloads = [
        ts for ts in (profile.recent_downloads or [])
        if ensure_utc(ts) >= cutoff_5min
    ]

    if is_download:
        profile.download_count += 1
        valid_downloads.append(current_dt_utc)
    elif is_delete:
        profile.delete_count += 1
    else:
        profile.access_count += 1

    profile.recent_downloads = valid_downloads
    burst_count = len(profile.recent_downloads)
    burst_detected = burst_count > 50

    burst_info = {
        "burst_detected": burst_detected,
        "burst_count": burst_count,
    }

    # 5. Detect anomaly evaluating all 8 windows and burst state
    finding = detect_anomaly(
        user_id=user_id,
        event_id=request.event_id,
        timestamp=current_time,
        current_rate=current_rate,
        ewma_dict=profile.ewma,  # compare against previous EWMA baseline before updating
        burst_info=burst_info,
    )

    role_assessment = assess_role_activity(business_role, event or {})
    finding.business_role = role_assessment["business_role"]
    finding.role_mismatch = role_assessment["role_mismatch"]
    finding.role_anomaly_score = role_assessment["role_anomaly_score"]
    finding.observed_resource_categories = role_assessment["observed_resource_categories"]
    finding.role_reason = role_assessment["role_reason"]
    if finding.role_mismatch:
        activity_reason = finding.reason
        finding.is_anomaly = True
        if finding.anomaly_type == "DOWNLOAD_BURST":
            finding.anomaly_type = "COMPOUND_BURST"
        elif finding.anomaly_type == "ACTIVITY_SPIKE":
            finding.anomaly_type = "COMPOUND"
        else:
            finding.anomaly_type = "ROLE_ACCESS_MISMATCH"
        finding.reason = f"{activity_reason} {finding.role_reason}"
    
    # 6. Save updated baseline
    profile.last_activity_timestamp = current_time
    profile.ewma = new_ewma
    profile.updated_at = datetime.now(timezone.utc)
    await save_user_profile(profile)
    
    # 7. Save finding
    await save_anomaly_finding(finding)
    
    return finding
