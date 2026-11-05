"""Enforcement execution.

Unlike the original prototype, no action is described as successful until the
database mutation has actually happened. Active actions (restricting an account
or revoking devices) require an explicit administrative confirmation.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.database.mongodb import get_database
from app.enforcement.policy import (
    determine_response_action,
    generate_response_reason,
    requires_confirmation,
)
from app.enforcement.schemas import (
    ActionTypeEnum,
    EnforcementRequest,
    EnforcementResponseModel,
    ResponseStatusEnum,
)
from app.services.alerts import create_alert
from app.services.devices import revoke_all_user_devices

logger = logging.getLogger(__name__)

ACTIVE_ACTIONS = {ActionTypeEnum.RESTRICT_USER, ActionTypeEnum.REVOKE_DEVICES}


class EnforcementNotFound(ValueError):
    pass


class EnforcementConflict(ValueError):
    pass


class EnforcementConfirmationRequired(ValueError):
    pass


async def _notify_integrations(risk: dict, response: dict) -> dict:
    """Send optional Slack/Jira notifications; report skipped integrations."""
    results: dict = {}
    try:
        from app.integrations.alerts import create_jira_ticket, send_slack_alert
    except ImportError:
        return {"slack": "unavailable", "jira": "unavailable"}

    try:
        results["slack"] = send_slack_alert(risk, response)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Slack notification failed: %s", exc)
        results["slack"] = "failed"
    try:
        results["jira"] = create_jira_ticket(risk, response)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Jira notification failed: %s", exc)
        results["jira"] = "failed"
    return results


async def execute_response(
    payload: EnforcementRequest, actor_id: str
) -> EnforcementResponseModel:
    db = get_database()
    if db is None:
        raise EnforcementNotFound("Database connection failed")

    risk = await db.risk_assessments.find_one({"risk_id": payload.risk_id})
    if not risk:
        raise EnforcementNotFound(f"Risk assessment {payload.risk_id} not found")

    existing = await db.enforcement_responses.find_one({"risk_id": payload.risk_id})
    if existing:
        model = EnforcementResponseModel(**existing)
        model.response_status = ResponseStatusEnum.ALREADY_HANDLED
        return model

    action = payload.action or determine_response_action(risk.get("risk_category", "LOW"))
    if requires_confirmation(action) and not payload.confirm:
        raise EnforcementConfirmationRequired(
            f"{action.value} changes account or device state and requires confirm=true"
        )

    user_id = risk.get("user_id")
    if not user_id:
        raise EnforcementNotFound("Risk assessment has no associated user")
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise EnforcementNotFound("Risk assessment user no longer exists")

    previous_status = user.get("enforcement_status", "ACTIVE")
    resulting_status = previous_status
    revoked_devices = 0
    targets: list[str] = []
    now = datetime.now(timezone.utc)

    try:
        if action == ActionTypeEnum.RESTRICT_USER:
            await db.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "enforcement_status": "RESTRICTED",
                        "enforcement_updated_at": now,
                        "enforcement_reason": payload.reason
                        or f"Administrative action for {risk.get('risk_category')} risk",
                    }
                },
            )
            revoked_devices = await revoke_all_user_devices(
                db, user_id, "Account restricted by administrator"
            )
            resulting_status = "RESTRICTED"
            targets.append(f"user:{user_id}")
            active = await db.devices.find(
                {"user_id": user_id, "status": "REVOKED", "revoked_at": {"$gte": now}}
            ).to_list(length=100)
            targets.extend(f"device:{device['device_id']}" for device in active)
        elif action == ActionTypeEnum.REVOKE_DEVICES:
            device_ids = [
                device["device_id"]
                for device in await db.devices.find(
                    {"user_id": user_id, "status": "ACTIVE"}
                ).to_list(length=100)
            ]
            revoked_devices = await revoke_all_user_devices(
                db, user_id, "Device enrollment revoked by administrator"
            )
            targets.extend(f"device:{device_id}" for device_id in device_ids)
        elif action == ActionTypeEnum.ALERT:
            await create_alert(
                db,
                severity="MEDIUM",
                title="Administrator review requested",
                reason=payload.reason
                or generate_response_reason(action, risk.get("risk_category", "MEDIUM")),
                user_id=user_id,
                event_id=risk.get("event_id"),
                risk_id=payload.risk_id,
                risk_score=risk.get("combined_score"),
                source="enforcement",
                dedupe_scope=f"enforcement-{payload.risk_id}",
            )
        elif action == ActionTypeEnum.WARN:
            await create_alert(
                db,
                severity="HIGH",
                title="High-risk activity requires administrative action",
                reason=payload.reason
                or generate_response_reason(action, risk.get("risk_category", "HIGH")),
                user_id=user_id,
                event_id=risk.get("event_id"),
                risk_id=payload.risk_id,
                risk_score=risk.get("combined_score"),
                source="enforcement",
                dedupe_scope=f"enforcement-{payload.risk_id}",
            )
    except Exception:
        logger.exception("Enforcement action %s failed for risk %s", action, payload.risk_id)
        failed = EnforcementResponseModel(
            risk_id=payload.risk_id,
            user_id=user_id,
            event_id=risk.get("event_id"),
            risk_category=risk.get("risk_category", "UNKNOWN"),
            action_taken=action,
            response_status=ResponseStatusEnum.FAILED,
            reason=payload.reason or "Enforcement action failed",
            actor_id=actor_id,
            confirmed=payload.confirm,
            previous_enforcement_status=previous_status,
            resulting_enforcement_status=previous_status,
        )
        failed_document = failed.model_dump()
        failed_document["action_taken"] = failed.action_taken.value
        failed_document["response_status"] = failed.response_status.value
        await db.enforcement_responses.insert_one(failed_document)
        raise

    reason = payload.reason or generate_response_reason(
        action, risk.get("risk_category", "UNKNOWN")
    )
    model = EnforcementResponseModel(
        risk_id=payload.risk_id,
        user_id=user_id,
        event_id=risk.get("event_id"),
        risk_category=risk.get("risk_category", "UNKNOWN"),
        action_taken=action,
        response_status=ResponseStatusEnum.EXECUTED,
        reason=reason,
        actor_id=actor_id,
        confirmed=payload.confirm,
        previous_enforcement_status=previous_status,
        resulting_enforcement_status=resulting_status,
        revoked_devices=revoked_devices,
        targets=targets,
        timestamp=now,
    )
    document = model.model_dump()
    document["action_taken"] = action.value
    document["response_status"] = ResponseStatusEnum.EXECUTED.value
    if action in {ActionTypeEnum.WARN, ActionTypeEnum.RESTRICT_USER}:
        document["integration_results"] = await _notify_integrations(risk, document)
        model.integration_results = document["integration_results"]

    await db.enforcement_responses.insert_one(document)
    return model


async def rollback_response(
    response_id: str, actor_id: str, reason: str
) -> EnforcementResponseModel:
    db = get_database()
    if db is None:
        raise EnforcementNotFound("Database connection failed")

    response = await db.enforcement_responses.find_one({"response_id": response_id})
    if not response:
        raise EnforcementNotFound("Enforcement response not found")
    if response.get("response_status") == ResponseStatusEnum.ROLLED_BACK.value:
        raise EnforcementConflict("This response has already been rolled back")
    if response.get("action_taken") not in {a.value for a in ACTIVE_ACTIONS}:
        raise EnforcementConflict("Only account or device actions can be rolled back")

    now = datetime.now(timezone.utc)
    user_id = response.get("user_id")
    if response["action_taken"] == ActionTypeEnum.RESTRICT_USER.value:
        # Restore the account only when no other un-rolled-back restriction
        # remains for this user.
        other = await db.enforcement_responses.find_one(
            {
                "user_id": user_id,
                "action_taken": ActionTypeEnum.RESTRICT_USER.value,
                "response_status": ResponseStatusEnum.EXECUTED.value,
                "response_id": {"$ne": response_id},
            }
        )
        if not other:
            await db.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "enforcement_status": "ACTIVE",
                        "enforcement_updated_at": now,
                        "enforcement_reason": f"Restriction rolled back: {reason}",
                    }
                },
            )

    await db.enforcement_responses.update_one(
        {"response_id": response_id},
        {
            "$set": {
                "response_status": ResponseStatusEnum.ROLLED_BACK.value,
                "rolled_back_at": now,
                "rollback_by": actor_id,
                "rollback_reason": reason,
                "resulting_enforcement_status": "ACTIVE",
            }
        },
    )
    updated = await db.enforcement_responses.find_one({"response_id": response_id})
    return EnforcementResponseModel(**updated)
