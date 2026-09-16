from fastapi import APIRouter, HTTPException
from typing import List
from app.privacy.schemas import PrivacyAnalysisRequest, PrivacyFindingModel
from app.privacy.service import analyze_text
from app.database.mongodb import get_database

router = APIRouter()

@router.post("/analyze", response_model=PrivacyFindingModel, status_code=201)
async def perform_privacy_analysis(request: PrivacyAnalysisRequest):
    """
    Analyzes controlled payload text, detects PII using Presidio, 
    calculates sensitivity score, and stores the finding in MongoDB.
    """
    try:
        if not request.text:
            raise ValueError("Text cannot be empty.")
        if len(request.text) > 100000:
            raise ValueError("Text exceeds maximum allowed length.")
            
        finding = await analyze_text(request)
        return finding
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.get("/findings", response_model=List[PrivacyFindingModel])
async def get_privacy_findings(limit: int = 50, skip: int = 0):
    """Retrieves stored privacy findings."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    cursor = db.pii_findings.find().sort("timestamp", -1).skip(skip).limit(limit)
    findings = await cursor.to_list(length=limit)
    return findings

@router.get("/findings/{finding_id}", response_model=PrivacyFindingModel)
async def get_privacy_finding(finding_id: str):
    """Retrieves a specific privacy finding by ID."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    finding = await db.pii_findings.find_one({"finding_id": finding_id})
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding
