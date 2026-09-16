from app.enforcement.schemas import EnforcementRequest, EnforcementResponseModel, ResponseStatusEnum
from app.enforcement.policy import determine_response_action, generate_response_reason
from app.database.mongodb import get_database

async def execute_response(request: EnforcementRequest) -> EnforcementResponseModel:
    db = get_database()
    if db is None:
        raise ValueError("Database connection failed")
        
    # 1. Verify risk assessment exists
    risk_assessment = await db.risk_assessments.find_one({"risk_id": request.risk_id})
    if not risk_assessment:
        raise ValueError(f"Risk assessment with ID {request.risk_id} not found")
        
    # 2. Duplicate protection / Idempotency
    existing_response = await db.enforcement_responses.find_one({"risk_id": request.risk_id})
    if existing_response:
        # Return existing but mark as already handled
        response = EnforcementResponseModel(**existing_response)
        response.response_status = ResponseStatusEnum.ALREADY_HANDLED
        return response
        
    # 3. Determine policy
    risk_category = risk_assessment.get("risk_category", "LOW")
    action_to_take = determine_response_action(risk_category)
    reason = generate_response_reason(action_to_take, risk_category)
    
    # 4. Execute (Simulated execution for prototype)
    # Since this is a safe prototype, we mark active interventions as SIMULATED,
    # and passive actions (LOG, ALERT, WARN) as EXECUTED (since we successfully record/alert them).
    if action_to_take == "SIMULATED_BLOCK":
        status = ResponseStatusEnum.SIMULATED
    else:
        status = ResponseStatusEnum.EXECUTED
        
    response_model = EnforcementResponseModel(
        risk_id=request.risk_id,
        user_id=risk_assessment.get("user_id"),
        event_id=risk_assessment.get("event_id"),
        risk_category=risk_category,
        action_taken=action_to_take,
        response_status=status,
        reason=reason
    )
    
    # 5. Persist
    await db.enforcement_responses.insert_one(response_model.model_dump())
    
    # 6. Trigger Integrations (Slack/Jira)
    if risk_category in ["HIGH", "CRITICAL"]:
        try:
            from app.integrations.alerts import send_slack_alert, create_jira_ticket
            # We must pass dictionaries to the integration functions
            send_slack_alert(risk_assessment, response_model.model_dump())
            create_jira_ticket(risk_assessment, response_model.model_dump())
        except ImportError:
            pass # Integrations module might not be available in all setups
    
    return response_model
