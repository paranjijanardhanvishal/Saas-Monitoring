from typing import Dict, Any, List
from app.privacy.schemas import PrivacyAnalysisRequest, PrivacyFindingModel, EntitySummary
from app.privacy.presidio_analyzer import get_analyzer
from app.privacy.sensitivity import classify_entity_sensitivity, calculate_sensitivity_score, determine_risk_category
from app.database.mongodb import get_database

async def analyze_text(request: PrivacyAnalysisRequest) -> PrivacyFindingModel:
    """Runs privacy analysis on provided text and stores the finding."""
    analyzer = get_analyzer()
    
    # Run presidio
    # Limit entities to keep it reasonably fast, or leave empty to run all supported
    results = analyzer.analyze(text=request.text, language='en')
    
    # Aggregate entities
    entity_counts: Dict[str, int] = {}
    
    # Handle overlaps: Presidio returns overlapping entities sometimes, 
    # but basic overlapping logic requires filtering.
    # For now, we trust Presidio's output or perform a simple deduplication if needed.
    # analyzer.analyze already handles some overlapping internally if return_decision_process is false
    for result in results:
        etype = result.entity_type
        entity_counts[etype] = entity_counts.get(etype, 0) + 1
        
    high_c = 0
    mod_c = 0
    low_c = 0
    
    entity_summaries: List[EntitySummary] = []
    
    for etype, count in entity_counts.items():
        sens = classify_entity_sensitivity(etype)
        
        # Don't silently give UNKNOWN a high score. Treat it as 0 weight, but log it.
        if sens == "HIGH":
            high_c += count
        elif sens == "MODERATE":
            mod_c += count
        elif sens == "LOW":
            low_c += count
            
        entity_summaries.append(EntitySummary(
            entity_type=etype,
            sensitivity=sens,
            count=count
        ))
        
    score = calculate_sensitivity_score(high_c, mod_c, low_c)
    category = determine_risk_category(score)
    
    finding = PrivacyFindingModel(
        file_id=request.file_id,
        event_id=request.event_id,
        user_id=request.user_id,
        entities=entity_summaries,
        high_count=high_c,
        moderate_count=mod_c,
        low_count=low_c,
        sensitivity_score=score,
        category=category
    )
    
    # Persist to database
    db = get_database()
    if db is not None:
        await db.pii_findings.insert_one(finding.model_dump())
        
    return finding
