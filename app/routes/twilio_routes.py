"""
app/routes/twilio_routes.py - Twilio WhatsApp & Voice Integration Routes
"""
from fastapi import APIRouter, Request, Form, Query, UploadFile, File
from fastapi.responses import Response
from typing import Optional
import logging
import base64
import io
import os

from ..services.twilio_service import get_twilio_service
from ..services.session_service import get_session_service
from ..services.speech_service import get_speech_service
from ..controllers.voiceAssistantController import VoiceAssistantController

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
twilio_service = get_twilio_service()
session_service = get_session_service()
speech_service = get_speech_service()
voice_controller = VoiceAssistantController()

@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """Handle incoming WhatsApp messages from Twilio"""
    try:
        # Get form data from Twilio webhook
        form_data = await request.form()
        
        # Extract message details
        from_number = form_data.get("From", "")
        to_number = form_data.get("To", "")
        message_body = form_data.get("Body", "")
        message_sid = form_data.get("MessageSid", "")
        num_media = int(form_data.get("NumMedia", "0"))
        
        logger.info(f"📱 WhatsApp message from {from_number}: {message_body}")
        
        # Check if it's a WhatsApp message
        if not twilio_service.is_whatsapp_message(from_number):
            logger.warning(f"⚠ Non-WhatsApp message received: {from_number}")
            return Response(content="", media_type="text/plain")
        
        # Extract clean phone number for session
        clean_number = twilio_service.extract_whatsapp_number(from_number)
        
        # Get or create session for this WhatsApp number
        session = session_service.get_or_create_session(
            platform="whatsapp",
            whatsapp_number=clean_number
        )
        
        logger.info(f"💬 Session: {session.session_id}, Auth: {session.get_auth_status()}")
        
        # Track if this was a voice message for response format
        is_voice_input = False
        response_text = ""
        
        # Handle media messages (voice messages)
        if num_media > 0:
            # Process each media file
            for i in range(num_media):
                media_url = form_data.get(f"MediaUrl{i}", "")
                media_content_type = form_data.get(f"MediaContentType{i}", "")
                
                logger.info(f"🎵 Media {i+1}: {media_content_type} - {media_url}")
                
                # Handle voice messages
                if twilio_service.is_voice_message(media_content_type):
                    is_voice_input = True  # Mark as voice input
                    try:
                        logger.info("🎤 Processing voice message...")
                        
                        # Download the voice message
                        audio_data = await twilio_service.download_media(media_url)
                        logger.info(f"📥 Downloaded {len(audio_data)} bytes of audio data")
                        
                        # Convert audio format for speech recognition
                        input_format = twilio_service.get_audio_format_from_content_type(media_content_type)
                        logger.info(f"🔄 Converting audio from {input_format} to WAV...")
                        
                        wav_audio_data = twilio_service.convert_audio_for_speech_recognition(
                            audio_data, 
                            input_format
                        )
                        logger.info(f"✅ Converted to WAV: {len(wav_audio_data)} bytes")
                        
                        # Convert speech to text
                        user_text = speech_service.speech_to_text(wav_audio_data)
                        logger.info(f"🎤 Voice message transcribed: '{user_text}'")
                        
                        if user_text.strip():
                            # Process the transcribed text through voice controller
                            response_text = await voice_controller.process_text_message(session, user_text)
                        else:
                            response_text = "🎤 I couldn't understand your voice message clearly. Could you please try again or send a text message?"
                        
                    except Exception as voice_error:
                        logger.error(f"⚠ Voice message processing error: {str(voice_error)}")
                        # More specific error messages
                        if "Audio conversion not available" in str(voice_error):
                            response_text = "⚠ Audio conversion not available. Please install pydub or send a text message."
                        elif "Speech recognition failed" in str(voice_error):
                            response_text = "🎤 I couldn't understand your voice message clearly. Could you please try again or send a text message?"
                        elif "Audio file could not be read" in str(voice_error):
                            response_text = "🎤 There was an issue with your audio file format. Please try recording again or send a text message."
                        else:
                            response_text = "⚠ Sorry, I couldn't process your voice message. Please try sending a text message or try again."
                
                # Handle other media types (images, documents, etc.)
                else:
                    response_text = f"I received a {media_content_type} file. Currently, I can only process voice messages and text. Please send a voice message or text for assistance with municipal services."
        
        # Handle text messages
        elif message_body.strip():
            # Process the text message through voice assistant controller
            response_text = await voice_controller.process_text_message(session, message_body)
        
        # Handle empty messages
        else:
            response_text = "👋 Hello! How can I help you with municipal services today? You can send me a text message or voice message."
        
        # VOICE RESPONSE: If input was voice, respond with voice
        if is_voice_input and response_text:
            try:
                # Convert response text to speech
                audio_response = speech_service.text_to_speech(response_text)
                
                # Send voice response back to WhatsApp
                voice_response_result = await twilio_service.send_whatsapp_voice_response(
                    from_number, response_text, audio_response
                )
                
                if voice_response_result.get("success"):
                    logger.info("🎤 Voice response sent successfully")
                    return Response(content="", media_type="text/plain")
                else:
                    logger.warning("⚠️ Voice response failed, already handled in service")
                    return Response(content="", media_type="text/plain")
                    
            except Exception as tts_error:
                logger.error(f"⚠️ Text-to-speech error: {str(tts_error)}")
                # Send a simple text fallback
                formatted_response = twilio_service.format_whatsapp_message(
                    f"🎤 {response_text}", "whatsapp"
                )
                twiml_response = twilio_service.create_whatsapp_response(formatted_response)
                return Response(content=str(twiml_response), media_type="text/xml")
        
        # TEXT RESPONSE: For text inputs only (not voice fallback)
        elif not is_voice_input and response_text:
            # Format response for WhatsApp (clean and with emojis)
            formatted_response = twilio_service.format_whatsapp_message(response_text, "whatsapp")
            
            # Create WhatsApp response
            twiml_response = twilio_service.create_whatsapp_response(formatted_response)
            
            logger.info(f"🤖 WhatsApp response: {formatted_response[:100]}...")
            
            return Response(content=str(twiml_response), media_type="text/xml")
        
        # Empty response if no text to send
        else:
            return Response(content="", media_type="text/plain")
        
    except Exception as e:
        logger.error(f"⚠ WhatsApp webhook error: {str(e)}")
        import traceback
        logger.error(f"⚠ Full traceback: {traceback.format_exc()}")
        
        # Send error message to user
        error_response = twilio_service.create_whatsapp_response(
            "⚠ Sorry, I encountered a technical issue. Please try again in a moment."
        )
        return Response(content=str(error_response), media_type="text/xml")

