from fastapi import APIRouter, HTTPException
from typing import List
from app.behavior.schemas import BehaviorAnalysisRequest, AnomalyFindingModel, BehaviorProfileModel
from app.behavior.service import analyze_behavior
from app.database.mongodb import get_database

router = APIRouter()

@router.post("/analyze", response_model=AnomalyFindingModel, status_code=201)
async def perform_behavior_analysis(request: BehaviorAnalysisRequest):
    """
    Analyzes an event for behavioral anomalies using EWMA baselines.
    """
    try:
        if not request.user_id:
            raise ValueError("user_id is required.")
        if not request.event_id:
            raise ValueError("event_id is required.")
            
        finding = await analyze_behavior(request)
        return finding
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.get("/users/{user_id}", response_model=BehaviorProfileModel)
async def get_user_behavior_profile(user_id: str):
    """Retrieves the current behavioral baseline for a user."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    profile = await db.behavior_profiles.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@router.get("/anomalies", response_model=List[AnomalyFindingModel])
async def get_anomalies(limit: int = 50, skip: int = 0):
    """Retrieves anomaly findings."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    cursor = db.anomalies.find().sort("timestamp", -1).skip(skip).limit(limit)
    findings = await cursor.to_list(length=limit)
    return findings

@router.get("/anomalies/{anomaly_id}", response_model=AnomalyFindingModel)
async def get_anomaly(anomaly_id: str):
    """Retrieves a specific anomaly by ID."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    finding = await db.anomalies.find_one({"anomaly_id": anomaly_id})
    if not finding:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return finding
