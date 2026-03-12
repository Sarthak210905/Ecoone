"""
app/services/speech_service.py - Speech Recognition & Synthesis Service
"""
import os
import uuid
import speech_recognition as sr
import pyttsx3
from io import BytesIO
from fastapi import HTTPException

class SpeechService:
    def __init__(self):
        self.temp_dir = "temp_audio"
        self.ensure_temp_dir()
    
    def ensure_temp_dir(self):
        """Ensure temp directory exists"""
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
    
    def speech_to_text(self, audio_data: bytes) -> str:
        """Convert speech to text using speech_recognition library"""
        try:
            # Initialize recognizer
            r = sr.Recognizer()
            
            # Convert bytes to AudioFile
            audio_file = sr.AudioFile(BytesIO(audio_data))
            
            with audio_file as source:
                # Adjust for ambient noise
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.record(source)
            
            # Recognize speech using Google's API with Indian English
            text = r.recognize_google(audio, language='en-IN')
            return text
        except sr.UnknownValueError:
            raise HTTPException(status_code=400, detail="Could not understand audio. Please speak clearly.")
        except sr.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Speech recognition service error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Speech recognition failed: {str(e)}")
    
    def text_to_speech(self, text: str) -> bytes:
        """Convert text to speech and return audio bytes (Hinglish/Indian accent preferred)"""
        try:
            # Initialize TTS engine
            engine = pyttsx3.init()
            
            # Configure voice settings for Hinglish/Indian English
            voices = engine.getProperty('voices')
            preferred_indian_voices = ["heera", "ravi", "india", "hinglish", "en-in"]
            
            selected = None
            for voice in voices:
                if any(keyword in voice.name.lower() for keyword in preferred_indian_voices):
                    engine.setProperty('voice', voice.id)
                    selected = voice
                    break
            
            # Fallback: female voice, then first available
            if not selected:
                for voice in voices:
                    if 'female' in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        selected = voice
                        break
            if not selected and voices:
                engine.setProperty('voice', voices[0].id)
            
            engine.setProperty('rate', 160)   # slightly slower, natural
            engine.setProperty('volume', 0.9) # clear volume
            
            # Create a unique temp file name
            temp_file = os.path.join(self.temp_dir, f"temp_audio_{uuid.uuid4().hex[:8]}.wav")
            
            # Save to file
            engine.save_to_file(text, temp_file)
            engine.runAndWait()
            
            # Read the file and return bytes
            with open(temp_file, 'rb') as f:
                audio_data = f.read()
            
            # Clean up temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)
            
            return audio_data
        except Exception as e:
            print(f"TTS Error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Text-to-speech failed: {str(e)}")
    
    def cleanup_temp_files(self):
        """Clean up old temporary audio files"""
        try:
            for filename in os.listdir(self.temp_dir):
                if filename.startswith('temp_audio_') and filename.endswith('.wav'):
                    file_path = os.path.join(self.temp_dir, filename)
                    try:
                        os.remove(file_path)
                        print(f"🧹 Cleaned up temp file: {filename}")
                    except Exception as e:
                        print(f"❌ Failed to clean up {filename}: {e}")
        except Exception as e:
            print(f"❌ Error during temp file cleanup: {e}")

# Global instance
speech_service = SpeechService()

def get_speech_service() -> SpeechService:
    """Get the global speech service instance"""
    return speech_service
