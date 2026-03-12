import os
import json
import asyncio
import httpx
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
import speech_recognition as sr
import pyttsx3
from io import BytesIO
import base64
import uuid
from datetime import datetime, timedelta
from app.database.database import init_db
from app.utils.redis_client import connect_redis, redis_client
from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router
from app.routes.grievance_routes import router as grievance_router
from app.routes.grievance_admin_routes import router as grievance_admin_router

load_dotenv()

# Configure Gemini AI
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI(title="Multi-Agent Municipal Voice Assistant", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(auth_router, prefix="/api/auth")
app.include_router(user_router, prefix="/api/users")
app.include_router(grievance_router, prefix="/api/grievances")
app.include_router(grievance_admin_router, prefix="/api/grievances")

# Base API URL for municipal services
BASE_API_URL = os.getenv("BASE_API_URL", "http://localhost:8000/api")

# Create a single HTTP client instance
http_client = httpx.AsyncClient(timeout=30.0)

# Current user session
current_session = {
    "token": None,
    "user_id": None,
    "mobile": None
}

# Cache for categories
app_cache = {
    "categories": [],
    "last_categories_fetch": None
}

# ==================== MULTI-AGENT SYSTEM ====================

class AgentRole:
    ROUTER = "router"
    ANALYZER = "analyzer"  
    FUNCTION_CALLER = "function_caller"
    RESPONSE_FORMATTER = "response_formatter"

class MultiAgentSystem:
    def __init__(self):
        self.agents = {
            AgentRole.ROUTER: self.create_router_agent(),
            AgentRole.ANALYZER: self.create_analyzer_agent(),
            AgentRole.FUNCTION_CALLER: self.create_function_caller_agent(),
            AgentRole.RESPONSE_FORMATTER: self.create_response_formatter_agent()
        }
    
    def create_router_agent(self):
        """Agent that determines user intent and routes to appropriate action"""
        system_instruction = """
You are a Router Agent for Municipal Services. Your job is to classify user intent and determine the next action.

CLASSIFY USER MESSAGES INTO THESE CATEGORIES:
1. "complaint" - User describes an issue (garbage, pothole, water, electricity, etc.)
2. "complaint_status" - User asks about complaint status or provides grievance ID
3. "authentication" - User wants to login/OTP/verify
4. "profile" - User wants to see/update profile
5. "categories" - User asks about available services/categories
6. "general_help" - General questions about municipal services

EXAMPLES:
- "There's garbage on my street" → complaint
- "Check status of complaint GR123" → complaint_status
- "I want to login" → authentication
- "What services do you offer?" → categories

RESPOND WITH ONLY:
{
  "intent": "category_name",
  "confidence": "high/medium/low",
  "extracted_info": {
    "grievance_id": "if_found",
    "mobile": "if_found",
    "issue_type": "if_clear"
  }
}
"""
        return genai.GenerativeModel("gemini-2.0-flash-lite", system_instruction=system_instruction)
    
    def create_analyzer_agent(self):
        """Agent that analyzes complaint descriptions and extracts structured data"""
        system_instruction = """
You are a Complaint Analyzer Agent. Extract structured complaint data from natural language.

ANALYZE USER COMPLAINT AND RETURN JSON:
{
  "category": "match from GARBAGE|POTHOLE|WATER_LEAKAGE|STREET_LIGHT|DRAINAGE|ELECTRICITY",
  "title": "brief title (max 50 chars)",
  "description": "detailed description",
  "location": "area/locality mentioned",
  "address": "complete address if available",
  "landmark": "nearby landmark if mentioned",  
  "priority": "LOW|MEDIUM|HIGH|CRITICAL based on urgency",
  "missing_info": ["list of critical missing information"]
}

MAPPING EXAMPLES:
- "garbage/kooda/trash" → GARBAGE
- "pothole/road damage" → POTHOLE
- "bijli/electricity/power" → ELECTRICITY
- "paani/water leak" → WATER_LEAKAGE
- "street light/batti" → STREET_LIGHT
- "drainage/sewage/nali" → DRAINAGE

If location is unclear, add "specific_address" to missing_info.
"""
        return genai.GenerativeModel("gemini-2.0-flash-lite", system_instruction=system_instruction)
    
    def create_function_caller_agent(self):
        """Agent that decides which functions to call and with what parameters"""
        system_instruction = """
You are a Function Caller Agent. You MUST call appropriate functions based on the task.

AVAILABLE FUNCTIONS:
- send_otp(mobile)
- verify_otp(mobile, otp) 
- get_grievance_categories()
- register_complaint(category, title, description, location, address, priority, landmark, ward_number, pin_code)
- get_complaint_status(grievance_id)
- get_user_profile()
- update_profile(name, email, age, gender, location)

RULES:
1. For complaint registration: ALWAYS call register_complaint() with ALL required parameters
2. For status check: ALWAYS call get_complaint_status() with grievance_id
3. For auth: ALWAYS call send_otp() or verify_otp()
4. NEVER fake function results - ALWAYS make actual calls

If user confirms complaint details, immediately call register_complaint().
"""
        
        return genai.GenerativeModel(
            "gemini-2.0-flash-lite", 
            system_instruction=system_instruction,
            tools=[{"function_declarations": self.get_function_schemas()}]
        )
    
    def create_response_formatter_agent(self):
        """Agent that formats responses in a user-friendly way"""
        system_instruction = """
You are a Response Formatter Agent. Create friendly, helpful responses for users.

GUIDELINES:
-Always response in the language the user used - if he used hinglish reply in hinglish etc.
- Be conversational and helpful
- Use emojis and formatting for clarity
- Show confidence in extracted data
- Ask for missing info politely
- Confirm actions clearly
- Keep responses concise but informative

RESPONSE TYPES:
1. Complaint Analysis: Show extracted details and ask for missing info
2. Function Results: Format API responses in user-friendly way  
3. Confirmations: Ask user to confirm before taking action
4. Errors: Explain errors helpfully and suggest alternatives
"""
        return genai.GenerativeModel("gemini-2.0-flash-lite", system_instruction=system_instruction)
    
    def get_function_schemas(self):
        """Return function schemas for the function caller agent"""
        return [
            {
                "name": "send_otp",
                "description": "Send OTP to mobile number",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mobile": {"type": "string", "description": "Mobile number with country code"}
                    },
                    "required": ["mobile"]
                }
            },
            {
                "name": "verify_otp",
                "description": "Verify OTP and authenticate user",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mobile": {"type": "string"},
                        "otp": {"type": "string"}
                    },
                    "required": ["mobile", "otp"]
                }
            },
            {
                "name": "register_complaint",
                "description": "Register a new complaint with structured data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "location": {"type": "string"},
                        "address": {"type": "string"},
                        "priority": {"type": "string"},
                        "landmark": {"type": "string"},
                        "ward_number": {"type": "string"},
                        "pin_code": {"type": "string"}
                    },
                    "required": ["category", "title", "description", "location", "address"]
                }
            },
            {
                "name": "get_complaint_status",
                "description": "Get complaint status by ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "grievance_id": {"type": "string"}
                    },
                    "required": ["grievance_id"]
                }
            },
            {
                "name": "get_grievance_categories",
                "description": "Get available complaint categories",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_user_profile",
                "description": "Get user profile",
                "parameters": {
                    "type": "object", 
                    "properties": {},
                    "required": []
                }
            }
        ]

