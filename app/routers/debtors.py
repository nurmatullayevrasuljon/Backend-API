from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from .dependencies import get_current_user

router = APIRouter()


def _as_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/stats")
def debtor_stats(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    week_later = now + timedelta(days=7)
    month_ago = now - timedelta(days=30)

    all_debtors = db.query(models.Debtor).filter(models.Debtor.is_active == True).all()  # noqa: E712

    overdue = []
    upcoming = []

    for d in all_debtors:
        due = _as_aware(d.due_date)
        if due is None:
            continue
        if due < now:
            overdue.append(d)
        elif now <= due <= week_later:
            upcoming.append(d)

    overdue_total = sum(d.remaining_amount for d in overdue)
    upcoming_total = sum(d.remaining_amount for d in upcoming)

    collected = (
        db.query(func.sum(models.Debtor.paid_amount))
        .filter(
            models.Debtor.is_active == True,  # noqa: E712
            models.Debtor.updated_at >= month_ago,
        )
        .scalar()
        or 0.0
    )

    return {
        "overdue_total": overdue_total,
        "overdue_count": len(overdue),
        "upcoming_total": upcoming_total,
        "upcoming_count": len(upcoming),
        "monthly_collected": collected,
    }


@router.get("/", response_model=list[schemas.DebtorOut])
def list_debtors(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = db.query(models.Debtor).filter(models.Debtor.is_active == True)  # noqa: E712

    if search:
        q = q.filter(
            models.Debtor.full_name.ilike(f"%{search}%") |
            models.Debtor.phone.ilike(f"%{search}%")
        )

    debtors = q.order_by(models.Debtor.due_date.asc()).all()

    if status_filter and status_filter != "all":
        normalized = status_filter.strip().lower()
        filtered = []
        for d in debtors:
            st = d.status
            st_value = st.value if hasattr(st, "value") else str(st)
            if st_value.lower() == normalized:
                filtered.append(d)
        debtors = filtered

    return debtors


@router.get("/{debtor_id}", response_model=schemas.DebtorOut)
def get_debtor(debtor_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    d = db.query(models.Debtor).filter(
        models.Debtor.id == debtor_id,
        models.Debtor.is_active == True  # noqa: E712
    ).first()
    if not d:
        raise HTTPException(status_code=404, detail="Qarzdor topilmadi")
    return d


@router.post("/", response_model=schemas.DebtorOut, status_code=201)
def create_debtor(data: schemas.DebtorCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    debtor = models.Debtor(**data.model_dump())
    db.add(debtor)
    db.commit()
    db.refresh(debtor)
    return debtor


@router.put("/{debtor_id}", response_model=schemas.DebtorOut)
def update_debtor(
    debtor_id: int,
    data: schemas.DebtorUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    d = db.query(models.Debtor).filter(models.Debtor.id == debtor_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Qarzdor topilmadi")

    for field, val in data.model_dump(exclude_none=True).items():
        setattr(d, field, val)

    db.commit()
    db.refresh(d)
    return d


@router.post("/{debtor_id}/pay", response_model=schemas.DebtorOut)
def add_payment(
    debtor_id: int,
    data: schemas.DebtPaymentSchema,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    d = db.query(models.Debtor).filter(models.Debtor.id == debtor_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Qarzdor topilmadi")

    if data.amount > d.remaining_amount:
        raise HTTPException(
            status_code=400,
            detail=f"To'lov miqdori qarz summasidan oshib ketdi. Qolgan qarz: {d.remaining_amount}",
        )

    d.paid_amount += data.amount
    if d.remaining_amount <= 0:
        d.is_active = False

    db.commit()
    db.refresh(d)
    return d


@router.delete("/{debtor_id}")
def delete_debtor(debtor_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    d = db.query(models.Debtor).filter(models.Debtor.id == debtor_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Qarzdor topilmadi")
    d.is_active = False
    db.commit()
    return {"message": "Qarzdor o'chirildi"}


@router.get("/{debtor_id}/sms-reminder")
def send_sms_reminder(debtor_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    d = db.query(models.Debtor).filter(models.Debtor.id == debtor_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Qarzdor topilmadi")

    due = _as_aware(d.due_date)
    due_text = due.strftime("%d.%m.%Y") if due else d.due_date.strftime("%d.%m.%Y")

    message = (
        f"Hurmatli {d.full_name}, qarzingiz {d.remaining_amount:,.0f} UZS "
        f"muddati {due_text} gacha to'lanishi kerak."
    )

    return {
        "status": "simulated",
        "phone": d.phone,
        "message": message,
        "note": "Real SMS integratsiyasi uchun Eskiz.uz yoki Playmobile API ulaning",
    }