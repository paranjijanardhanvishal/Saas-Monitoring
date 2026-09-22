import re
import logging

logger = logging.getLogger(__name__)

class MockResult:
    def __init__(self, entity_type: str):
        self.entity_type = entity_type

class MockAnalyzerEngine:
    def __init__(self):
        self.patterns = {
            "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
            "EMAIL_ADDRESS": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "PHONE_NUMBER": r"\b\+?\d{10,14}\b",
            "AADHAAR": r"\b\d{4}\s?\d{4}\s?\d{4}\b",
            "PASSWORD": r"(?i)(password|passwd|pwd)\s*[:=]\s*[^\s\.]+",
            "US_SSN": r"\b\d{3}-\d{2}-\d{4}\b"
        }
        
    def analyze(self, text: str, language: str):
        results = []
        if not text:
            return results
        for entity_type, pattern in self.patterns.items():
            for _ in re.finditer(pattern, text):
                results.append(MockResult(entity_type))
        return results

_analyzer_engine = None

def get_analyzer():
    global _analyzer_engine
    if _analyzer_engine is None:
        logger.info("Initializing Lightweight Mock AnalyzerEngine...")
        _analyzer_engine = MockAnalyzerEngine()
    return _analyzer_engine