# Create multi-agent system
multi_agent_system = MultiAgentSystem()

# ==================== CHAT SESSION MANAGEMENT ====================

chat_sessions = {}

class ChatSession:
    def __init__(self, session_id: str, user_id: str = None):
        self.session_id = session_id
        self.user_id = user_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.message_history = []
        self.context = {
            "pending_complaint": None,
            "current_step": None,
            "extracted_data": {}
        }
        
    def update_activity(self):
        self.last_activity = datetime.now()
        
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)
    
    def add_message(self, role: str, content: str):
        self.message_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        if len(self.message_history) > 20:
            self.message_history = self.message_history[-20:]

def get_or_create_chat_session(session_id: str = None, user_id: str = None) -> ChatSession:
    cleanup_expired_sessions()
    
    if session_id and session_id in chat_sessions:
        session = chat_sessions[session_id]
        session.update_activity()
        return session
    
    new_session_id = session_id or str(uuid.uuid4())
    session = ChatSession(new_session_id, user_id)
    chat_sessions[new_session_id] = session
    return session

def cleanup_expired_sessions():
    expired_sessions = [
        sid for sid, session in chat_sessions.items() 
        if session.is_expired()
    ]
    
    for sid in expired_sessions:
        del chat_sessions[sid]

# ==================== API FUNCTION IMPLEMENTATIONS ====================

