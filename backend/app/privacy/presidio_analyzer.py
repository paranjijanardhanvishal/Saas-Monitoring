"""PII detection engines.

Two engines are supported and the active one is always reported to callers:

* ``presidio`` - Microsoft Presidio with a spaCy ``en_core_web_sm`` model,
  supplemented with custom recognizers for identifiers Presidio does not
  ship (Indian Aadhaar, inline password assignments).
* ``regex`` - a deterministic, dependency-light fallback used when Presidio
  or its language model is unavailable.

The engine is selected with ``PII_ENGINE`` (``auto``, ``presidio`` or
``regex``). ``auto`` tries Presidio first and falls back to regex. Selecting
``presidio`` explicitly raises when it cannot be initialised so an operator
does not silently believe a weaker engine is running.

Only entity types, spans and counts are returned. Raw text is never logged or
persisted by this module.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Patterns shared by the regex engine and Presidio custom recognizers.
CUSTOM_PATTERNS: Dict[str, str] = {
    "AADHAAR": r"(?<!\d)(?<!\d\s)\d{4}\s?\d{4}\s?\d{4}(?!\s?\d)",
    "PASSWORD": r"(?i)(?:password|passwd|pwd)\s*[:=]\s*[^\s,;]+",
    "CREDIT_CARD": r"(?<![\d-])\d(?:[ -]?\d){12,15}(?![\d-])",
    "EMAIL_ADDRESS": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "PHONE_NUMBER": r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}(?!\d)",
    "US_SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "IP_ADDRESS": r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
}

CUSTOM_SCORES = {
    "AADHAAR": 0.85,
    "PASSWORD": 0.9,
    "CREDIT_CARD": 0.8,
    "EMAIL_ADDRESS": 0.8,
    "PHONE_NUMBER": 0.65,
    "US_SSN": 0.85,
    "IP_ADDRESS": 0.6,
}


@dataclass(frozen=True)
class PIIEntity:
    entity_type: str
    start: int
    end: int
    score: float = 0.5


class RegexAnalyzerEngine:
    """Dependency-light detector used as a fallback."""

    engine_name = "regex"

    def __init__(self) -> None:
        self.patterns = dict(CUSTOM_PATTERNS)
        self._compiled = {name: re.compile(pattern) for name, pattern in self.patterns.items()}

    def analyze(self, text: str, language: str = "en") -> List[PIIEntity]:
        if not text:
            return []
        results: List[PIIEntity] = []
        for entity_type, compiled in self._compiled.items():
            for match in compiled.finditer(text):
                results.append(
                    PIIEntity(
                        entity_type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        score=CUSTOM_SCORES.get(entity_type, 0.5),
                    )
                )
        return _deduplicate(results)


class PresidioAnalyzerEngine:
    """Presidio engine with custom recognizers for local identifier formats."""

    engine_name = "presidio"

    def __init__(self) -> None:
        from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        provider = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }
        )
        nlp_engine = provider.create_engine()
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(nlp_engine=nlp_engine, languages=["en"])

        # Presidio does not include these identifiers by default.
        self.patterns = {}
        for entity_type in ("AADHAAR", "PASSWORD", "US_SSN", "IP_ADDRESS"):
            pattern = CUSTOM_PATTERNS[entity_type]
            self.patterns[entity_type] = pattern
            registry.add_recognizer(
                PatternRecognizer(
                    supported_entity=entity_type,
                    patterns=[Pattern(name=entity_type.lower(), regex=pattern, score=CUSTOM_SCORES[entity_type])],
                    supported_language="en",
                )
            )

        # Also keep the regex patterns available for a transparent fallback if
        # a future Presidio release fails at request time.
        self.patterns.update(
            {name: pattern for name, pattern in CUSTOM_PATTERNS.items() if name not in self.patterns}
        )
        self._engine = AnalyzerEngine(
            nlp_engine=nlp_engine, registry=registry, supported_languages=["en"]
        )
        self._fallback = RegexAnalyzerEngine()

    def analyze(self, text: str, language: str = "en") -> List[PIIEntity]:
        if not text:
            return []
        try:
            raw = self._engine.analyze(text=text, language=language)
        except Exception:
            logger.exception("Presidio analysis failed; using regex fallback for this request")
            return self._fallback.analyze(text, language)
        results = [
            PIIEntity(
                entity_type=item.entity_type,
                start=int(item.start),
                end=int(item.end),
                score=float(getattr(item, "score", 0.5)),
            )
            for item in raw
        ]
        return _deduplicate(results)


def _deduplicate(results: List[PIIEntity]) -> List[PIIEntity]:
    """Remove overlapping detections, preferring the highest-confidence span."""
    ordered = sorted(results, key=lambda item: (-item.score, item.start, item.end))
    selected: List[PIIEntity] = []
    for candidate in ordered:
        if candidate.start == candidate.end:
            continue
        if any(
            candidate.start < existing.end and existing.start < candidate.end
            for existing in selected
        ):
            continue
        selected.append(candidate)
    return sorted(selected, key=lambda item: (item.start, item.end))


_analyzer_engine = None
_analyzer_lock = threading.Lock()


def _create_engine():
    configured = (settings.PII_ENGINE or "auto").strip().lower()
    if configured == "regex":
        logger.info("PII engine configured as regex")
        return RegexAnalyzerEngine()
    if configured not in {"auto", "presidio"}:
        logger.warning("Unknown PII_ENGINE '%s'; falling back to auto", configured)
        configured = "auto"
    try:
        engine = PresidioAnalyzerEngine()
        logger.info("PII engine initialised: presidio (en_core_web_sm)")
        return engine
    except Exception as exc:
        if configured == "presidio":
            raise RuntimeError(
                "PII_ENGINE=presidio was requested but Presidio could not be initialised"
            ) from exc
        logger.warning("Presidio unavailable (%s); using regex PII fallback", exc)
        return RegexAnalyzerEngine()


def get_analyzer():
    """Return the process-wide engine instance (thread-safe, lazily built)."""
    global _analyzer_engine
    if _analyzer_engine is None:
        with _analyzer_lock:
            if _analyzer_engine is None:
                _analyzer_engine = _create_engine()
    return _analyzer_engine


def get_engine_name() -> str:
    return getattr(get_analyzer(), "engine_name", "regex")


def active_engine_name() -> Optional[str]:
    """Return the loaded engine name without initialising one."""
    if _analyzer_engine is None:
        return None
    return getattr(_analyzer_engine, "engine_name", None)


def reset_analyzer() -> None:
    """Testing helper: force engine re-selection on next use."""
    global _analyzer_engine
    with _analyzer_lock:
        _analyzer_engine = None
