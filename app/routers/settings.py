from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from .dependencies import get_current_user
from ..utils.files import delete_file, save_upload_file

router = APIRouter()

UPLOAD_DIR = Path("uploads/avatars")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@router.get("/profile", response_model=schemas.UserOut)
def get_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return current_user


@router.put("/profile", response_model=schemas.UserOut)
def update_profile(
    data: schemas.UserUpdateSchema,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.email and data.email != current_user.email:
        exists = db.query(models.User).filter(models.User.email == data.email).first()
        if exists:
            raise HTTPException(status_code=400, detail="Bu email allaqachon ishlatilmoqda")

    update_data = data.model_dump(exclude_none=True)
    for field, val in update_data.items():
        setattr(current_user, field, val)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/profile/avatar", response_model=schemas.UserOut)
async def upload_avatar(
    avatar: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if avatar.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Faqat JPG, PNG yoki WebP rasm yuklash mumkin")

    if current_user.avatar_url:
        try:
            delete_file(current_user.avatar_url)
        except Exception:
            pass

    relative_path = await save_upload_file(avatar, subfolder="avatars")
    current_user.avatar_url = relative_path
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/system", response_model=schemas.UserOut)
def update_system_settings(
    data: schemas.SystemSettingsSchema,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.email_notifications is not None:
        current_user.email_notifications = data.email_notifications
    if data.dark_mode is not None:
        current_user.dark_mode = data.dark_mode

    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/security/2fa")
def toggle_2fa(
    enabled: bool,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.two_factor_enabled = enabled
    db.commit()
    return {
        "two_factor_enabled": enabled,
        "message": f"2FA {'yoqildi' if enabled else 'o‘chirildi'}",
    }
