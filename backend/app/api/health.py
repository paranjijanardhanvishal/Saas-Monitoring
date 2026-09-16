from fastapi import APIRouter, HTTPException
from app.database.mongodb import db_client

router = APIRouter()

@router.get("/health")
async def health_check():
    """Check application health and MongoDB connectivity."""
    db_status = "disconnected"
    try:
        # Ping the database to check connection
        if db_client.client:
            await db_client.client.admin.command('ping')
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        
    if db_status != "connected":
        raise HTTPException(status_code=503, detail={"status": "unhealthy", "database": db_status})
        
    return {"status": "ok", "database": db_status}
