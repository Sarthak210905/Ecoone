import cv2
import numpy as np
from typing import Dict, Any


class PhotoVerificationService:
    def __init__(self):
        try:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
        except:
            self.face_cascade = None
    
    async def verify_complaint_photo(self, image_data: bytes) -> Dict[str, Any]:
        """Verify complaint photo quality (not blurry, not blank)"""
        try:
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None or img.size == 0:
                return {
                    "valid": False,
                    "confidence": 0.0,
                    "reason": "Invalid or corrupted image"
                }
            
            # Check 1: Image not too dark
            brightness = cv2.mean(img)
            if brightness < 15:
                return {
                    "valid": False,
                    "confidence": 0.1,
                    "reason": "Image too dark - need better lighting"
                }
            
            # Check 2: Image not blurry (Laplacian variance)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            if laplacian_var < 80:
                return {
                    "valid": False,
                    "confidence": 0.2,
                    "reason": "Image too blurry - take a clear photo"
                }
            
            # Check 3: Has content
            hist = cv2.calcHist([gray],  None,  [0, 256])
            hist_entropy = -np.sum((hist / hist.sum()) * np.log2(hist / hist.sum() + 1e-10))
            
            if hist_entropy < 2.0:
                return {
                    "valid": False,
                    "confidence": 0.15,
                    "reason": "Image lacks detail - show issue clearly"
                }
            
            # Calculate confidence
            sharpness_score = min(laplacian_var / 500, 1.0)
            brightness_score = min(brightness / 200, 1.0)
            detail_score = min(hist_entropy / 7.0, 1.0)
            
            overall_confidence = (sharpness_score * 0.5 + brightness_score * 0.3 + detail_score * 0.2)
            
            return {
                "valid": True,
                "confidence": round(overall_confidence, 2),
                "reason": "Photo verification passed ✅"
            }
            
        except Exception as e:
            return {
                "valid": False,
                "confidence": 0.0,
                "reason": f"Verification error: {str(e)}"
            }
    
    async def verify_plantation_photo(self, image_data: bytes) -> Dict[str, Any]:
        """Verify tree/plant in photo"""
        try:
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None or img.size == 0:
                return {
                    "valid": False,
                    "green_percentage": 0.0,
                    "reason": "Invalid image"
                }
            
            # HSV for green detection
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            lower_green = np.array([25, 30, 30])
            upper_green = np.array([95, 255, 255])
            
            mask = cv2.inRange(hsv, lower_green, upper_green)
            green_pixels = cv2.countNonZero(mask)
            total_pixels = mask.size
            green_percentage = (green_pixels / total_pixels) * 100
            
            if green_percentage < 3:
                return {
                    "valid": False,
                    "green_percentage": round(green_percentage, 2),
                    "reason": "No green vegetation detected"
                }
            
            return {
                "valid": True,
                "green_percentage": round(green_percentage, 2),
                "verified_as_plantation": True,
                "message": "Tree/plant detected ✅"
            }
            
        except Exception as e:
            return {
                "valid": False,
                "reason": f"Error: {str(e)}"
            }


photo_verification_service = PhotoVerificationService()

def get_photo_verification_service() -> PhotoVerificationService:
    return photo_verification_service
