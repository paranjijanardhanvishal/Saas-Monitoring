"""Administrator-confirmed enforcement policy.

The mapping is a documented prototype policy, not an automated decision:
every active response must be explicitly requested and confirmed by an
administrator. Recommended actions are advisory only.
"""

from app.enforcement.schemas import ActionTypeEnum

ENFORCEMENT_POLICY = {
    "LOW": ActionTypeEnum.LOG,
    "MEDIUM": ActionTypeEnum.ALERT,
    "HIGH": ActionTypeEnum.WARN,
    "CRITICAL": ActionTypeEnum.RESTRICT_USER,
}


def determine_response_action(risk_category: str) -> ActionTypeEnum:
    return ENFORCEMENT_POLICY.get((risk_category or "").upper(), ActionTypeEnum.LOG)


def requires_confirmation(action: ActionTypeEnum) -> bool:
    return action in {ActionTypeEnum.RESTRICT_USER, ActionTypeEnum.REVOKE_DEVICES}


def generate_response_reason(action: ActionTypeEnum, risk_category: str) -> str:
    if action == ActionTypeEnum.LOG:
        return f"Event recorded. No active enforcement required for {risk_category} risk."
    if action == ActionTypeEnum.ALERT:
        return f"Security alert generated for {risk_category} risk event."
    if action == ActionTypeEnum.WARN:
        return f"Administrator warning raised for {risk_category} risk event."
    if action == ActionTypeEnum.RESTRICT_USER:
        return (
            f"Account restricted by administrator for {risk_category} risk. "
            "Active endpoint enrollments were revoked."
        )
    if action == ActionTypeEnum.REVOKE_DEVICES:
        return f"Active endpoint enrollments revoked by administrator for {risk_category} risk."
    return "Action applied."
