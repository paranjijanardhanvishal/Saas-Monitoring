from datetime import datetime, timezone
from typing import List, Optional
import uuid

from pydantic import BaseModel, Field, field_validator


class EntitySummary(BaseModel):
    entity_type: str
    sensitivity: str
    count: int


class PrivacyFindingModel(BaseModel):
    """Stored PII finding metadata.

    Raw analysed text is deliberately absent: only entity types, counts and a
    derived score are persisted.
    """

    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_id: Optional[str] = None
    event_id: Optional[str] = None
    user_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    entities: List[EntitySummary] = []

    high_count: int = 0
    moderate_count: int = 0
    low_count: int = 0

    sensitivity_score: int = 0
    category: str = "SAFE"
    engine: str = "regex"
    source: str = "manual_text"
    ocr_engine: Optional[str] = None
    file_type: Optional[str] = None
    page_count: Optional[int] = None
    text_length: int = 0


class PrivacyAnalysisRequest(BaseModel):
    """Analysed text is accepted but never echoed or persisted.

    The owning ``user_id`` is assigned by the server from the authenticated
    principal; clients cannot attribute a finding to another account.
    """

    text: str = Field(min_length=1)
    file_id: Optional[str] = Field(default=None, max_length=128)
    event_id: Optional[str] = Field(default=None, max_length=128)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text cannot be empty.")
        return value


class OCRScanResponse(BaseModel):
    finding: PrivacyFindingModel
    risk_assessment: Optional[dict] = None
    ocr_engine: str
    page_count: int
