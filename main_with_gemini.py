"""
main_with_gemini.py - Clean Voice Assistant with WhatsApp Integration and Fixed Audio Serving
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import mimetypes
import threading
import schedule
import time

# Import database and Redis initialization
from app.database.database import init_db
from app.utils.redis_client import connect_redis

# Import existing routes
from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router
from app.routes.grievance_routes import router as grievance_router
from app.routes.grievance_admin_routes import router as grievance_admin_router
from app.routes.green_credit_routes import router as green_credit_router



# Import new voice assistant routes
from app.routes.voice_chat_routes import router as voice_chat_router
from app.routes.twilio_routes import router as twilio_router

# Import services for initialization
from app.services.gemini_service import get_gemini_service
from app.services.municipal_api_service import get_municipal_api_service
from app.services.twilio_service import get_twilio_service
from app.services.session_service import get_session_service
from app.services.speech_service import get_speech_service

load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Municipal Voice Assistant with WhatsApp & Voice Calls",
    version="3.0.0",
    description="Complete municipal services assistant with voice, text, WhatsApp, and phone call support"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static directory exists
os.makedirs("static/audio", exist_ok=True)

# Configure MIME types for audio files
mimetypes.add_type('audio/wav', '.wav')
mimetypes.add_type('audio/mpeg', '.mp3')
mimetypes.add_type('audio/ogg', '.ogg')

# Custom StaticFiles class to ensure proper Content-Type for audio files
class AudioStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def get_response(self, path: str, scope):
        """Override to ensure proper Content-Type for audio files"""
        response = super().get_response(path, scope)
        
        # Ensure proper Content-Type for audio files
        if path.endswith('.wav'):
            if hasattr(response, 'headers'):
                response.headers['Content-Type'] = 'audio/wav'
        elif path.endswith('.mp3'):
            if hasattr(response, 'headers'):
                response.headers['Content-Type'] = 'audio/mpeg'
        elif path.endswith('.ogg'):
            if hasattr(response, 'headers'):
                response.headers['Content-Type'] = 'audio/ogg'
        
        return response

# Mount static files with custom handler for audio
app.mount("/static", AudioStaticFiles(directory="static"), name="static")

# Alternative: Custom endpoint for serving audio files with explicit Content-Type
@app.get("/audio/{filename}")
async def serve_audio_file(filename: str):
    """Serve audio files with explicit Content-Type headers for WhatsApp compatibility"""
    file_path = os.path.join("static/audio", filename)
    
    if not os.path.exists(file_path):
        return {"error": "File not found"}, 404
    
    # Determine content type based on file extension (WhatsApp compatible)
    content_type = "audio/ogg"  # Default to OGG (preferred by WhatsApp)
    if filename.endswith('.mp3'):
        content_type = "audio/mpeg"
    elif filename.endswith('.ogg'):
        content_type = "audio/ogg"
    elif filename.endswith('.m4a'):
        content_type = "audio/m4a"
    elif filename.endswith('.amr'):
        content_type = "audio/amr"
    elif filename.endswith('.wav'):
        content_type = "audio/wav"
    
    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=filename,
        headers={
            "Content-Type": content_type,
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Accept-Ranges": "bytes"  # Important for audio streaming
        }
    )

# ==================== REGISTER ALL ROUTES ====================

# Existing routes
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(user_router, prefix="/api/users", tags=["Users"])
app.include_router(grievance_router, prefix="/api/grievances", tags=["Grievances"])
app.include_router(grievance_admin_router, prefix="/api/grievances", tags=["Admin Grievances"])
# New Green Credits routes
app.include_router(green_credit_router, prefix="/api/green-credits", tags=["Green Credits"])

# New voice assistant routes
app.include_router(voice_chat_router, prefix="/api/chat", tags=["Voice Chat"])
app.include_router(twilio_router, prefix="/api/twilio", tags=["Twilio Integration"])

# ==================== AUDIO CLEANUP SCHEDULER ====================

def run_audio_cleanup():
    """Run audio file cleanup"""
    twilio_service = get_twilio_service()
    twilio_service.cleanup_old_audio_files(max_age_hours=2)  # Clean files older than 2 hours

def schedule_cleanup():
    """Schedule cleanup to run every hour"""
    schedule.every(1).hour.do(run_audio_cleanup)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

def start_cleanup_scheduler():
    """Start the cleanup scheduler in a separate thread"""
    cleanup_thread = threading.Thread(target=schedule_cleanup, daemon=True)
    cleanup_thread.start()
    print("🧹 Audio file cleanup scheduler started")

# ==================== LIFECYCLE EVENTS ====================

@app.on_event("startup")
async def startup_event():
    """Initialize all services on startup"""
    print("🚀 Municipal Voice Assistant with WhatsApp Integration starting...")
    print(f"📡 Base API URL: {os.getenv('BASE_API_URL', 'http://localhost:8000/api')}")
    print(f"🌐 Base URL for webhooks: {os.getenv('BASE_URL', 'https://your-domain.ngrok.io')}")
    
    try:
        # Start audio cleanup scheduler
        start_cleanup_scheduler()
        
        # Initialize database
        print("📊 Connecting to MongoDB...")
        await init_db()
        print("✅ MongoDB connected!")
        
        # Initialize Redis
        print("🔴 Connecting to Redis...")
        try:
            await connect_redis()
            print("✅ Redis connected!")
        except Exception as err:
            print(f"⚠️ Redis connection failed (optional): {err}")
        
        # Initialize Gemini AI
        print("🤖 Initializing Gemini AI...")
        gemini_service = get_gemini_service()
        gemini_service.initialize()
        print("✅ Gemini AI initialized!")
        
        # Initialize Municipal API Service
        print("🏛️ Initializing Municipal API Service...")
        api_service = get_municipal_api_service()
        await api_service.initialize()
        print("✅ Municipal API Service initialized!")
        
        # Check Twilio configuration
        twilio_service = get_twilio_service()
        if twilio_service.is_configured():
            print("📱 Twilio configured successfully!")
            webhook_urls = twilio_service.get_webhook_urls()
            print(f"📱 WhatsApp Webhook: {webhook_urls['whatsapp_webhook']}")
            print(f"☎️ Voice Webhook: {webhook_urls['voice_webhook']}")
            
            # Additional WhatsApp-specific setup info
            base_url = os.getenv('BASE_URL', 'https://your-domain.ngrok.io')
            print(f"🎵 Audio serving URL: {base_url}/audio/ or {base_url}/static/audio/")
            
        else:
            print("⚠️ Twilio not configured (set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)")
        
        print("✅ All services initialized successfully!")
        print("\n🎯 Available Features:")
        print("   • Web Voice Chat (/api/chat/voice)")
        print("   • Web Text Chat (/api/chat/text)")
        print("   • WhatsApp Integration (/api/twilio/whatsapp)")
        print("   • Voice Call Integration (/api/twilio/voice)")
        print("   • Session Management (/api/chat/sessions)")
        print("   • Municipal Services (complaints, profiles, etc.)")
        print("   • Audio File Serving (/audio/{filename} or /static/audio/{filename})")
        
    except Exception as e:
        print(f"❌ Startup error: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    print("🛑 Shutting down Municipal Voice Assistant...")
    
    try:
        # Clean up Municipal API Service
        api_service = get_municipal_api_service()
        await api_service.cleanup()
        
        # Clean up speech service temp files
        speech_service = get_speech_service()
        speech_service.cleanup_temp_files()
        
        # Clean up audio files
        twilio_service = get_twilio_service()
        twilio_service.cleanup_old_audio_files(max_age_hours=0)  # Clean all files on shutdown
        
        print("✅ Shutdown complete!")
        
    except Exception as e:
        print(f"❌ Shutdown error: {str(e)}")

# ==================== ROOT ENDPOINT ====================

@app.get("/")
async def root():
    """Root endpoint with service information"""
    twilio_service = get_twilio_service()
    session_service = get_session_service()
    
    return {
        "message": "Municipal Voice Assistant with WhatsApp & Voice Calls",
        "version": "3.0.0",
        "status": "running",
        "features": [
            "Voice Input/Output (Web)",
            "Text Chat (Web)",
            "WhatsApp Integration",
            "Phone Call Support",
            "Mandatory User Authentication",
            "Session Management",
            "Municipal Services Integration",
            "Audio File Serving with Proper MIME Types"
        ],
        "endpoints": {
            "web_voice_chat": "/api/chat/voice",
            "web_text_chat": "/api/chat/text",
            "whatsapp_webhook": "/api/twilio/whatsapp",
            "voice_webhook": "/api/twilio/voice",
            "twilio_config": "/api/twilio/config",
            "sessions": "/api/chat/sessions",
            "audio_files": "/audio/{filename}",
            "static_files": "/static/audio/{filename}",
            "health": "/health"
        },
        "configuration": {
            "twilio_configured": twilio_service.is_configured(),
            "active_sessions": session_service.get_active_sessions_count(),
            "base_api_url": os.getenv("BASE_API_URL", "http://localhost:8000/api"),
            "audio_serving": "Custom audio endpoint with explicit MIME types"
        },
        "setup_instructions": {
            "whatsapp": "Configure Twilio WhatsApp sandbox webhook to /api/twilio/whatsapp",
            "voice": "Configure Twilio phone number webhook to /api/twilio/voice",
            "ngrok": "Use ngrok or similar for local development webhooks",
            "audio_troubleshooting": {
                "primary_url": "/audio/{filename} (recommended for WhatsApp)",
                "fallback_url": "/static/audio/{filename}",
                "mime_types": "Explicitly set Content-Type headers for audio files"
            }
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    session_service = get_session_service()
    twilio_service = get_twilio_service()
    
    return {
        "status": "OK",
        "service": "Municipal Voice Assistant",
        "version": "3.0.0",
        "timestamp": "2024-01-01T00:00:00Z",  # You can use actual timestamp
        "services": {
            "gemini_ai": "initialized",
            "municipal_api": "connected",
            "twilio": "configured" if twilio_service.is_configured() else "not_configured",
            "sessions": f"{session_service.get_active_sessions_count()} active",
            "audio_serving": "enabled with proper MIME types"
        },
        "platforms": [
            "Web Voice Chat",
            "Web Text Chat", 
            "WhatsApp",
            "Voice Calls"
        ]
    }

# ==================== DEBUGGING ENDPOINTS ====================

@app.get("/debug/audio/{filename}")
async def debug_audio_file(filename: str):
    """Debug endpoint to check audio file details"""
    file_path = os.path.join("static/audio", filename)
    
    if not os.path.exists(file_path):
        return {
            "error": "File not found",
            "path": file_path,
            "exists": False
        }
    
    file_stats = os.stat(file_path)
    
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    
    return {
        "filename": filename,
        "path": file_path,
        "exists": True,
        "size_bytes": file_stats.st_size,
        "mime_type": mime_type,
        "extension": os.path.splitext(filename)[1],
        "created": file_stats.st_ctime,
        "modified": file_stats.st_mtime,
        "serving_urls": {
            "primary": f"/audio/{filename}",
            "static": f"/static/audio/{filename}"
        }
    }

@app.get("/debug/static-dir")
async def debug_static_directory():
    """Debug endpoint to list static audio files"""
    audio_dir = "static/audio"
    
    if not os.path.exists(audio_dir):
        return {
            "error": "Audio directory does not exist",
            "path": audio_dir
        }
    
    files = []
    for filename in os.listdir(audio_dir):
        if filename.endswith(('.wav', '.mp3', '.ogg', '.m4a', '.amr')):
            file_path = os.path.join(audio_dir, filename)
            file_stats = os.stat(file_path)
            mime_type, _ = mimetypes.guess_type(file_path)
            
            # Override MIME type for better WhatsApp compatibility
            if filename.endswith('.ogg'):
                mime_type = "audio/ogg"
            elif filename.endswith('.mp3'):
                mime_type = "audio/mpeg"
            elif filename.endswith('.amr'):
                mime_type = "audio/amr"
            
            files.append({
                "filename": filename,
                "size_bytes": file_stats.st_size,
                "mime_type": mime_type,
                "age_hours": (time.time() - file_stats.st_mtime) / 3600,
                "whatsapp_compatible": filename.endswith(('.ogg', '.mp3', '.amr')),
                "urls": {
                    "primary": f"/audio/{filename}",
                    "static": f"/static/audio/{filename}"
                }
            })
    
    return {
        "audio_directory": audio_dir,
        "total_files": len(files),
        "files": files
    }

# ==================== RUN APPLICATION ====================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("VOICE_ASSISTANT_PORT", 8000))
    print(f"🎙️ Starting Municipal Voice Assistant on port {port}...")
    print("💡 Don't forget to:")
    print("   1. Set up ngrok: ngrok http 8000")
    print("   2. Configure Twilio webhooks with your ngrok URL")
    print("   3. Test WhatsApp and voice call integration")
    print("   4. Use /audio/{filename} endpoint for better audio serving")
    uvicorn.run("main_with_gemini:app", host="127.0.0.1", port=port, reload=True)