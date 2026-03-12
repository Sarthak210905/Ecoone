from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.middlewares.authMiddleware import get_current_user
from app.services.green_credit_service import get_green_credit_service
from app.database.database import get_grievances_collection
router = APIRouter()
gc_service = get_green_credit_service()

class RedeemRequest(BaseModel):
    credits: int

@router.get("/balance")
async def get_balance(current_user=Depends(get_current_user)):
    grievances_collection = get_grievances_collection()
    user_id_str = str(current_user["_id"])
    # Count total grievances for this user
    grievances_count = await grievances_collection.count_documents({"user_id": user_id_str})
    per_grievance_credit = 5  # or whatever your config is
    grievance_credits = grievances_count * per_grievance_credit
    # Optionally, add other sources of green credits
    credits_data = await gc_service.get_user_credits(current_user["_id"])
    non_grievance_credits = credits_data.get("balance", 0)
    total_credits = grievance_credits + non_grievance_credits
    return {
        "success": True,
        "total_grievances": grievances_count,
        "credits_from_grievances": grievance_credits,
        "credits_from_other_sources": non_grievance_credits,
        "total_credits": total_credits
    }


@router.post("/redeem")
async def redeem_credits(request: RedeemRequest, current_user=Depends(get_current_user)):
    # Redemption logic to be implemented, can be similar to award logic
    return {"message": "Redeem credits feature coming soon"}

