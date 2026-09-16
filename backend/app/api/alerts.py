from fastapi import APIRouter, HTTPException
from app.database.mongodb import get_database
from app.models.alert import AlertResponse, AlertCreate
from typing import List
from bson import ObjectId

router = APIRouter()

@router.get("", response_model=List[AlertResponse])
async def get_alerts(limit: int = 50, skip: int = 0):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    cursor = db.alerts.find().sort("timestamp", -1).skip(skip).limit(limit)
    alerts = []
    async for alert in cursor:
        alert["_id"] = str(alert["_id"])
        alerts.append(AlertResponse(**alert))
    return alerts

@router.post("", status_code=201, response_model=AlertResponse)
async def create_alert(alert: AlertCreate):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    from datetime import datetime
    alert_dict = alert.dict()
    alert_dict["timestamp"] = datetime.utcnow()
    
    result = await db.alerts.insert_one(alert_dict)
    alert_dict["_id"] = str(result.inserted_id)
    return AlertResponse(**alert_dict)

@router.patch("/{alert_id}/status")
async def update_alert_status(alert_id: str, status: str):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        obj_id = ObjectId(alert_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid Alert ID")

    result = await db.alerts.update_one({"_id": obj_id}, {"$set": {"status": status}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found or status identical")
    return {"status": "success"}
