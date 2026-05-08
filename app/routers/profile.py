from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from .dependencies import get_current_user
from ..utils.files import delete_file, save_upload_file

router = APIRouter()


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    department: Optional[models.Department] = None
    company_name: Optional[str] = None


@router.get("")
def get_profile(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    sales_count = (
        db.query(func.count(models.Sale.id))
        .filter(models.Sale.user_id == current_user.id)
        .scalar()
        or 0
    )
    sales_total = (
        db.query(func.coalesce(func.sum(models.Sale.total_amount), 0.0))
        .filter(models.Sale.user_id == current_user.id)
        .scalar()
        or 0.0
    )
    customers_count = (
        db.query(func.count(models.Debtor.id))
        .filter(models.Debtor.is_active == True)  # noqa: E712
        .scalar()
        or 0
    )

    today_label = date.today().strftime("%a, %d %b")

    return {
        "profile": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone": current_user.phone,
            "avatar": current_user.avatar_url,
            "department": current_user.department.value if current_user.department else None,
            "company_name": current_user.company_name,
            "is_admin": current_user.role == models.UserRole.admin,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at,
        },
        "stats": {
            "customers_count": customers_count,
            "deals_count": sales_count,
            "sales_total": round(float(sales_total), 2),
            "today_label": today_label,
        },
    }


@router.put("")
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if payload.email and payload.email != current_user.email:
        exists = db.query(models.User).filter(models.User.email == payload.email).first()
        if exists:
            raise HTTPException(status_code=400, detail="Bu email allaqachon ishlatilmoqda")

    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.email is not None:
        current_user.email = payload.email.strip().lower()
    if payload.phone is not None:
        current_user.phone = payload.phone.strip()
    if payload.department is not None:
        current_user.department = payload.department
    if payload.company_name is not None:
        current_user.company_name = payload.company_name.strip()

    db.commit()
    db.refresh(current_user)
    return {"detail": "Profil yangilandi"}


@router.post("/avatar")
async def upload_profile_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.avatar_url:
        try:
            delete_file(current_user.avatar_url)
        except Exception:
            pass

    relative_path = await save_upload_file(file, subfolder="avatars")
    current_user.avatar_url = relative_path
    db.commit()
    return {"avatar": relative_path}
