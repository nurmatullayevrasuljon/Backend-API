from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..utils.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
    get_current_user,
)

router = APIRouter()


@router.post("/register", response_model=schemas.TokenSchema, status_code=201)
def register(data: schemas.RegisterSchema, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    exists = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Bu email allaqachon ro'yxatdan o'tgan")

    user = models.User(
        full_name=data.full_name.strip(),
        email=email,
        phone=data.phone.strip() if data.phone else None,
        company_name=data.company_name.strip() if data.company_name else None,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    refresh = create_refresh_token({"sub": user.id})
    _save_refresh_token(db, user.id, refresh)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@router.post("/login", response_model=schemas.TokenSchema)
def login(data: schemas.LoginSchema, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email.strip().lower()).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email yoki parol noto'g'ri")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Hisob faol emas")

    access = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    refresh = create_refresh_token({"sub": user.id})
    _save_refresh_token(db, user.id, refresh)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@router.post("/refresh", response_model=schemas.TokenSchema)
def refresh_token(data: schemas.RefreshSchema, db: Session = Depends(get_db)):
    payload = verify_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token kerak")

    user_id = int(payload["sub"])
    stored = db.query(models.RefreshToken).filter(
        models.RefreshToken.token == data.refresh_token,
        models.RefreshToken.user_id == user_id,
    ).first()
    if not stored:
        raise HTTPException(status_code=401, detail="Yaroqsiz refresh token")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    access = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    new_refresh = create_refresh_token({"sub": user.id})
    db.delete(stored)
    _save_refresh_token(db, user.id, new_refresh)
    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"}


@router.post("/logout")
def logout(
    data: schemas.RefreshSchema,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    stored = db.query(models.RefreshToken).filter(models.RefreshToken.token == data.refresh_token).first()
    if stored:
        db.delete(stored)
        db.commit()
    return {"message": "Muvaffaqiyatli chiqildi"}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == int(current_user["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    return user


@router.post("/change-password")
def change_password(
    data: schemas.ChangePasswordSchema,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == int(current_user["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    if not verify_password(data.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Eski parol noto'g'ri")
    user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"message": "Parol muvaffaqiyatli o'zgartirildi"}


def _save_refresh_token(db: Session, user_id: int, token: str):
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    rt = models.RefreshToken(user_id=user_id, token=token, expires_at=expires)
    db.add(rt)
    db.commit()
