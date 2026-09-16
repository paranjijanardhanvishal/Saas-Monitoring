from app.risk.schemas import RiskAssessmentRequest, RiskAssessmentModel
from app.risk.scoring import calculate_combined_risk, determine_overall_risk_category, normalize_behavioral_deviation, PRIVACY_WEIGHT, BEHAVIORAL_WEIGHT
from app.risk.factors import generate_risk_explanation
from app.database.mongodb import get_database

async def analyze_risk(request: RiskAssessmentRequest) -> RiskAssessmentModel:
    db = get_database()
    
    privacy_finding = None
    anomaly_finding = None
    
    # Retrieve Privacy Finding
    if db is not None and request.privacy_finding_id:
        privacy_finding = await db.pii_findings.find_one({"finding_id": request.privacy_finding_id})
        
    # Retrieve Behavioral Anomaly Finding
    if db is not None and request.anomaly_id:
        anomaly_finding = await db.anomalies.find_one({"anomaly_id": request.anomaly_id})
        
    is_partial = False
    
    # Extract Privacy Score
    privacy_score = 0.0
    if privacy_finding:
        privacy_score = float(privacy_finding.get("sensitivity_score", 0.0))
    else:
        is_partial = True
        
    # Extract Behavioral Score
    behavioral_score = 0.0
    if anomaly_finding:
        deviation = anomaly_finding.get("deviation", 1.0)
        behavioral_score = normalize_behavioral_deviation(deviation)
    else:
        is_partial = True
        
    # Calculate Combined Risk
    # Handle cases where one signal is missing by still using the configured weights,
    # but the missing signal contributes 0. 
    # Alternatively, we could re-weight to 1.0 for the available signal, but standardizing
    # allows partial data to inherently reflect a lower "confidence" combined score.
    # The paper's goal is a combined risk engine. We use the standard weights.
    combined_score = calculate_combined_risk(privacy_score, behavioral_score)
    risk_category = determine_overall_risk_category(combined_score)
    
    # Generate explanations
    risk_factors, explanation = generate_risk_explanation(
        privacy_score=privacy_score,
        behavioral_score=behavioral_score,
        privacy_finding=privacy_finding,
        anomaly_finding=anomaly_finding
    )
    
    assessment = RiskAssessmentModel(
        user_id=request.user_id,
        event_id=request.event_id,
        privacy_finding_id=request.privacy_finding_id,
        anomaly_id=request.anomaly_id,
        privacy_score=privacy_score,
        behavioral_score=behavioral_score,
        privacy_weight=PRIVACY_WEIGHT,
        behavioral_weight=BEHAVIORAL_WEIGHT,
        combined_score=combined_score,
        risk_category=risk_category,
        risk_factors=risk_factors,
        explanation=explanation,
        is_partial_assessment=is_partial,
        timestamp=request.timestamp
    )
    
    # Persist to database
    if db is not None:
        await db.risk_assessments.insert_one(assessment.model_dump())
        
    return assessment
