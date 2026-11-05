"""Administrator-only controls for the isolated synthetic demonstration."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.dependencies import get_current_admin_user
from app.database.mongodb import get_database
from app.models.user import UserModel
from app.services.audit import record_audit
from app.services.demo import generate_demo_run, reset_demo_runs

router = APIRouter()


@router.get("/status")
async def demo_status(current_user: UserModel = Depends(get_current_admin_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    runs = await db.demo_runs.find({}, {"_id": 0}).sort("created_at", -1).limit(10).to_list(length=10)
    return {"enabled": True, "synthetic_only": True, "runs": runs}


@router.post("/generate", status_code=201)
async def generate_demo(request: Request, current_user: UserModel = Depends(get_current_admin_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    result = await generate_demo_run(db)
    await record_audit(db, current_user.user_id, current_user.role, "demo.generated", "demo_run", result["run_id"], "success", client_ip=request.client.host if request.client else None)
    return result


@router.delete("/reset")
async def reset_demo(request: Request, current_user: UserModel = Depends(get_current_admin_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    counts = await reset_demo_runs(db)
    await record_audit(db, current_user.user_id, current_user.role, "demo.reset", "demo_run", "synthetic", "success", client_ip=request.client.host if request.client else None, metadata=counts)
    return {"status": "reset", "deleted": counts, "synthetic_only": True}
