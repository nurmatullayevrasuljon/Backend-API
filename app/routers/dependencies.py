from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..utils.security import verify_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    payload = verify_token(credentials.credentials)

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Noto'g'ri token turi")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token ichida user topilmadi")

    user = db.query(models.User).filter(
        models.User.id == int(user_id),
        models.User.is_active == True,  # noqa: E712
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="Foydalanuvchi topilmadi yoki faol emas")

    return user


def get_admin_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Faqat adminlar uchun")
    return current_user
