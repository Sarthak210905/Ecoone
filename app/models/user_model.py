from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId

class User(BaseModel):
    id: Optional[ObjectId] = Field(alias="_id")
    name: str
    phone: str
    email: Optional[str] = None
    profile_photo: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None

    # New fields added for Green Credits System:
    green_credits: int = 0                    # Current green credits balance
    total_credits_earned: int = 0             # Total green credits earned over lifetime
    credits_redeemed: int = 0                  # Total credits redeemed

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True
        json_encoders = {
            ObjectId: lambda oid: str(oid),
        }
