from fastapi import APIRouter, HTTPException
from typing import List
from app.risk.schemas import RiskAssessmentRequest, RiskAssessmentModel
from app.risk.service import analyze_risk
from app.database.mongodb import get_database

router = APIRouter()

@router.post("/analyze", response_model=RiskAssessmentModel, status_code=201)
async def perform_risk_assessment(request: RiskAssessmentRequest):
    """
    Analyzes combined risk based on privacy and behavioral findings.
    """
    try:
        if not request.user_id:
            raise ValueError("user_id is required.")
        if not request.event_id:
            raise ValueError("event_id is required.")
            
        assessment = await analyze_risk(request)
        return assessment
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.get("/assessments", response_model=List[RiskAssessmentModel])
async def get_risk_assessments(limit: int = 50, skip: int = 0):
    """Retrieves risk assessments."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    cursor = db.risk_assessments.find().sort("timestamp", -1).skip(skip).limit(limit)
    assessments = await cursor.to_list(length=limit)
    return assessments

@router.get("/assessments/{risk_id}", response_model=RiskAssessmentModel)
async def get_risk_assessment(risk_id: str):
    """Retrieves a specific risk assessment by ID."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    assessment = await db.risk_assessments.find_one({"risk_id": risk_id})
    if not assessment:
        raise HTTPException(status_code=404, detail="Risk assessment not found")
    return assessment

@router.get("/users/{user_id}", response_model=List[RiskAssessmentModel])
async def get_user_risk_assessments(user_id: str, limit: int = 50):
    """Retrieves risk assessments for a specific user."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    cursor = db.risk_assessments.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
    assessments = await cursor.to_list(length=limit)
    return assessments
