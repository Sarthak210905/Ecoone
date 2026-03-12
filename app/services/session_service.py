"""
app/services/session_service.py - Chat Session Management Service
"""
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from .gemini_service import get_gemini_service

class ChatSession:
    def __init__(self, session_id: str, user_id: str = None, platform: str = "web"):
        self.session_id = session_id
        self.user_id = user_id
        self.platform = platform  # "web", "whatsapp", "voice", "whatsapp_call"
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.chat = None  # Gemini chat instance
        self.message_history = []  # Store conversation history
        self.function_call_history = []  # Store function call results for context
        
        # Authentication state
        self.is_authenticated = False
        self.pending_mobile = None  # Store mobile during OTP flow
        self.auth_token = None
        self.user_info = None
        
        # Platform-specific data
        self.whatsapp_number = None  # For WhatsApp sessions
        self.call_sid = None  # For voice call sessions
        self.caller_number = None  # Store caller phone number for voice calls
        
        # Login flow state
        self.auth_step = "NEED_MOBILE"  # NEED_MOBILE -> NEED_OTP -> AUTHENTICATED
        
        # Auto-authenticate for voice platforms
        if platform in ["voice", "whatsapp_call"]:
            self.auth_step = "NEED_AUTO_AUTH"  # Special state for voice authentication
        
        # Initialize Gemini chat
        self._init_gemini_chat()
        
    def _init_gemini_chat(self):
        """Initialize Gemini chat instance"""
        try:
            gemini_service = get_gemini_service()
            self.chat = gemini_service.start_chat(history=[])
        except Exception as e:
            print(f"❌ Failed to initialize Gemini chat for session {self.session_id}: {e}")
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
        
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired"""
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)
    
    def add_message(self, role: str, content: str, function_calls: List[Dict] = None):
        """Add message to history"""
        self.message_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "function_calls": function_calls or [],
            "platform": self.platform
        })
        
        # Keep only last 20 messages to prevent memory issues
        if len(self.message_history) > 20:
            self.message_history = self.message_history[-20:]

    def set_authenticated(self, token: str, user_info: dict):
        """Mark session as authenticated"""
        self.is_authenticated = True
        self.auth_token = token
        self.user_info = user_info
        self.auth_step = "AUTHENTICATED"
        self.user_id = user_info.get("_id")

    def get_auth_status(self):
        """Get current authentication status"""
        return {
            "authenticated": self.is_authenticated,
            "auth_step": self.auth_step,
            "mobile": self.pending_mobile,
            "user_id": self.user_id,
            "platform": self.platform,
            "caller_number": getattr(self, 'caller_number', None)
        }
    
    def set_whatsapp_info(self, whatsapp_number: str):
        """Set WhatsApp-specific information"""
        self.whatsapp_number = whatsapp_number
        if self.platform == "web":  # Only change if not already set to whatsapp_call
            self.platform = "whatsapp"
    
    def set_voice_info(self, call_sid: str):
        """Set voice call-specific information"""
        self.call_sid = call_sid
        if self.platform == "web":  # Only change if not already set
            self.platform = "voice"
    
    def set_caller_number(self, caller_number: str):
        """Set caller phone number for voice authentication"""
        self.caller_number = caller_number

class SessionService:
    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        
    def get_or_create_session(self, session_id: str = None, user_id: str = None, 
                            platform: str = "web", whatsapp_number: str = None,
                            call_sid: str = None) -> ChatSession:
        """Get existing session or create new one"""
        
        # Clean up expired sessions
        self.cleanup_expired_sessions()
        
        # For WhatsApp, use phone number as session ID if no session_id provided
        if platform == "whatsapp" and not session_id and whatsapp_number:
            session_id = f"whatsapp_{whatsapp_number.replace('+', '').replace(':', '_')}"
        
        # For WhatsApp calls, use call SID as session ID
        elif platform == "whatsapp_call" and not session_id and call_sid:
            session_id = f"whatsapp_call_{call_sid}"
        
        # For voice calls, use call SID as session ID if no session_id provided
        elif platform == "voice" and not session_id and call_sid:
            session_id = f"voice_{call_sid}"
        
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session.update_activity()
            return session
        
        # Create new session
        new_session_id = session_id or str(uuid.uuid4())
        session = ChatSession(new_session_id, user_id, platform)
        
        # Set platform-specific info
        if platform == "whatsapp" and whatsapp_number:
            session.set_whatsapp_info(whatsapp_number)
        elif platform in ["voice", "whatsapp_call"] and call_sid:
            session.set_voice_info(call_sid)
        
        self.sessions[new_session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get existing session by ID"""
        return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a specific session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def cleanup_expired_sessions(self):
        """Remove expired chat sessions"""
        expired_sessions = [
            sid for sid, session in self.sessions.items() 
            if session.is_expired()
        ]
        
        for sid in expired_sessions:
            del self.sessions[sid]
        
        if expired_sessions:
            print(f"🧹 Cleaned up {len(expired_sessions)} expired chat sessions")
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        return len(self.sessions)
    
    def get_sessions_by_platform(self, platform: str) -> List[ChatSession]:
        """Get all sessions for a specific platform"""
        return [session for session in self.sessions.values() if session.platform == platform]
    
    def build_context_prompt(self, session: ChatSession) -> str:
        """Build context prompt from chat history"""
        if not session.message_history:
            return ""
        
        context_parts = []
        
        # Add conversation context
        if len(session.message_history) > 0:
            context_parts.append("Previous conversation context:")
            for msg in session.message_history[-5:]:  # Last 5 messages for context
                role_emoji = "👤" if msg["role"] == "user" else "🤖"
                context_parts.append(f"{role_emoji} {msg['role']}: {msg['content']}")
        
        # Add function call context if relevant
        recent_function_calls = [
            call for call in session.function_call_history[-3:]  # Last 3 function calls
            if datetime.fromisoformat(call["timestamp"]) > datetime.now() - timedelta(minutes=10)
        ]
        
        if recent_function_calls:
            context_parts.append("\nRecent actions taken:")
            for call in recent_function_calls:
                context_parts.append(f"- {call['function_name']}: {call.get('result_summary', 'Action completed')}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def get_all_sessions_info(self) -> List[Dict]:
        """Get information about all active sessions"""
        sessions_info = []
        for session_id, session in self.sessions.items():
            sessions_info.append({
                "session_id": session_id,
                "user_id": session.user_id,
                "platform": session.platform,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "message_count": len(session.message_history),
                "function_calls": len(session.function_call_history),
                "auth_status": session.get_auth_status(),
                "whatsapp_number": getattr(session, 'whatsapp_number', None),
                "call_sid": getattr(session, 'call_sid', None),
                "caller_number": getattr(session, 'caller_number', None)
            })
        return sessions_info

# Global instance
session_service = SessionService()

def get_session_service() -> SessionService:
    """Get the global session service instance"""
    return session_service