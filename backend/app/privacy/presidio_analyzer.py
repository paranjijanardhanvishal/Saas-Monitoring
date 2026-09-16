from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
import logging

logger = logging.getLogger(__name__)

# Global Analyzer Engine instance
_analyzer_engine = None

def get_analyzer() -> AnalyzerEngine:
    global _analyzer_engine
    if _analyzer_engine is None:
        logger.info("Initializing Presidio AnalyzerEngine...")
        try:
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            
            # Configure to use en_core_web_sm to save memory/download time
            configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]
            }
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            
            _analyzer_engine = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
            
            # Custom Recognizer for Indian Aadhaar (12 digits, optional spaces)
            # This is a naive regex for test purposes; in reality Aadhaar has Verhoeff checksum
            aadhaar_pattern = Pattern(
                name="aadhaar_pattern",
                regex=r"\b\d{4}\s?\d{4}\s?\d{4}\b",
                score=0.5
            )
            aadhaar_recognizer = PatternRecognizer(
                supported_entity="AADHAAR",
                patterns=[aadhaar_pattern],
                name="aadhaar_recognizer"
            )
            _analyzer_engine.registry.add_recognizer(aadhaar_recognizer)
            
            # Custom Recognizer for Passwords/Credentials (Naive for testing)
            password_pattern = Pattern(
                name="password_pattern",
                regex=r"(?i)(password|passwd|pwd)\s*[:=]\s*[^\s\.]+",
                score=0.5
            )
            password_recognizer = PatternRecognizer(
                supported_entity="PASSWORD",
                patterns=[password_pattern],
                name="password_recognizer"
            )
            _analyzer_engine.registry.add_recognizer(password_recognizer)
            
            logger.info("Presidio AnalyzerEngine initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Presidio AnalyzerEngine: {e}")
            raise
    
    return _analyzer_engine
