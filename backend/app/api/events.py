from fastapi import APIRouter, HTTPException
from app.database.mongodb import get_database
from app.models.event import EventModel
from typing import List

router = APIRouter()
from app.services.monitoring import log_event

@router.post("/events", status_code=201, response_model=dict)
async def create_event(event: EventModel):
    """Ingest a new monitoring event (used by the proxy)."""
    try:
        await log_event(event)
        return {"status": "success", "event_id": event.event_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events", response_model=List[EventModel])
async def get_events(limit: int = 50, skip: int = 0):
    """Get monitored events."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    events_cursor = db.events.find().sort("timestamp", -1).skip(skip).limit(limit)
    events = await events_cursor.to_list(length=limit)
    return events

@router.get("/events/{event_id}", response_model=EventModel)
async def get_event(event_id: str):
    """Get a specific event by ID."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
        
    event = await db.events.find_one({"event_id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
