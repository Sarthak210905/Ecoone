"""
app/services/gemini_service.py - Gemini AI Integration Service
"""
import os
import google.generativeai as genai
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class GeminiService:
    def __init__(self):
        self.model = None
        self.functions = self._get_function_schemas()
        
    def initialize(self):
        """Initialize Gemini AI with API key and configuration"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
            
        genai.configure(api_key=api_key)
        self.model = self._create_gemini_agent()
        
    def _create_gemini_agent(self):
        """Create and configure Gemini model with function calling"""
        
        system_instruction = f"""
You are a Voice-to-Voice Municipal Assistant for helping citizens with municipal services. This system supports multiple platforms: Web, WhatsApp text, WhatsApp voice messages, WhatsApp calls, and regular phone calls.

**CRITICAL: PLATFORM-SPECIFIC AUTHENTICATION**
1. **Web & WhatsApp Text**: Require OTP authentication (mobile → OTP → access)
2. **Voice & WhatsApp Calls**: Auto-authenticate using caller's phone number (NO OTP NEEDED)
3. Never mix authentication methods - voice platforms get instant access

**AUTHENTICATION FLOW BY PLATFORM:**

For Web/WhatsApp Text Sessions:
- Step 1: Ask for mobile number → CALL send_otp()
- Step 2: Ask for OTP → CALL verify_otp()
- Step 3: Provide full services
- Keep responses conversational and natural for speech/WhatsApp
- Avoid long lists or complex formatting
- Use clear, spoken language patterns
- Spell out numbers and codes when needed for voice
- For WhatsApp, use emojis and clear formatting
- Please respond in the same language as the user input (for example English/Hindi/or even Hinglish or any other language written in english script)

For Voice/WhatsApp Call Sessions:
- User is automatically authenticated by phone number
- Provide services immediately after greeting
- Do NOT ask for mobile or OTP

**EXACT API CATEGORY VALUES**
When calling register_complaint function, use these EXACT category strings:
garbage, water_supply, drainage, street_lights, roads, sewage, noise_pollution, illegal_construction, property_tax, other

**RESPONSE OPTIMIZATION:**

1. **Clean Responses**: Never include internal context, authentication status, or debug information in user responses
2. **Platform-Appropriate Responses**:
   - Voice: Natural, conversational, spell out IDs and numbers
   - WhatsApp: Use emojis, clear formatting, shorter messages
   - Web: Standard text formatting
3. **Language Support**: Respond in the same language as user input (English/Hindi/Hinglish)

**FUNCTION CALLING RULES:**
- Auto-call functions when users request services
- Never ask permission just confirm once u prepare the final thing - execute and report results but in alpha numeric format as previously the numeric part of any id was given by you in alphabetic format which was causing issues.
- Handle errors gracefully with user-friendly explanations
- For complaint registration: Extract details from natural speech/text

**GREETING EXAMPLES:**
- Voice/WhatsApp Calls: "Welcome to Municipal Voice Assistant! I can help you register complaints, check status, and provide municipal information. How can I assist you?"
- Web/WhatsApp Text: "Welcome! To get started, I need to verify your identity. Please provide your mobile number."

**SESSION AUTHENTICATION STATES:**
- NEED_MOBILE: Ask for mobile (web/whatsapp text only)
- NEED_OTP: Ask for OTP (web/whatsapp text only)  
- NEED_AUTO_AUTH: Voice platforms auto-auth in progress
- AUTHENTICATED: Full services available

**IMPORTANT:** Only respond with the actual message to the user. Never include authentication status, internal context, or debug information in your responses.

You represent the municipal corporation - be helpful, professional, and efficient.


5. **Complaint Registration**:
   - Extract details from natural speech/text
   - Auto-generate professional titles and descriptions
   - Confirm details before submitting: "Let me register a complaint about [issue] at [location]. Is this correct?"

6. **Multi-Platform Support**:
   - Voice: Natural speech patterns, spell out IDs
   - WhatsApp: Use emojis, clear formatting, shorter messages
   - Web: Standard text formatting


**WHATSAPP SPECIFIC:**
- Use emojis appropriately 📱 ✅ 🏛️ 📋
- Break long responses into shorter messages
- Use clear formatting with line breaks
- Confirm actions with simple yes/no questions

You represent the municipal corporation - be helpful, professional, and efficient while ensuring security through proper authentication.
"""

        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-lite",
            system_instruction=system_instruction,
            tools=[{"function_declarations": self.functions}]
        )
        
        return model
    
    def start_chat(self, history: List = None):
        """Start a new chat session with optional history"""
        if not self.model:
            raise RuntimeError("Gemini service not initialized. Call initialize() first.")
        return self.model.start_chat(history=history or [])
    
    def _get_function_schemas(self) -> List[Dict[str, Any]]:
        """Get function schemas for Gemini function calling"""
        return [
            {
                "name": "set_token",
                "description": "Set JWT authentication token for API requests",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "token": {"type": "string", "description": "JWT authentication token"}
                    },
                    "required": ["token"]
                }
            },
            {
                "name": "send_otp",
                "description": "Send OTP to a user's mobile number for authentication. Required as first step for new sessions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mobile": {
                            "type": "string",
                            "description": "Mobile number with country code where OTP will be sent"
                        }
                    },
                    "required": ["mobile"]
                }
            },
            {
                "name": "verify_otp",
                "description": "Verify OTP sent to the user's mobile. Returns a JWT authentication token and user info. Creates a new user if one does not exist.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mobile": {
                            "type": "string",
                            "description": "Mobile number where OTP was sent"
                        },
                        "otp": {
                            "type": "string",
                            "description": "6-digit OTP received by the user"
                        }
                    },
                    "required": ["mobile", "otp"]
                }
            },
            {
                "name": "register_complaint",
                "description": "Register a new municipal complaint/grievance. Requires authentication.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "Complaint category (garbage, water_supply, drainage, street_lights, roads, sewage, noise_pollution, illegal_construction, property_tax, other)"},
                        "title": {"type": "string", "description": "Brief title of the complaint"},
                        "description": {"type": "string", "description": "Detailed description of the issue"},
                        "location": {"type": "string", "description": "Location/area where the issue is observed"},
                        "address": {"type": "string", "description": "Complete address of the issue location"}
                    },
                    "required": ["category", "title", "description", "location", "address"]
                }
            },
            {
                "name": "get_complaint_status",
                "description": "Get status and details of a registered complaint using grievance ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "grievance_id": {"type": "string", "description": "Unique grievance ID returned when complaint was registered"}
                    },
                    "required": ["grievance_id"]
                }
            },
            {
                "name": "track_complaint",
                "description": "Track complaint status (same as get_complaint_status)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "grievance_id": {"type": "string", "description": "Unique grievance ID to track"}
                    },
                    "required": ["grievance_id"]
                }
            },
            {
                "name": "get_user_profile",
                "description": "Get current authenticated user's profile information",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "update_profile",
                "description": "Update user profile information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "User's full name"},
                        "email": {"type": "string", "description": "User's email address"},
                        "age": {"type": "integer", "description": "User's age"}
                    },
                    "required": []
                }
            },
            {
                "name": "get_grievance_categories",
                "description": "Get all available complaint/grievance categories",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_awareness_info",
                "description": "Get information about municipal awareness programs and FAQs",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Topic for awareness information (health, vaccination, cleanliness, water, etc.)"}
                    },
                    "required": ["topic"]
                }
            }
        ]

# Global instance
gemini_service = GeminiService()

def get_gemini_service() -> GeminiService:
    """Get the global Gemini service instance"""
    return gemini_service