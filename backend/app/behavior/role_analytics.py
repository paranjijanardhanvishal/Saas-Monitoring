"""Rule-based role context for attributed endpoint activity.

This is a transparent prototype policy, not a learned role model. It inspects
short-lived event metadata and returns category-level evidence; resource names
are never copied into the finding or its explanation.
"""

from __future__ import annotations

import re
from typing import Any


BUSINESS_ROLES = ("GENERAL", "DEVELOPER", "HR", "FINANCE")

ROLE_RESOURCE_TERMS = {
    "DEVELOPER": (
        "source code", "source", "repository", "repo", "build", "ci cd",
        "devops", "api", "package", "deployment", "software",
    ),
    "HR": (
        "human resource", "hr", "employee", "personnel", "recruit",
        "candidate", "benefit", "onboarding",
    ),
    "FINANCE": (
        "finance", "invoice", "accounting", "account", "tax", "budget",
        "billing", "payment", "expense",
    ),
}

# Payroll is used by both HR and Finance, so it is deliberately neutral.
SHARED_RESOURCE_TERMS = ("payroll", "shared", "general", "company-wide")

HIGH_IMPACT_ACTIONS = {"DELETE", "SHARE", "PERMISSION_CHANGE"}
ELEVATED_ACTIONS = {"DOWNLOAD", "UPLOAD", "MODIFY"}


def _normalized_event_context(event: dict[str, Any]) -> str:
    metadata = event.get("metadata") or {}
    application = event.get("application") or {}
    values = [
        event.get("resource_name"),
        event.get("resource_id"),
        metadata.get("resource_category"),
        metadata.get("department_category"),
        metadata.get("data_category"),
        application.get("name"),
    ]
    context = " ".join(str(value) for value in values if value)
    return re.sub(r"[^a-z0-9]+", " ", context.casefold()).strip()


def _contains_term(context: str, term: str) -> bool:
    normalized_term = re.sub(r"[^a-z0-9]+", " ", term.casefold()).strip()
    return f" {normalized_term} " in f" {context} "


def assess_role_activity(business_role: str | None, event: dict[str, Any]) -> dict[str, Any]:
    """Compare an attributed event with the prototype's business-role policy.

    The current proxy intentionally clears user identity, so its events are
    excluded unless a future verified identity mapper marks them trusted.
    """
    role = (business_role or "GENERAL").upper()
    if role not in BUSINESS_ROLES:
        role = "GENERAL"

    empty_result = {
        "business_role": role,
        "role_mismatch": False,
        "role_anomaly_score": 0.0,
        "observed_resource_categories": [],
        "role_reason": None,
    }
    if role == "GENERAL":
        return empty_result

    source = event.get("source")
    metadata = event.get("metadata") or {}
    verified_proxy = source == "saas_proxy" and metadata.get("identity_verified") is True
    if source != "endpoint_agent" and not verified_proxy:
        return empty_result

    context = _normalized_event_context(event)
    if not context or any(_contains_term(context, term) for term in SHARED_RESOURCE_TERMS):
        return empty_result

    observed = [
        candidate
        for candidate, terms in ROLE_RESOURCE_TERMS.items()
        if any(_contains_term(context, term) for term in terms)
    ]
    foreign = [candidate for candidate in observed if candidate != role]
    if not foreign:
        return empty_result

    action = str(event.get("action", "")).rsplit(".", 1)[-1].upper()
    event_type = str(event.get("event_type", "")).casefold()
    if action in HIGH_IMPACT_ACTIONS or event_type.endswith((".deleted", ".shared", ".permission_changed")):
        score = 90.0
    elif action in ELEVATED_ACTIONS or event_type.endswith((".modified", ".download_observed")):
        score = 75.0
    else:
        score = 65.0

    categories = sorted(set(foreign))
    category_names = {"DEVELOPER": "Developer", "HR": "HR", "FINANCE": "Finance"}
    role_name = category_names.get(role, "General")
    observed_labels = [category_names[item] for item in sorted(set(observed))]
    foreign_labels = ", ".join(category_names[item] for item in categories)
    reason = f"{role_name} profile activity matched a {foreign_labels} resource category."
    return {
        "business_role": role,
        "role_mismatch": True,
        "role_anomaly_score": score,
        "observed_resource_categories": observed_labels,
        "role_reason": reason,
    }