async def send_otp(mobile: str) -> Dict[str, Any]:
    """Send OTP to mobile number"""
    try:
        response = await http_client.post(
            f"{BASE_API_URL}/auth/send-otp",
            params={"mobile": mobile}
        )
        if response.status_code == 200:
            current_session["mobile"] = mobile
            return {"success": True, "message": "OTP sent successfully", "mobile": mobile}
        else:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            return {"success": False, "error": error_data.get("detail", "Failed to send OTP")}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def verify_otp(mobile: str, otp: str) -> Dict[str, Any]:
    """Verify OTP and get authentication token"""
    try:
        response = await http_client.post(
            f"{BASE_API_URL}/auth/verify-otp",
            params={"mobile": mobile, "otp": otp}
        )
        if response.status_code == 200:
            data = response.json()
            current_session["token"] = data["token"]
            current_session["user_id"] = data["user"]["_id"]
            current_session["mobile"] = mobile
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

async def register_complaint(category: str, title: str, description: str, location: str, address: str, 
                           priority: str = "MEDIUM", landmark: str = "", ward_number: str = "1", 
                           pin_code: str = "462001") -> Dict[str, Any]:
    """Register a new complaint"""
    if not current_session["token"]:
        return {"success": False, "error": "Authentication required. Please login first."}
    
    try:
        headers = {"Authorization": f"Bearer {current_session['token']}"}
        payload = {
            "title": title,
            "description": description,
            "category": category.upper().replace(" ", "_"),
            "priority": priority.upper(),
            "location": location,
            "address": address,
            "landmark": landmark,
            "ward_number": ward_number,
            "pin_code": pin_code,
            "anonymous": False
        }
        
        response = await http_client.post(
            f"{BASE_API_URL}/grievances/create",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 201:
            data = response.json()
            return {
                "success": True,
                "message": "Complaint registered successfully",
                "grievance_id": data["grievance"]["grievance_id"],
                "status": data["grievance"]["status"],
                "full_response": data["grievance"]
            }
        else:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            return {"success": False, "error": error_data.get("detail", f"Failed to register complaint. Status: {response.status_code}")}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_complaint_status(grievance_id: str) -> Dict[str, Any]:
    """Get status of a complaint"""
    try:
        response = await http_client.get(f"{BASE_API_URL}/grievances/track/{grievance_id}")
        if response.status_code == 200:
            data = response.json()
            return {"success": True, "grievance": data["grievance"]}
        else:
            return {"success": False, "error": "Complaint not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_grievance_categories() -> Dict[str, Any]:
    """Get all available categories"""
    global app_cache
    
    if (app_cache["categories"] and app_cache["last_categories_fetch"] and 
        datetime.now() - app_cache["last_categories_fetch"] < timedelta(minutes=10)):
        return {
            "success": True,
            "categories": app_cache["categories"],
            "message": "Categories retrieved from cache"
        }
    
    try:
        response = await http_client.get(f"{BASE_API_URL}/grievances/categories")
        
        if response.status_code == 200:
            data = response.json()
            categories = data.get("categories", [])
            
            app_cache["categories"] = categories
            app_cache["last_categories_fetch"] = datetime.now()
            
            return {"success": True, "categories": categories}
        else:
            return {"success": False, "error": f"API returned status {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_user_profile() -> Dict[str, Any]:
    """Get user profile"""
    if not current_session["token"]:
        return {"success": False, "error": "Authentication required"}
    
    try:
        headers = {"Authorization": f"Bearer {current_session['token']}"}
        response = await http_client.get(f"{BASE_API_URL}/users/me", headers=headers)
        if response.status_code == 200:
            data = response.json()
            return {"success": True, "user": data["user"]}
        else:
            return {"success": False, "error": "Failed to get profile"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Function mapping for the function caller agent
function_map = {
    "send_otp": send_otp,
    "verify_otp": verify_otp,
    "register_complaint": register_complaint,
    "get_complaint_status": get_complaint_status,
    "get_grievance_categories": get_grievance_categories,
    "get_user_profile": get_user_profile
}

# ==================== MULTI-AGENT PROCESSING ====================

async def process_with_multi_agents(user_message: str, session: ChatSession) -> str:
    """Process user message through multi-agent system"""
    
    try:
        # Step 1: Route the user intent
        print("🎯 Step 1: Routing user intent...")
        router_response = multi_agent_system.agents[AgentRole.ROUTER].generate_content(
            f"Classify this user message: '{user_message}'"
        )
        
        try:
            routing_result = json.loads(router_response.text.strip())
            print(f"📋 Routing result: {routing_result}")
        except json.JSONDecodeError:
            print(f"⚠️ Router response parsing failed: {router_response.text}")
            return "I'm having trouble understanding your request. Could you please rephrase it?"
        
        intent = routing_result.get("intent", "general_help")
        
        # Step 2: Handle based on intent
        if intent == "complaint":
            return await handle_complaint_flow(user_message, session, routing_result)
        elif intent == "complaint_status":
            return await handle_status_check(user_message, session, routing_result)
        elif intent == "authentication":
            return await handle_authentication(user_message, session, routing_result)
        elif intent == "categories":
            return await handle_categories_request(session)
        else:
            return await handle_general_help(user_message, session)
            
    except Exception as e:
        print(f"❌ Multi-agent processing error: {str(e)}")
        return "I encountered an error processing your request. Please try again."

async def handle_complaint_flow(user_message: str, session: ChatSession, routing_result: dict) -> str:
    """Handle complaint registration flow"""
    
    # Check if user is confirming a pending complaint
    if session.context.get("pending_complaint") and any(word in user_message.lower() for word in ["yes", "confirm", "register", "submit"]):
        return await register_pending_complaint(session)
    
    # Step 2: Analyze the complaint
    print("🔍 Step 2: Analyzing complaint...")
    analyzer_response = multi_agent_system.agents[AgentRole.ANALYZER].generate_content(
        f"Analyze this complaint: '{user_message}'"
    )
    
    try:
        analyzed_data = json.loads(analyzer_response.text.strip())
        print(f"📊 Analysis result: {analyzed_data}")
    except json.JSONDecodeError:
        print(f"⚠️ Analyzer response parsing failed: {analyzer_response.text}")
        return "I couldn't analyze your complaint properly. Could you describe the issue again?"
    
    # Store analyzed data in session
    session.context["pending_complaint"] = analyzed_data
    session.context["current_step"] = "awaiting_confirmation"
    
    # Step 3: Format response asking for confirmation
    print("💬 Step 3: Formatting confirmation response...")
    formatter_prompt = f"""
Format a user-friendly response showing the analyzed complaint details and asking for confirmation.

Analyzed Data: {json.dumps(analyzed_data, indent=2)}
Missing Info: {analyzed_data.get('missing_info', [])}

If missing critical info, ask for it. Otherwise, ask for confirmation to register.
"""
    
    formatter_response = multi_agent_system.agents[AgentRole.RESPONSE_FORMATTER].generate_content(formatter_prompt)
    return formatter_response.text

async def register_pending_complaint(session: ChatSession) -> str:
    """Register the pending complaint using function caller agent"""
    
    if not session.context.get("pending_complaint"):
        return "No pending complaint found. Please describe your issue first."
    
    complaint_data = session.context["pending_complaint"]
    
    # Check if user is authenticated
    if not current_session["token"]:
        return "Please login first to register complaints. Would you like me to send an OTP to your mobile number?"
    
    print("📞 Step: Calling function to register complaint...")
    
    # Use function caller agent to make the API call
    function_prompt = f"""
Register this complaint using the register_complaint function:

Complaint Data: {json.dumps(complaint_data, indent=2)}

IMPORTANT: You MUST call the register_complaint function with these parameters:
- category: {complaint_data.get('category', 'GENERAL')}
- title: {complaint_data.get('title', 'Municipal Issue')}
- description: {complaint_data.get('description', 'Issue reported by citizen')}
- location: {complaint_data.get('location', 'Not specified')}
- address: {complaint_data.get('address', complaint_data.get('location', 'Not specified'))}
- priority: {complaint_data.get('priority', 'MEDIUM')}
- landmark: {complaint_data.get('landmark', '')}
- ward_number: "1"
- pin_code: "462001"
"""
    
    # Create chat for function calling
    function_chat = multi_agent_system.agents[AgentRole.FUNCTION_CALLER].start_chat(history=[])
    function_response = function_chat.send_message(function_prompt)
    
    # Process function calls if any
    if (function_response.candidates and 
        len(function_response.candidates) > 0 and 
        function_response.candidates[0].content and 
        function_response.candidates[0].content.parts):
        
        for part in function_response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                function_name = part.function_call.name
                function_args = dict(part.function_call.args)
                
                print(f"🔧 Function call detected: {function_name} with args: {function_args}")
                
                if function_name in function_map:
                    # Execute the function
                    result = await function_map[function_name](**function_args)
                    print(f"✅ Function result: {result}")
                    
                    # Clear pending complaint
                    session.context["pending_complaint"] = None
                    session.context["current_step"] = None
                    
                    # Format success response
                    if result.get("success"):
                        return f"""
🎉 **Complaint Registered Successfully!**

**Grievance ID:** {result.get('grievance_id', 'N/A')}
**Status:** {result.get('status', 'SUBMITTED')}

You can track your complaint using the Grievance ID. You'll receive SMS updates on the progress.

Is there anything else I can help you with?
"""
                    else:
                        return f"❌ Failed to register complaint: {result.get('error', 'Unknown error')}"
    
    return "I wasn't able to register the complaint properly. Please try again."

async def handle_status_check(user_message: str, session: ChatSession, routing_result: dict) -> str:
    """Handle complaint status checking"""
    
    grievance_id = routing_result.get("extracted_info", {}).get("grievance_id")
    
    if not grievance_id:
        # Try to extract from message
        words = user_message.upper().split()
        for word in words:
            if word.startswith("GR") or (word.isalnum() and len(word) > 5):
                grievance_id = word
                break
    
    if not grievance_id:
        return "Please provide your Grievance ID to check the status. It usually starts with 'GR' followed by numbers."
    
    # Call function to get status
    result = await get_complaint_status(grievance_id)
    
    if result.get("success"):
        grievance = result["grievance"]
        return f"""
📋 **Complaint Status**

**Grievance ID:** {grievance.get('grievance_id', 'N/A')}
**Status:** {grievance.get('status', 'N/A')}
**Category:** {grievance.get('category', 'N/A')}
**Title:** {grievance.get('title', 'N/A')}
**Submitted on:** {grievance.get('created_at', 'N/A')}
**Last Updated:** {grievance.get('updated_at', 'N/A')}

{grievance.get('description', '')}
"""
    else:
        return f"❌ Could not find complaint with ID '{grievance_id}'. Please check the ID and try again."

async def handle_authentication(user_message: str, session: ChatSession, routing_result: dict) -> str:
    """Handle authentication flow"""
    
    mobile = routing_result.get("extracted_info", {}).get("mobile")
    
    if "otp" in user_message.lower() and any(word.isdigit() and len(word) == 6 for word in user_message.split()):
        # User is providing OTP
        otp = next((word for word in user_message.split() if word.isdigit() and len(word) == 6), None)
        if otp and current_session.get("mobile"):
            result = await verify_otp(current_session["mobile"], otp)
            if result.get("success"):
                return f"✅ Login successful! Welcome {result['user']['name']}. You can now register complaints and check their status."
            else:
                return f"❌ Invalid OTP: {result.get('error', 'Please try again')}"
        else:
            return "Please provide the 6-digit OTP you received."
    
    if not mobile:
        return "Please provide your mobile number to receive an OTP for login."
    
    # Send OTP
    result = await send_otp(mobile)
    if result.get("success"):
        return f"📱 OTP sent to {mobile}. Please reply with the 6-digit OTP to complete login."
    else:
        return f"❌ Failed to send OTP: {result.get('error', 'Please try again')}"

async def handle_categories_request(session: ChatSession) -> str:
    """Handle request for available categories"""
    
    result = await get_grievance_categories()
    
    if result.get("success"):
        categories = result["categories"]
        category_list = "\n".join([f"• {cat.get('name', 'N/A')}" for cat in categories])
        return f"""
📋 **Available Municipal Services:**

{category_list}

You can report any of these issues by simply describing the problem. For example: "There's garbage piling up on my street" or "The street light is not working near my house."
"""
    else:
        return "I couldn't fetch the available categories right now. You can still describe your issue and I'll help categorize it."

async def handle_general_help(user_message: str, session: ChatSession) -> str:
    """Handle general help requests"""
    
    return """
👋 **Welcome to Municipal Voice Assistant!**

I can help you with:
🏛️ **Register Complaints** - Report issues like garbage, potholes, water leaks, street lights, etc.
📊 **Check Status** - Track your complaint progress using Grievance ID
🔐 **Account Services** - Login with OTP, view profile
📋 **Information** - Available services and categories

Just tell me what you need help with in simple words. For example:
• "There's a pothole on MG Road"
• "Check status of GR12345"
• "I want to login"

How can I assist you today?
"""

# ==================== API ENDPOINTS ====================

class TextQueryRequest(BaseModel):
    message: str
    language: Optional[str] = "en"
    session_id: Optional[str] = None

@app.post("/chat/text")
async def text_chat(request: TextQueryRequest):
    """Handle text-based chat with multi-agent system"""
    try:
        # Get or create chat session
        session = get_or_create_chat_session(
            session_id=request.session_id, 
            user_id=current_session.get("user_id")
        )
        
        print(f"💬 Using chat session: {session.session_id}")
        print(f"👤 User message: {request.message}")
        
        # Process with multi-agent system
        response_text = await process_with_multi_agents(request.message, session)
        
        # Add to session history
        session.add_message("user", request.message)
        session.add_message("assistant", response_text)
        
        print(f"🤖 Bot response: {response_text}")
        
        return JSONResponse({
            "success": True,
            "response": response_text,
            "session_id": session.session_id,
            "message_count": len(session.message_history),
            "session_info": {
                "authenticated": bool(current_session["token"]),
                "user_id": current_session.get("user_id"),
                "mobile": current_session.get("mobile"),
                "pending_complaint": bool(session.context.get("pending_complaint"))
            }
        })
        
    except Exception as e:
        print(f"❌ Error in text_chat: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

# ==================== VOICE PROCESSING ====================

def speech_to_text(audio_data: bytes) -> str:
    """Convert speech to text"""
    try:
        r = sr.Recognizer()
        audio_file = sr.AudioFile(BytesIO(audio_data))
        
        with audio_file as source:
            audio = r.record(source)
        
        text = r.recognize_google(audio, language='en-IN')
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Speech recognition failed: {str(e)}")

def text_to_speech(text: str) -> bytes:
    """Convert text to speech"""
    try:
        engine = pyttsx3.init()
        
        voices = engine.getProperty('voices')
        if len(voices) > 1:
            engine.setProperty('voice', voices[1].id)
        
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 0.8)
        
        engine.save_to_file(text, 'temp_audio.wav')
        engine.runAndWait()
        
        with open('temp_audio.wav', 'rb') as f:
            audio_data = f.read()
        
        os.remove('temp_audio.wav')
        return audio_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text-to-speech failed: {str(e)}")

@app.post("/chat/voice")
async def voice_chat(audio_file: UploadFile = File(...), session_id: Optional[str] = Form(None)):
    """Handle voice-based chat with multi-agent system"""
    try:
        # Convert speech to text
        audio_data = await audio_file.read()
        user_text = speech_to_text(audio_data)
        
        print(f"👤 User said: {user_text}")
        
        # Get or create chat session
        session = get_or_create_chat_session(
            session_id=session_id, 
            user_id=current_session.get("user_id")
        )
        
        # Process with multi-agent system
        response_text = await process_with_multi_agents(user_text, session)
        
        # Add to session history
        session.add_message("user", user_text)
        session.add_message("assistant", response_text)
        
        print(f"🤖 Bot response: {response_text}")
        
        # Convert response to speech
        audio_response = text_to_speech(response_text)
        
        return JSONResponse({
            "success": True,
            "text_input": user_text,
            "text_response": response_text,
            "audio_response": base64.b64encode(audio_response).decode(),
            "session_id": session.session_id,
            "message_count": len(session.message_history),
            "session_info": {
                "authenticated": bool(current_session["token"]),
                "user_id": current_session.get("user_id"),
                "mobile": current_session.get("mobile"),
                "pending_complaint": bool(session.context.get("pending_complaint"))
            }
        })
            
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

# ==================== SESSION MANAGEMENT ENDPOINTS ====================

@app.get("/chat/sessions")
async def get_active_sessions():
    """Get list of active chat sessions"""
    cleanup_expired_sessions()
    
    sessions_info = []
    for session_id, session in chat_sessions.items():
        sessions_info.append({
            "session_id": session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "message_count": len(session.message_history),
            "pending_complaint": bool(session.context.get("pending_complaint")),
            "current_step": session.context.get("current_step")
        })
    
    return JSONResponse({
        "active_sessions": len(sessions_info),
        "sessions": sessions_info
    })

@app.get("/chat/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """Get conversation history for a session"""
    if session_id not in chat_sessions:
        return JSONResponse({
            "error": "Session not found"
        }, status_code=404)
    
    session = chat_sessions[session_id]
    return JSONResponse({
        "session_id": session_id,
        "message_history": session.message_history,
        "context": session.context,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat()
    })

@app.delete("/chat/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear/delete a specific chat session"""
    if session_id in chat_sessions:
        del chat_sessions[session_id]
        return JSONResponse({"message": f"Session {session_id} cleared successfully"})
    else:
        return JSONResponse({"error": "Session not found"}, status_code=404)

@app.post("/chat/sessions/cleanup")
async def cleanup_sessions():
    """Manually cleanup expired sessions"""
    initial_count = len(chat_sessions)
    cleanup_expired_sessions()
    final_count = len(chat_sessions)
    
    return JSONResponse({
        "message": f"Cleaned up {initial_count - final_count} expired sessions",
        "active_sessions": final_count
    })

@app.get("/session/status")
async def get_session_status():
    """Get current session status"""
    return JSONResponse({
        "authenticated": bool(current_session["token"]),
        "user_id": current_session.get("user_id"),
        "mobile": current_session.get("mobile")
    })

@app.post("/session/clear")
async def clear_session_status():
    """Clear current session"""
    current_session.clear()
    current_session.update({"token": None, "user_id": None, "mobile": None})
    return JSONResponse({"message": "Session cleared successfully"})

@app.get("/health")
async def health_check():
    return {"status": "OK", "service": "Multi-Agent Municipal Voice Assistant"}

# ==================== DEBUG ENDPOINTS ====================

@app.get("/debug/test-agents")
async def test_agents():
    """Test all agents individually"""
    test_message = "There's garbage piling up on MG Road near City Mall"
    
    results = {}
    
    try:
        # Test Router Agent
        router_response = multi_agent_system.agents[AgentRole.ROUTER].generate_content(
            f"Classify this user message: '{test_message}'"
        )
        results["router"] = {
            "response": router_response.text,
            "success": True
        }
    except Exception as e:
        results["router"] = {"error": str(e), "success": False}
    
    try:
        # Test Analyzer Agent
        analyzer_response = multi_agent_system.agents[AgentRole.ANALYZER].generate_content(
            f"Analyze this complaint: '{test_message}'"
        )
        results["analyzer"] = {
            "response": analyzer_response.text,
            "success": True
        }
    except Exception as e:
        results["analyzer"] = {"error": str(e), "success": False}
    
    try:
        # Test Response Formatter Agent
        formatter_response = multi_agent_system.agents[AgentRole.RESPONSE_FORMATTER].generate_content(
            f"Format a friendly response for: '{test_message}'"
        )
        results["formatter"] = {
            "response": formatter_response.text,
            "success": True
        }
    except Exception as e:
        results["formatter"] = {"error": str(e), "success": False}
    
    return JSONResponse(results)

@app.get("/debug/test-api")
async def test_api_connection():
    """Test connection to municipal API"""
    try:
        response = await http_client.get(f"{BASE_API_URL}/grievances/categories")
        
        return JSONResponse({
            "base_url": BASE_API_URL,
            "status_code": response.status_code,
            "response_body": response.text,
            "success": response.status_code == 200
        })
    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "base_url": BASE_API_URL
        }, status_code=500)

@app.get("/debug/function-test/{function_name}")
async def test_function_directly(function_name: str):
    """Test a specific function directly"""
    if function_name not in function_map:
        return JSONResponse({"error": f"Function {function_name} not found"}, status_code=404)
    
    try:
        if function_name in ["get_grievance_categories", "get_user_profile"]:
            result = await function_map[function_name]()
        else:
            result = {"message": f"Function {function_name} requires parameters. Use the chat interface to test it."}
            
        return JSONResponse({
            "function_name": function_name,
            "result": result,
            "success": True
        })
    except Exception as e:
        return JSONResponse({
            "function_name": function_name,
            "error": str(e),
            "success": False
        }, status_code=500)

# ==================== LIFECYCLE EVENTS ====================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 Multi-Agent Municipal Voice Assistant starting up...")
    print(f"📡 Will connect to municipal API at: {BASE_API_URL}")
    
    print("Connecting to MongoDB...")
    await init_db()

    print("Testing Redis Connection...")
    try:
        await connect_redis()
        print("✅ Redis connection successful!")
    except Exception as err:
        print(f"⚠️ Redis connection failed: {err}")
    
    print("Initializing Multi-Agent System...")
    try:
        # Test all agents
        test_message = "test initialization"
        for role, agent in multi_agent_system.agents.items():
            test_response = agent.generate_content(f"Test: {test_message}")
            print(f"✅ {role} agent initialized successfully")
    except Exception as e:
        print(f"⚠️ Agent initialization warning: {e}")
        
    # Pre-load categories cache
    try:
        await get_grievance_categories()
        print("✅ Categories cache preloaded")
    except Exception as e:
        print(f"⚠️ Could not preload categories: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    print("🛑 Shutting down Multi-Agent Municipal Voice Assistant...")
    await http_client.aclose()

@app.get("/")
async def root():
    return {
        "message": "Multi-Agent Municipal Voice Assistant",
        "version": "2.0.0",
        "status": "running",
        "architecture": "Multi-Agent System",
        "agents": {
            "router": "Classifies user intent and routes requests",
            "analyzer": "Extracts structured data from natural language",
            "function_caller": "Executes API functions based on requirements",
            "response_formatter": "Creates user-friendly responses"
        },
        "features": [
            "Intent Classification",
            "Smart Complaint Analysis", 
            "Automatic Function Calling",
            "Conversation Context Management",
            "Voice & Text Support",
            "Session Management"
        ],
        "workflow": [
            "1. Router Agent classifies user intent",
            "2. Analyzer Agent extracts structured data (for complaints)",
            "3. Function Caller Agent executes required API calls",
            "4. Response Formatter Agent creates user-friendly responses"
        ],
        "endpoints": {
            "text_chat": "/chat/text",
            "voice_chat": "/chat/voice",
            "session_status": "/session/status",
            "session_history": "/chat/sessions/{session_id}/history",
            "test_agents": "/debug/test-agents",
            "health": "/health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("VOICE_ASSISTANT_PORT", 8000))
    print(f"Starting Multi-Agent Municipal Voice Assistant on port {port}...")
    uvicorn.run("main_with_multi_gemini:app", host="0.0.0.0", port=port, reload=True)