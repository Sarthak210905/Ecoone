from typing import Dict, Any
from app.database.database import get_users_collection, get_green_credits_collection
from datetime import datetime
from bson import ObjectId


class GreenCreditService:
    def __init__(self):
        self.credit_values = {
            "complaint_filed": 5,
            "tree_plantation": 50,
            "pollution_report": 10,
            "solar_installation": 500,
            "waste_segregation": 20,
            "clothes_donation": 15,  # Added donation actions
            "goods_donation": 10
        }
    
    async def award_credits(
        self,
        user_id: ObjectId,
        action: str,
        quantity: int = 1,
        reference_id: str = None
    ) -> Dict[str, Any]:
        if action not in self.credit_values:
            return {"success": False, "error": f"Unknown action: {action}"}
        
        users_collection = get_users_collection()
        credits_collection = get_green_credits_collection()
        credits_awarded = self.credit_values[action] * quantity
        
        transaction = {
            "user_id": user_id,
            "action": action,
            "quantity": quantity,
            "credits_awarded": credits_awarded,
            "reference_id": reference_id,
            "transaction_type": "credit",
            "created_at": datetime.utcnow(),
            "status": "completed"
        }
        
        await credits_collection.insert_one(transaction)
        await users_collection.update_one(
            {"_id": user_id},
            {
                "$inc": {
                    "green_credits": credits_awarded,
                    "total_credits_earned": credits_awarded
                }
            }
        )
        user = await users_collection.find_one({"_id": user_id})
        
        return {
            "success": True,
            "action": action,
            "credits_awarded": credits_awarded,
            "user_balance": user.get("green_credits", 0) if user else 0,
            "message": f"🌱 You earned {credits_awarded} Green Credits!"
        }
    
    async def get_user_credits(self, user_id: ObjectId) -> Dict[str, Any]:
        users_collection = get_users_collection()
        credits_collection = get_green_credits_collection()
        user = await users_collection.find_one({"_id": user_id})
        if not user:
            return {"success": False, "error": "User not found"}
        transactions = await credits_collection.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(10).to_list(length=10)
        serialized_transactions = [
            {
                "action": t["action"],
                "credits": t.get("credits_awarded", t.get("credits_redeemed", 0)),
                "type": t["transaction_type"],
                "created_at": t["created_at"].isoformat()
            }
            for t in transactions
        ]
        return {
            "success": True,
            "balance": user.get("green_credits", 0),
            "total_earned": user.get("total_credits_earned", 0),
            "total_redeemed": user.get("credits_redeemed", 0),
            "transactions": serialized_transactions
        }


green_credit_service = GreenCreditService()

def get_green_credit_service() -> GreenCreditService:
    return green_credit_service

