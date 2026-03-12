"""
app/services/twilio_service.py - Fixed version with proper audio serving for WhatsApp
"""
import os
import httpx
import io
import tempfile
import time
import uuid
from typing import Optional, List
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from dotenv import load_dotenv
from urllib.parse import quote

try:
    from pydub import AudioSegment
    AUDIO_CONVERSION_AVAILABLE = True
except ImportError:
    AUDIO_CONVERSION_AVAILABLE = False
    print("⚠️ pydub not available. Install with: pip install pydub")

load_dotenv()

class TwilioService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
        self.client = None
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
    
    def is_configured(self) -> bool:
        """Check if Twilio is properly configured"""
        return all([self.account_sid, self.auth_token, self.client])
    
    # ==================== MEDIA METHODS ====================
    
    async def download_media(self, media_url: str) -> bytes:
        """Download media file from Twilio - handles redirects properly"""
        try:
            # Create HTTP client with Twilio authentication and follow redirects
            async with httpx.AsyncClient(follow_redirects=True) as client:
                # First request with authentication to get the actual media URL
                response = await client.get(
                    media_url,
                    auth=(self.account_sid, self.auth_token),
                    timeout=30.0  # Add timeout for large files
                )
                response.raise_for_status()
                return response.content
        except Exception as e:
            print(f"❌ Error downloading media: {str(e)}")
            raise e

    async def send_whatsapp_voice_response(self, to_number: str, text_response: str, audio_data: bytes) -> dict:
        """Send WhatsApp voice response with WhatsApp-compatible audio format"""
        if not self.is_configured():
            return {"success": False, "error": "Twilio not configured"}
        
        try:
            # Create public audio directory if it doesn't exist
            public_audio_dir = "static/audio"
            os.makedirs(public_audio_dir, exist_ok=True)
            
            # Convert audio to WhatsApp-compatible format first
            processed_audio, audio_format = self._convert_to_whatsapp_audio(audio_data)
            
            # Generate unique filename with appropriate extension
            audio_filename = f"voice_response_{uuid.uuid4().hex[:8]}.{audio_format}"
            audio_file_path = os.path.join(public_audio_dir, audio_filename)
            
            # Save audio file
            with open(audio_file_path, 'wb') as f:
                f.write(processed_audio)
            
            print(f"📁 Audio file saved: {audio_file_path} ({len(processed_audio)} bytes)")
            
            # Create public URL using the custom audio endpoint with explicit Content-Type
            base_url = os.getenv("BASE_URL", "http://localhost:8000")
            # Remove any trailing slashes and ensure proper URL format
            base_url = base_url.rstrip('/')
            # Use custom audio endpoint instead of static files for better MIME type handling
            media_url = f"{base_url}/audio/{audio_filename}"
            
            print(f"🔗 Media URL: {media_url}")
            
            # Send WhatsApp message with audio
            message_result = self.send_whatsapp_message(
                to_number=to_number,
                message="🎤 Voice response",  # Brief text with audio
                media_url=media_url
            )
            
            # Schedule cleanup of the audio file after 2 hours
            import threading
            import time
            
            def cleanup_file():
                time.sleep(7200)  # 2 hours
                try:
                    if os.path.exists(audio_file_path):
                        os.remove(audio_file_path)
                        print(f"🧹 Cleaned up audio file: {audio_filename}")
                except Exception as e:
                    print(f"⚠️ Failed to cleanup {audio_filename}: {e}")
            
            cleanup_thread = threading.Thread(target=cleanup_file, daemon=True)
            cleanup_thread.start()
            
            return message_result
            
        except Exception as e:
            print(f"❌ Voice response error: {str(e)}")
            # Fallback to text-only response
            return self.send_whatsapp_message(
                to_number=to_number,
                message=f"🎤 {text_response}"
            )

    def _convert_to_whatsapp_audio(self, audio_data: bytes) -> tuple[bytes, str]:
        """Convert audio data to WhatsApp-compatible format, returns (audio_bytes, format_extension)"""
        if not AUDIO_CONVERSION_AVAILABLE:
            print("⚠️ pydub not available, returning original audio as MP3")
            return audio_data, "mp3"
        
        try:
            # Try to load as audio segment
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_data))
            
            # Convert to WhatsApp-compatible format
            # WhatsApp supports: OGG (Opus), MP3, AMR
            # OGG with Opus codec is preferred for voice messages
            audio_segment = audio_segment.set_channels(1)  # Mono
            audio_segment = audio_segment.set_frame_rate(16000)  # 16kHz
            audio_segment = audio_segment.set_sample_width(2)  # 16-bit
            
            # Try OGG first (preferred for WhatsApp voice messages)
            try:
                ogg_buffer = io.BytesIO()
                audio_segment.export(
                    ogg_buffer, 
                    format="ogg", 
                    codec="libopus",
                    parameters=[
                        "-ac", "1",  # Mono
                        "-ar", "16000",  # 16kHz
                        "-b:a", "32k"  # 32kbps bitrate (good for voice)
                    ]
                )
                ogg_buffer.seek(0)
                ogg_data = ogg_buffer.read()
                
                if len(ogg_data) > 100:  # Valid audio file
                    print(f"🔧 Audio converted to OGG format: {len(ogg_data)} bytes")
                    return ogg_data, "ogg"
                else:
                    raise Exception("OGG conversion resulted in tiny file")
                    
            except Exception as ogg_error:
                print(f"⚠️ OGG conversion failed: {ogg_error}, trying MP3...")
                
                # Fallback to MP3
                mp3_buffer = io.BytesIO()
                audio_segment.export(
                    mp3_buffer,
                    format="mp3",
                    parameters=[
                        "-ac", "1",  # Mono
                        "-ar", "16000",  # 16kHz  
                        "-b:a", "32k"  # 32kbps bitrate
                    ]
                )
                mp3_buffer.seek(0)
                mp3_data = mp3_buffer.read()
                
                print(f"🔧 Audio converted to MP3 format: {len(mp3_data)} bytes")
                return mp3_data, "mp3"
            
        except Exception as e:
            print(f"⚠️ Audio conversion failed: {str(e)}, using original as MP3")
            return audio_data, "mp3"

    def convert_audio_for_speech_recognition(self, audio_data: bytes, input_format: str = "ogg") -> bytes:
        """Convert audio to WAV format for speech recognition"""
        if not AUDIO_CONVERSION_AVAILABLE:
            raise Exception("Audio conversion not available. Install pydub: pip install pydub")
        
        try:
            # Create audio segment from bytes
            audio_segment = AudioSegment.from_file(
                io.BytesIO(audio_data), 
                format=input_format
            )
            
            # Convert to WAV format with specific settings for speech recognition
            # Mono, 16kHz sample rate is optimal for most speech recognition services
            audio_segment = audio_segment.set_channels(1)  # Mono
            audio_segment = audio_segment.set_frame_rate(16000)  # 16kHz
            audio_segment = audio_segment.set_sample_width(2)  # 16-bit
            
            # Export to WAV bytes
            wav_buffer = io.BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            
            return wav_buffer.read()
            
        except Exception as e:
            print(f"❌ Error converting audio: {str(e)}")
            raise e
    
    def get_audio_format_from_content_type(self, content_type: str) -> str:
        """Get audio format from content type"""
        format_map = {
            "audio/ogg": "ogg",
            "audio/mpeg": "mp3",
            "audio/mp4": "mp4",
            "audio/m4a": "m4a",
            "audio/amr": "amr",
            "audio/wav": "wav",
            "audio/webm": "webm"
        }
        return format_map.get(content_type.lower(), "ogg")
    
    async def get_media_content_info(self, message_sid: str, media_sid: str) -> dict:
        """Get media content information from Twilio"""
        try:
            if not self.client:
                raise Exception("Twilio client not initialized")
            
            # Get media resource
            media = self.client.messages(message_sid).media(media_sid).fetch()
            
            return {
                "content_type": media.content_type,
                "date_created": media.date_created,
                "date_updated": media.date_updated,
                "uri": media.uri
            }
        except Exception as e:
            print(f"❌ Error getting media info: {str(e)}")
            return {}
    
    # ==================== WHATSAPP METHODS ====================
    
    def cleanup_old_audio_files(self, max_age_hours: int = 24):
        """Clean up old audio files from static directory"""
        try:
            public_audio_dir = "static/audio"
            
            if not os.path.exists(public_audio_dir):
                return
            
            current_time = time.time()
            for filename in os.listdir(public_audio_dir):
                if filename.startswith('voice_response_') and filename.endswith(('.wav', '.ogg', '.mp3')):
                    file_path = os.path.join(public_audio_dir, filename)
                    file_age_hours = (current_time - os.path.getmtime(file_path)) / 3600
                    
                    if file_age_hours > max_age_hours:
                        try:
                            os.remove(file_path)
                            print(f"🧹 Cleaned up old audio file: {filename}")
                        except Exception as e:
                            print(f"⚠️ Failed to clean up {filename}: {e}")
        except Exception as e:
            print(f"⚠️ Error during audio cleanup: {e}")

    def create_whatsapp_response(self, message: str, media_url: Optional[str] = None) -> MessagingResponse:
        """Create a WhatsApp response message"""
        resp = MessagingResponse()
        msg = resp.message()
        
        # Split long messages into chunks for WhatsApp
        if len(message) > 1600:  # WhatsApp has a 1600 character limit
            chunks = self._split_message(message, 1600)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    msg.body(chunk)
                else:
                    # Create additional message elements for subsequent chunks
                    additional_msg = resp.message()
                    additional_msg.body(chunk)
        else:
            msg.body(message)
        
        # Add media if provided
        if media_url:
            msg.media(media_url)
        
        return resp
    
    def send_whatsapp_message(self, to_number: str, message: str, media_url: Optional[str] = None) -> dict:
        """Send a WhatsApp message programmatically"""
        if not self.is_configured():
            return {"success": False, "error": "Twilio not configured"}
        
        try:
            # Ensure WhatsApp format
            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"
            
            message_kwargs = {
                "body": message,
                "from_": self.whatsapp_number,
                "to": to_number
            }
            
            if media_url:
                message_kwargs["media_url"] = [media_url]
            
            message = self.client.messages.create(**message_kwargs)
            
            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status
            }
        except Exception as e:
            print(f"❌ WhatsApp send error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def format_whatsapp_message(self, text: str, platform: str = "whatsapp") -> str:
        """Format message for WhatsApp with emojis and proper formatting"""
        if platform != "whatsapp":
            return text
        
        # Clean up any leaked debug information first
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            # Skip debug/internal lines
            if any(skip_phrase in line.lower() for skip_phrase in [
                'current session authentication',
                'authentication status:',
                '- authenticated:',
                '- auth step:',
                '- pending mobile:',
                '- user id:',
                '- platform:',
                'authentication rules:',
                'previous conversation context:',
                'current user message:',
                'internal context'
            ]):
                continue
            
            # Skip numbered authentication rules
            if line_stripped.lower().startswith(('1.', '2.', '3.', '4.', '5.', '6.')) and ('auth' in line.lower() or 'otp' in line.lower()):
                continue
                
            # Skip emoji conversation markers
            if line_stripped.startswith(('👤 ', '🤖 ')):
                continue
            
            if line_stripped:
                cleaned_lines.append(line)
        
        # Reconstruct the message
        formatted = '\n'.join(cleaned_lines).strip()
        
        if not formatted:
            return "How can I help you with municipal services today?"
        
        # Add appropriate emojis and formatting for WhatsApp
        emoji_replacements = {
            "Welcome": "🏛️ *Welcome*",
            "OTP sent": "📱 *OTP sent*",
            "logged in": "✅ *logged in*",
            "complaint": "📋 complaint",
            "registered": "✅ *registered*",
            "error": "❌ Error",
            "Error": "❌ Error", 
            "success": "✅ Success",
            "Success": "✅ Success",
            "ID": "*ID*",
            "status": "📊 *status*",
            "Status": "📊 *Status*"
        }
        
        for phrase, replacement in emoji_replacements.items():
            formatted = formatted.replace(phrase, replacement)
        
        # Format complaint IDs in bold
        import re
        formatted = re.sub(r'\b([A-Z0-9]{8,})\b', r'*\1*', formatted)
        
        return formatted
    
    # ==================== VOICE CALL METHODS ====================
    
    def create_voice_response(self, text: str, gather_input: bool = False, 
                             gather_type: str = "speech", timeout: int = 5) -> VoiceResponse:
        """Create a voice response with TwiML"""
        response = VoiceResponse()
        
        if gather_input:
            gather = Gather(
                input=gather_type,  # 'speech', 'dtmf', or 'speech dtmf'
                timeout=timeout,
                action='/api/twilio/voice/process',  # Where to send the gathered input
                method='POST',
                speechTimeout='auto',
                language='en-IN'  # Indian English
            )
            gather.say(text, voice='alice', language='en-IN')
            response.append(gather)
            
            # Fallback if no input received
            response.say("I didn't receive any input. Please call back when you're ready.")
        else:
            response.say(text, voice='alice', language='en-IN')
        
        return response
    
    def make_outbound_call(self, to_number: str, message: str) -> dict:
        """Make an outbound call with a message"""
        if not self.is_configured():
            return {"success": False, "error": "Twilio not configured"}
        
        try:
            # Encode message for safe URL usage
            encoded_message = quote(message)
            twiml_url = f"{os.getenv('BASE_URL', '')}/api/twilio/voice/twiml?message={encoded_message}"
            
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=twiml_url,
                method='GET'
            )
            
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_simple_voice_twiml(self, message: str) -> VoiceResponse:
        """Create simple voice TwiML for outbound calls"""
        response = VoiceResponse()
        response.say(message, voice='alice', language='en-IN')
        return response
    
    # ==================== UTILITY METHODS ====================
    
    def _split_message(self, message: str, max_length: int) -> List[str]:
        """Split long messages into chunks for WhatsApp"""
        if len(message) <= max_length:
            return [message]
        
        chunks = []
        current_chunk = ""
        
        # Split by sentences first
        sentences = message.split('. ')
        
        for sentence in sentences:
            if len(current_chunk + sentence) <= max_length - 10:  # Leave some buffer
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def extract_whatsapp_number(self, from_number: str) -> str:
        """Extract clean phone number from WhatsApp format"""
        if from_number.startswith("whatsapp:"):
            return from_number.replace("whatsapp:", "")
        return from_number
    
    def is_whatsapp_message(self, from_number: str) -> bool:
        """Check if message is from WhatsApp"""
        return from_number.startswith("whatsapp:")
    
    def is_voice_message(self, media_content_type: str) -> bool:
        """Check if the media is a voice message"""
        voice_types = [
            "audio/ogg",
            "audio/mpeg", 
            "audio/mp4",
            "audio/amr",
            "audio/wav"
        ]
        return media_content_type.lower() in voice_types
    
    def get_webhook_urls(self) -> dict:
        """Get webhook URLs for Twilio configuration"""
        base_url = os.getenv("BASE_URL", "https://your-domain.ngrok.io")
        return {
            "whatsapp_webhook": f"{base_url}/api/twilio/whatsapp",
            "voice_webhook": f"{base_url}/api/twilio/voice",
            "voice_status_callback": f"{base_url}/api/twilio/voice/status"
        }

# Global instance
twilio_service = TwilioService()

def get_twilio_service() -> TwilioService:
    """Get the global Twilio service instance"""
    return twilio_service