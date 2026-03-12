"""
app/services/municipal_api_service.py - Municipal API Integration Service
"""
import os
import httpx
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

class MunicipalAPIService:
    def __init__(self):
        self.base_url = os.getenv("BASE_API_URL", "http://localhost:8000/api")
        self.http_client = None
    
    async def initialize(self):
        """Initialize HTTP client"""
        if not self.http_client:
            self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def cleanup(self):
        """Cleanup HTTP client"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
    
    # ==================== AUTHENTICATION FUNCTIONS ====================
    
    async def set_token(self, session, token: str) -> Dict[str, Any]:
        """Set JWT token for API authentication"""
        session.auth_token = token
        return {"success": True, "message": "Token set successfully"}
    
    async def send_otp(self, session, mobile: str) -> Dict[str, Any]:
        """Send OTP to mobile number"""
        try:
            await self.initialize()
            response = await self.http_client.post(
                f"{self.base_url}/auth/send-otp",
                params={"mobile": mobile}
            )
            if response.status_code == 200:
                session.pending_mobile = mobile
                session.auth_step = "NEED_OTP"
                return {"success": True, "message": "OTP sent successfully", "mobile": mobile}
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                return {"success": False, "error": error_data.get("detail", "Failed to send OTP")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def verify_otp(self, session, mobile: str, otp: str) -> Dict[str, Any]:
        """Verify OTP and get authentication token"""
        try:
            await self.initialize()
            response = await self.http_client.post(
                f"{self.base_url}/auth/verify-otp",
                params={"mobile": mobile, "otp": otp}
            )
            if response.status_code == 200:
                data = response.json()
                session.set_authenticated(data["token"], data["user"])
                return {
                    "success": True,
                    "message": "OTP verified successfully",
                    "token": data["token"],
                    "user": data["user"]
                }
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                return {"success": False, "error": error_data.get("detail", "Invalid OTP")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def auto_authenticate_by_mobile(self, session, mobile: str) -> Dict[str, Any]:
        """Auto-authenticate user by mobile number (for voice calls only)"""
        try:
            await self.initialize()
            
            # Try to get user by mobile number directly
            response = await self.http_client.get(
                f"{self.base_url}/users/by-mobile/{mobile}"
            )
            
            if response.status_code == 200:
                user_data = response.json()
                user = user_data["user"]
                
                # Create a temporary token for voice call authentication
                # In production, you'd want a proper voice-auth endpoint
                token_response = await self.http_client.post(
                    f"{self.base_url}/auth/voice-auth",
                    json={"mobile": mobile, "platform": session.platform}
                )
                
                if token_response.status_code == 200:
                    token_data = token_response.json()
                    return {
                        "success": True,
                        "message": "Auto-authenticated successfully",
                        "token": token_data["token"],
                        "user": user
                    }
            
            # If user doesn't exist, create a minimal voice profile
            create_response = await self.http_client.post(
                f"{self.base_url}/auth/create-voice-user",
                json={
                    "mobile": mobile,
                    "platform": session.platform,
                    "name": f"Voice User {mobile[-4:]}"
                }
            )
            
            if create_response.status_code == 201:
                create_data = create_response.json()
                return {
                    "success": True,
                    "message": "New voice user created and authenticated",
                    "token": create_data["token"],
                    "user": create_data["user"]
                }
            
            return {"success": False, "error": "Could not authenticate voice user"}
            
        except Exception as e:
            print(f"❌ Auto-auth error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ==================== COMPLAINT/GRIEVANCE FUNCTIONS ====================
    
    async def register_complaint(self, session, category: str, title: str, description: str, location: str, address: str) -> Dict[str, Any]:
        """Register a new grievance/complaint"""
        if not session.is_authenticated:
            return {"success": False, "error": "Authentication required. Please login first."}
        
        try:
            await self.initialize()
            headers = {"Authorization": f"Bearer {session.auth_token}"}
            payload = {
                "title": title,
                "description": description,
                "category": category,
                "priority": "medium",
                "location": location,
                "address": address,
                "landmark": "",
                "ward_number": "1",
                "pin_code": "462001",
                "contact_person": "",
                "alternate_mobile": "",
                "anonymous": False
            }
            
            response = await self.http_client.post(
                f"{self.base_url}/grievances/create",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 201:
                data = response.json()
                return {
                    "success": True,
                    "message": "Complaint registered successfully",
                    "grievance_id": data["grievance"]["grievance_id"],
                    "status": data["grievance"]["status"]
                }
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                return {"success": False, "error": error_data.get("detail", "Failed to register complaint")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_complaint_status(self, session, grievance_id: str) -> Dict[str, Any]:
        """Get status of a specific complaint"""
        try:
            await self.initialize()
            response = await self.http_client.get(f"{self.base_url}/grievances/track/{grievance_id}")
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "grievance": data["grievance"]
                }
            else:
                return {"success": False, "error": "Complaint not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def track_complaint(self, session, grievance_id: str) -> Dict[str, Any]:
        """Track complaint status (alias for get_complaint_status)"""
        return await self.get_complaint_status(session, grievance_id)
    
    # ==================== USER PROFILE FUNCTIONS ====================
    
    async def get_user_profile(self, session) -> Dict[str, Any]:
        """Get current user profile"""
        if not session.is_authenticated:
            return {"success": False, "error": "Authentication required"}
        
        try:
            await self.initialize()
            headers = {"Authorization": f"Bearer {session.auth_token}"}
            response = await self.http_client.get(f"{self.base_url}/users/me", headers=headers)
            if response.status_code == 200:
                return {"success": True, "user": response.json()["user"]}
            else:
                return {"success": False, "error": "Failed to get profile"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def update_profile(self, session, name: str = None, email: str = None, age: int = None) -> Dict[str, Any]:
        """Update user profile"""
        if not session.is_authenticated:
            return {"success": False, "error": "Authentication required"}
        
        try:
            await self.initialize()
            headers = {"Authorization": f"Bearer {session.auth_token}"}
            payload = {}
            if name: payload["name"] = name
            if email: payload["email"] = email
            if age: payload["age"] = age
            
            response = await self.http_client.put(f"{self.base_url}/users/update-profile", json=payload, headers=headers)
            if response.status_code == 200:
                return {"success": True, "message": "Profile updated successfully"}
            else:
                return {"success": False, "error": "Failed to update profile"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ==================== INFORMATION FUNCTIONS ====================
    
    async def get_grievance_categories(self, session) -> Dict[str, Any]:
        """Get all available grievance categories"""
        try:
            await self.initialize()
            print(f"🔗 Making API call to: {self.base_url}/grievances/categories")
            response = await self.http_client.get(f"{self.base_url}/grievances/categories")
            print(f"📡 API Response Status: {response.status_code}")
            print(f"📄 API Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True, 
                    "categories": data.get("categories", []),
                    "message": "Categories retrieved successfully"
                }
            else:
                return {
                    "success": False, 
                    "error": f"API returned status {response.status_code}: {response.text}",
                    "categories": []
                }
        except Exception as e:
            print(f"❌ Error in get_grievance_categories: {str(e)}")
            return {
                "success": False, 
                "error": f"Failed to connect to API: {str(e)}",
                "categories": []
            }
    
    async def get_awareness_info(self, session, topic: str) -> Dict[str, Any]:
        """Get awareness information (RAG would go here)"""
        # This is where you'd implement RAG for municipal awareness content
        awareness_data = {
            "health": "Municipal health services include free vaccination drives, health checkups, and awareness programs about hygiene.",
            "vaccination": "Free vaccination drives are conducted every month at community centers. No appointment needed.",
            "cleanliness": "Swachh Bharat Mission promotes cleanliness. Report garbage issues through our complaint system.",
            "water": "Municipal water supply is available 24/7. Report leakages or quality issues immediately.",
            "default": "For more information about municipal services, you can register complaints, check status, or contact our helpline."
        }
        
        info = awareness_data.get(topic.lower(), awareness_data["default"])
        return {"success": True, "information": info, "topic": topic}

# Global instance
municipal_api_service = MunicipalAPIService()

def get_municipal_api_service() -> MunicipalAPIService:
    """Get the global municipal API service instance"""
    return municipal_api_service