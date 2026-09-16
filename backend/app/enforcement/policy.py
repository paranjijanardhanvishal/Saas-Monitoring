from app.enforcement.schemas import ActionTypeEnum

# The research paper describes mitigating risk but does not specify
# a rigid, exact mapping of risk categories to specific technical actions.
# This mapping is a configurable prototype implementation decision.

ENFORCEMENT_POLICY = {
    "LOW": ActionTypeEnum.LOG,
    "MEDIUM": ActionTypeEnum.ALERT,
    "HIGH": ActionTypeEnum.WARN,
    "CRITICAL": ActionTypeEnum.SIMULATED_BLOCK
}

def determine_response_action(risk_category: str) -> ActionTypeEnum:
    """
    Determines the appropriate enforcement action based on the risk category.
    Defaults to LOG if the category is unrecognized.
    """
    return ENFORCEMENT_POLICY.get(risk_category.upper(), ActionTypeEnum.LOG)

def generate_response_reason(action: ActionTypeEnum, risk_category: str) -> str:
    """
    Generates a human-readable reason for the taken action.
    """
    if action == ActionTypeEnum.LOG:
        return f"Event recorded. No active enforcement required for {risk_category} risk."
    elif action == ActionTypeEnum.ALERT:
        return f"Security alert generated for {risk_category} risk event."
    elif action == ActionTypeEnum.WARN:
        return f"High-risk warning issued to administrator for {risk_category} risk event."
    elif action == ActionTypeEnum.SIMULATED_BLOCK:
        return f"Simulated blocking action applied for {risk_category} risk event. (Prototype safe mode)"
    
    return "Action applied."
