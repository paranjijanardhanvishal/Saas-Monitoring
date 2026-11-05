from typing import Dict, List

from app.core.config import settings
from app.database.mongodb import get_database
from app.privacy.presidio_analyzer import get_analyzer, get_engine_name
from app.privacy.schemas import EntitySummary, PrivacyAnalysisRequest, PrivacyFindingModel
from app.privacy.sensitivity import (
    calculate_sensitivity_score,
    classify_entity_sensitivity,
    determine_risk_category,
)


async def analyze_text(
    request: PrivacyAnalysisRequest,
    user_id: str,
    *,
    source: str = "manual_text",
    ocr_engine: str | None = None,
    file_type: str | None = None,
    page_count: int | None = None,
) -> PrivacyFindingModel:
    """Detect PII in controlled text and persist only derived metadata.

    The caller must supply the server-assigned ``user_id``. Raw text never
    leaves this function except as transient in-memory data.
    """
    if not user_id:
        raise ValueError("An owning user is required.")
    if len(request.text) > settings.PII_MAX_TEXT_LENGTH:
        raise ValueError(
            f"Text exceeds the maximum length of {settings.PII_MAX_TEXT_LENGTH} characters."
        )

    analyzer = get_analyzer()
    results = analyzer.analyze(text=request.text, language="en")

    entity_counts: Dict[str, int] = {}
    for result in results:
        entity_counts[result.entity_type] = entity_counts.get(result.entity_type, 0) + 1

    high_count = 0
    moderate_count = 0
    low_count = 0
    entity_summaries: List[EntitySummary] = []

    for entity_type, count in sorted(entity_counts.items()):
        sensitivity = classify_entity_sensitivity(entity_type)
        if sensitivity == "HIGH":
            high_count += count
        elif sensitivity == "MODERATE":
            moderate_count += count
        elif sensitivity == "LOW":
            low_count += count
        # UNKNOWN entities are recorded but intentionally carry no score weight.
        entity_summaries.append(
            EntitySummary(entity_type=entity_type, sensitivity=sensitivity, count=count)
        )

    score = calculate_sensitivity_score(high_count, moderate_count, low_count)
    finding = PrivacyFindingModel(
        file_id=request.file_id,
        event_id=request.event_id,
        user_id=user_id,
        entities=entity_summaries,
        high_count=high_count,
        moderate_count=moderate_count,
        low_count=low_count,
        sensitivity_score=score,
        category=determine_risk_category(score),
        engine=get_engine_name(),
        source=source,
        ocr_engine=ocr_engine,
        file_type=file_type,
        page_count=page_count,
        text_length=len(request.text),
    )

    db = get_database()
    if db is not None:
        await db.pii_findings.insert_one(finding.model_dump())

    return finding
