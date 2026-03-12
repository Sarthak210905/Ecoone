"""
app/routes/voice_chat_routes.py - Voice & Text Chat Routes for Web Interface
"""
import base64
import os
import uuid
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..services.session_service import get_session_service
from ..services.speech_service import get_speech_service
from ..controllers.voiceAssistantController import VoiceAssistantController

router = APIRouter()

# Initialize services
session_service = get_session_service()
speech_service = get_speech_service()
voice_controller = VoiceAssistantController()

class TextQueryRequest(BaseModel):
    message: str
    language: Optional[str] = "en"
    session_id: Optional[str] = None

@router.post("/voice")
async def voice_to_voice_chat(audio_file: UploadFile = File(...), session_id: Optional[str] = Form(None)):
    """Handle complete voice-to-voice interaction with mandatory authentication"""
    try:
        # Step 1: Convert speech to text
        audio_data = await audio_file.read()
        user_text = speech_service.speech_to_text(audio_data)
        
        print(f"👤 User said: {user_text}")
        
        # Step 2: Get or create chat session
        session = session_service.get_or_create_session(
            session_id=session_id,
            platform="web"
        )
        
        print(f"💬 Session: {session.session_id}, Auth Status: {session.get_auth_status()}")
        
        # Step 3: Process message through voice controller
        response_text = await voice_controller.process_text_message(session, user_text)
        
        print(f"🤖 Bot response: {response_text}")
        
        # Step 4: Convert response to speech
        audio_response = speech_service.text_to_speech(response_text)
        
        # Step 5: Return voice response with session info
        return JSONResponse({
            "success": True,
            "user_speech": user_text,
            "bot_response": response_text,
            "audio_response": base64.b64encode(audio_response).decode(),
            "session_id": session.session_id,
            "auth_status": session.get_auth_status(),
            "message_count": len(session.message_history),
            "content_type": "audio/wav"
        })
            
    except HTTPException as he:
        # Handle HTTP exceptions (like speech recognition errors)
        error_message = str(he.detail)
        print(f"❌ HTTP Error: {error_message}")
        
        # Convert error to speech for voice response
        try:
            error_audio = speech_service.text_to_speech(f"I'm sorry, {error_message} Please try again.")
            return JSONResponse({
                "success": False,
                "error": error_message,
                "audio_response": base64.b64encode(error_audio).decode(),
                "session_id": session_id,
                "content_type": "audio/wav"
            }, status_code=he.status_code)
        except:
            return JSONResponse({
                "success": False,
                "error": error_message,
                "session_id": session_id
            }, status_code=he.status_code)
            
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(f"❌ Unexpected Error: {error_message}")
        
        # Try to provide voice error response
        try:
            error_audio = speech_service.text_to_speech("I'm sorry, there was a technical issue. Please try again.")
            return JSONResponse({
                "success": False,
                "error": error_message,
                "audio_response": base64.b64encode(error_audio).decode(),
                "session_id": session_id,
                "content_type": "audio/wav"
            }, status_code=500)
        except:
            return JSONResponse({
                "success": False,
                "error": error_message,
                "session_id": session_id
            }, status_code=500)

@router.post("/text")
async def text_chat_with_auth(request: TextQueryRequest):
    """Handle text-based chat with mandatory authentication (for testing)"""
    try:
        # Get or create chat session
        session = session_service.get_or_create_session(
            session_id=request.session_id,
            platform="web"
        )
        
        print(f"💬 Text Session: {session.session_id}, Auth: {session.get_auth_status()}")
        print(f"👤 User message: {request.message}")
        
        # Process message through voice controller
        response_text = await voice_controller.process_text_message(session, request.message)
        
        print(f"🤖 Bot response: {response_text}")
        
        return JSONResponse({
            "success": True,
            "response": response_text,
            "session_id": session.session_id,
            "auth_status": session.get_auth_status(),
            "message_count": len(session.message_history)
        })
        
    except Exception as e:
        print(f"❌ Error in text_chat: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

@router.get("/test/speech")
async def test_speech_generation():
    """Test text-to-speech functionality"""
    try:
        test_message = "Welcome to the Municipal Voice Assistant! I can help you register complaints and check their status. Please provide your mobile number to get started."
        audio_data = speech_service.text_to_speech(test_message)
        
        return JSONResponse({
            "success": True,
            "message": test_message,
            "audio_response": base64.b64encode(audio_data).decode(),
            "content_type": "audio/wav"
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

@router.get("/sessions")
async def get_active_sessions():
    """Get list of active chat sessions"""
    try:
        session_service.cleanup_expired_sessions()
        sessions_info = session_service.get_all_sessions_info()
        
        return JSONResponse({
            "success": True,
            "active_sessions": session_service.get_active_sessions_count(),
            "sessions": sessions_info
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

@router.get("/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed information about a specific session"""
    try:
        session = session_service.get_session(session_id)
        if not session:
            return JSONResponse({
                "success": False,
                "error": "Session not found"
            }, status_code=404)
        
        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "auth_status": session.get_auth_status(),
            "message_history": session.message_history,
            "function_call_history": session.function_call_history,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "platform": session.platform
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

@router.delete("/sessions/{session_id}")
async def clear_specific_session(session_id: str):
    """Clear/delete a specific chat session"""
    try:
        success = session_service.delete_session(session_id)
        if success:
            return JSONResponse({
                "success": True,
                "message": f"Session {session_id} cleared successfully"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "Session not found"
            }, status_code=404)
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

@router.post("/sessions/cleanup")
async def manual_cleanup_sessions():
    """Manually cleanup expired sessions"""
    try:
        initial_count = session_service.get_active_sessions_count()
        session_service.cleanup_expired_sessions()
        final_count = session_service.get_active_sessions_count()
        
        return JSONResponse({
            "success": True,
            "message": f"Cleaned up {initial_count - final_count} expired sessions",
            "active_sessions": final_count
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)