@router.post("/voice")
async def voice_webhook(request: Request):
    """Handle incoming voice calls from Twilio"""
    try:
        # Get form data from Twilio webhook
        form_data = await request.form()
        
        # Extract call details
        call_sid = form_data.get("CallSid", "")
        from_number = form_data.get("From", "")
        to_number = form_data.get("To", "")
        call_status = form_data.get("CallStatus", "")
        
        logger.info(f"☎️ Voice call from {from_number}, CallSid: {call_sid}, Status: {call_status}")
        
        # Get or create session for this call
        session = session_service.get_or_create_session(
            platform="voice",
            call_sid=call_sid
        )
        
        # Set caller number for auto-authentication  
        session.caller_number = from_number
        
        # Create initial voice response with greeting
        greeting = "Welcome to the Municipal Voice Assistant! I can help you register complaints, check complaint status, and provide information about municipal services. How can I assist you today?"
        
        # Create TwiML response that gathers speech input
        twiml_response = twilio_service.create_voice_response(
            text=greeting,
            gather_input=True,
            gather_type="speech",
            timeout=10
        )
        
        logger.info(f"🤖 Voice greeting sent for session: {session.session_id}")
        
        return Response(content=str(twiml_response), media_type="text/xml")
        
    except Exception as e:
        logger.error(f"❌ Voice webhook error: {str(e)}")
        
        # Create error response
        error_response = twilio_service.create_voice_response(
            text="Sorry, I encountered a technical issue. Please call back in a moment."
        )
        return Response(content=str(error_response), media_type="text/xml")

