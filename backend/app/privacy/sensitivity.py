HIGH_SENSITIVITY_ENTITIES = [
    "CREDIT_CARD",
    "AADHAAR",
    "PASSWORD",
    "US_SSN",
    "CRYPTO",
    "IBAN_CODE",
    "US_BANK_NUMBER"
]

MODERATE_SENSITIVITY_ENTITIES = [
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "UK_NHS"
]

LOW_SENSITIVITY_ENTITIES = [
    "PERSON",
    "IP_ADDRESS",
    "DATE_TIME",
    "LOCATION",
    "NRP", # Nationality, religious or political group
    "MEDICAL_LICENSE",
    "URL"
]

def classify_entity_sensitivity(entity_type: str) -> str:
    """Returns HIGH, MODERATE, LOW or UNKNOWN based on entity type."""
    if entity_type in HIGH_SENSITIVITY_ENTITIES:
        return "HIGH"
    if entity_type in MODERATE_SENSITIVITY_ENTITIES:
        return "MODERATE"
    if entity_type in LOW_SENSITIVITY_ENTITIES:
        return "LOW"
    return "UNKNOWN"

def calculate_sensitivity_score(high_count: int, moderate_count: int, low_count: int) -> int:
    """Calculates S = min(10H + 5M + 1L, 100)"""
    score = (10 * high_count) + (5 * moderate_count) + (1 * low_count)
    return min(score, 100)

def determine_risk_category(score: int) -> str:
    """
    Safe: S < 20
    Sensitive: 20 <= S < 60
    High-Risk: S >= 60
    """
    if score < 20:
        return "SAFE"
    elif score < 60:
        return "SENSITIVE"
    else:
        return "HIGH_RISK"
