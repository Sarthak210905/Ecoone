from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict

# Make sure to import your existing function
from utils import cloudinary_upload

# Optional: authentication dependency
from app.controllers.authcontroller import get_current_user

router = APIRouter()

@router.post("/upload-profile-photo")
async def upload_profile_photo_endpoint(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)  # if user auth required
) -> Dict:
    try:
        # Call your function to upload to Cloudinary
        image_url = await upload_profile_photo(file)
        # Return the image URL or any other info
        return {"success": True, "image_url": image_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