@router.post("/voice/process")
async def process_voice_input(request: Request):
    """Process speech input from voice calls"""
    try:
        # Get form data from Twilio
        form_data = await request.form()
        
        # Extract speech and call details
        speech_result = form_data.get("SpeechResult", "")
        call_sid = form_data.get("CallSid", "")
        confidence = form_data.get("Confidence", "0")
        
        logger.info(f"🎙️ Speech input: {speech_result} (confidence: {confidence})")
        
        # Get session for this call
        session_id = f"voice_{call_sid}"
        session = session_service.get_session(session_id)
        
        if not session:
            # Create new session if not found
            session = session_service.get_or_create_session(
                platform="voice",
                call_sid=call_sid
            )
        
        # Check speech confidence
        confidence_score = float(confidence) if confidence else 0
        if confidence_score < 0.5:
            # Low confidence, ask user to repeat
            twiml_response = twilio_service.create_voice_response(
                text="I didn't catch that clearly. Could you please repeat?",
                gather_input=True,
                gather_type="speech",
                timeout=10
            )
            return Response(content=str(twiml_response), media_type="text/xml")
        
        if not speech_result.strip():
            # No speech detected
            twiml_response = twilio_service.create_voice_response(
                text="I didn't hear anything. Please speak clearly and try again.",
                gather_input=True,
                gather_type="speech",
                timeout=10
            )
            return Response(content=str(twiml_response), media_type="text/xml")
        
        # Process the speech through voice assistant controller
        response_text = await voice_controller.process_text_message(session, speech_result)
        
        # Determine if we need more input
        auth_status = session.get_auth_status()
        needs_input = (
            "please" in response_text.lower() or
            "what" in response_text.lower() or
            "how can" in response_text.lower() or
            "?" in response_text
        )
        
        # Create voice response
        if needs_input:
            twiml_response = twilio_service.create_voice_response(
                text=response_text,
                gather_input=True,
                gather_type="speech",
                timeout=15
            )
        else:
            # Final response, don't gather more input
            twiml_response = twilio_service.create_voice_response(
                text=response_text + " Thank you for using Municipal Voice Assistant. Have a great day!",
                gather_input=False
            )
        
        logger.info(f"🤖 Voice response: {response_text[:100]}...")
        
        return Response(content=str(twiml_response), media_type="text/xml")
        
    except Exception as e:
        logger.error(f"❌ Voice processing error: {str(e)}")
        
        error_response = twilio_service.create_voice_response(
            text="I encountered an error processing your request. Please call back later."
        )
        return Response(content=str(error_response), media_type="text/xml")

@router.get("/voice/twiml")
async def simple_voice_twiml(message: str = Query(...)):
    """Generate simple TwiML for outbound calls"""
    try:
        twiml_response = twilio_service.create_simple_voice_twiml(message)
        return Response(content=str(twiml_response), media_type="text/xml")
    except Exception as e:
        logger.error(f"❌ TwiML generation error: {str(e)}")
        error_response = twilio_service.create_simple_voice_twiml("Error generating message.")
        return Response(content=str(error_response), media_type="text/xml")

@router.post("/voice/status")
async def voice_call_status(request: Request):
    """Handle voice call status updates"""
    try:
        form_data = await request.form()
        
        call_sid = form_data.get("CallSid", "")
        call_status = form_data.get("CallStatus", "")
        call_duration = form_data.get("CallDuration", "0")
        
        logger.info(f"☎️ Call status update: {call_sid} - {call_status} (duration: {call_duration}s)")
        
        # Clean up session if call is completed
        if call_status in ["completed", "failed", "busy", "no-answer"]:
            voice_session_id = f"voice_{call_sid}"
            session_service.delete_session(voice_session_id)
            logger.info(f"🧹 Cleaned up voice session for call: {call_sid}")
        
        return Response(content="OK", media_type="text/plain")
        
    except Exception as e:
        logger.error(f"❌ Voice status error: {str(e)}")
        return Response(content="ERROR", media_type="text/plain")

@router.get("/config")
async def get_twilio_config():
    """Get Twilio webhook URLs for configuration"""
    try:
        if not twilio_service.is_configured():
            return {
                "configured": False,
                "message": "Twilio not configured. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables."
            }
        
        webhook_urls = twilio_service.get_webhook_urls()
        
        return {
            "configured": True,
            "webhook_urls": webhook_urls,
            "setup_instructions": {
                "whatsapp": f"Set WhatsApp sandbox webhook to: {webhook_urls['whatsapp_webhook']}",
                "voice": f"Set phone number webhook to: {webhook_urls['voice_webhook']}",
                "status_callback": f"Set status callback to: {webhook_urls['voice_status_callback']}"
            }
        }
    except Exception as e:
        return {
            "configured": False,
            "error": str(e)
        }

@router.post("/send-whatsapp")
async def send_whatsapp_message_endpoint(
    to_number: str = Form(...),
    message: str = Form(...)
):
    """Send WhatsApp message programmatically (for testing/admin use)"""
    try:
        if not twilio_service.is_configured():
            return {
                "success": False,
                "error": "Twilio not configured"
            }
        
        # Format message for WhatsApp
        formatted_message = twilio_service.format_whatsapp_message(message, "whatsapp")
        
        result = twilio_service.send_whatsapp_message(to_number, formatted_message)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Send WhatsApp error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/make-call")
async def make_outbound_call_endpoint(
    to_number: str = Form(...),
    message: str = Form(...)
):
    """Make outbound call programmatically (for testing/admin use)"""
    try:
        if not twilio_service.is_configured():
            return {
                "success": False,
                "error": "Twilio not configured"
            }
        
        result = twilio_service.make_outbound_call(to_number, message)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Make call error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }