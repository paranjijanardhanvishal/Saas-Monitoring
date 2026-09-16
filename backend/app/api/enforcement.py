from fastapi import APIRouter, HTTPException
from typing import List
from app.enforcement.schemas import EnforcementRequest, EnforcementResponseModel
from app.enforcement.service import execute_response
from app.database.mongodb import get_database

router = APIRouter()

@router.post("/respond", response_model=EnforcementResponseModel, status_code=201)
async def trigger_enforcement_response(request: EnforcementRequest):
    """
    Triggers an enforcement response based on a generated risk assessment.
    """
    try:
        if not request.risk_id:
            raise ValueError("risk_id is required.")
            
        response = await execute_response(request)
        return response
    except ValueError as ve:
        raise HTTPException(status_code=404 if "not found" in str(ve).lower() else 400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.get("/responses", response_model=List[EnforcementResponseModel])
async def get_enforcement_responses(limit: int = 50, skip: int = 0):
    """Retrieves history of enforcement responses."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    cursor = db.enforcement_responses.find().sort("timestamp", -1).skip(skip).limit(limit)
    responses = await cursor.to_list(length=limit)
    return responses

@router.get("/responses/{response_id}", response_model=EnforcementResponseModel)
async def get_enforcement_response(response_id: str):
    """Retrieves a specific enforcement response by ID."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    response = await db.enforcement_responses.find_one({"response_id": response_id})
    if not response:
        raise HTTPException(status_code=404, detail="Response not found")
    return response

@router.get("/users/{user_id}", response_model=List[EnforcementResponseModel])
async def get_user_responses(user_id: str, limit: int = 50):
    """Retrieves response history for a specific user."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    cursor = db.enforcement_responses.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
    responses = await cursor.to_list(length=limit)
    return responses
