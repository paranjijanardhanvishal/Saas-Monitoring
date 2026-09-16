from fastapi import APIRouter, HTTPException
from app.database.mongodb import get_database
from app.models.incident import IncidentResponse, IncidentCreate
from typing import List
from bson import ObjectId
from datetime import datetime

router = APIRouter()

@router.get("", response_model=List[IncidentResponse])
async def get_incidents(limit: int = 50, skip: int = 0):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    cursor = db.incidents.find().sort("created_time", -1).skip(skip).limit(limit)
    incidents = []
    async for incident in cursor:
        incident["_id"] = str(incident["_id"])
        incidents.append(IncidentResponse(**incident))
    return incidents

@router.post("", status_code=201, response_model=IncidentResponse)
async def create_incident(incident: IncidentCreate):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    incident_dict = incident.dict()
    incident_dict["created_time"] = datetime.utcnow()
    incident_dict["response_history"] = ["Incident created"]
    
    result = await db.incidents.insert_one(incident_dict)
    incident_dict["_id"] = str(result.inserted_id)
    return IncidentResponse(**incident_dict)

@router.patch("/{incident_id}/status")
async def update_incident_status(incident_id: str, status: str):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        obj_id = ObjectId(incident_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid Incident ID")

    result = await db.incidents.update_one(
        {"_id": obj_id}, 
        {
            "$set": {"status": status},
            "$push": {"response_history": f"Status changed to {status}"}
        }
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Incident not found or status identical")
    return {"status": "success"}
