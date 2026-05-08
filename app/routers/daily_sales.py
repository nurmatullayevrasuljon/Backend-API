from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from .. import models
from ..dependencies import get_current_user
from ._helpers import start_of_day

router = APIRouter()


def _range_for_period(period: str):
    today = date.today()
    if period == "weekly":
        return (
            datetime.combine(today - timedelta(days=6), datetime.min.time()),
            datetime.combine(today + timedelta(days=1), datetime.min.time()),
        )
    if period == "monthly":
        return (
            datetime.combine(today.replace(day=1), datetime.min.time()),
            datetime.combine(today + timedelta(days=1), datetime.min.time()),
        )
    return (
        datetime.combine(today, datetime.min.time()),
        datetime.combine(today + timedelta(days=1), datetime.min.time()),
    )


@router.get("/stats")
def daily_sales_stats(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    today_start = start_of_day()
    tomorrow_start = today_start + timedelta(days=1)
    thirty_days_ago = today_start - timedelta(days=30)

    today_revenue = (
        db.query(func.coalesce(func.sum(models.Sale.total_amount), 0.0))
        .filter(
            models.Sale.status == models.SaleStatus.sold,
            models.Sale.created_at >= today_start,
            models.Sale.created_at < tomorrow_start,
        )
        .scalar()
        or 0.0
    )

    unpaid_debt = (
        db.query(func.coalesce(func.sum(models.Debtor.debt_amount - models.Debtor.paid_amount), 0.0))
        .filter(
            models.Debtor.is_active == True,  # noqa: E712
            (models.Debtor.debt_amount - models.Debtor.paid_amount) > 0,
        )
        .scalar()
        or 0.0
    )

    today_transactions = (
        db.query(func.count(models.Sale.id))
        .filter(
            models.Sale.status == models.SaleStatus.sold,
            models.Sale.created_at >= today_start,
            models.Sale.created_at < tomorrow_start,
        )
        .scalar()
        or 0
    )

    month_revenue = (
        db.query(func.coalesce(func.sum(models.Sale.total_amount), 0.0))
        .filter(
            models.Sale.status == models.SaleStatus.sold,
            models.Sale.created_at >= thirty_days_ago,
            models.Sale.created_at < tomorrow_start,
        )
        .scalar()
        or 0.0
    )

    return {
        "today_revenue": round(float(today_revenue), 2),
        "unpaid_debt": round(float(unpaid_debt), 2),
        "today_transactions": int(today_transactions),
        "month_revenue": round(float(month_revenue), 2),
    }


@router.get("/transactions")
def daily_transactions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    start_dt, end_dt = _range_for_period(period)

    query = (
        db.query(models.Sale)
        .options(joinedload(models.Sale.items).joinedload(models.SaleItem.product))
        .filter(models.Sale.created_at >= start_dt, models.Sale.created_at < end_dt)
        .order_by(models.Sale.created_at.desc())
    )

    if status_filter:
        st = status_filter.strip().lower()
        if st in {"sotildi", "sold"}:
            query = query.filter(models.Sale.status == models.SaleStatus.sold)
        elif st in {"qaytarildi", "returned"}:
            query = query.filter(models.Sale.status == models.SaleStatus.returned)

    if search:
        term = f"%{search.strip()}%"
        query = query.join(models.SaleItem).join(models.Product).filter(models.Product.name.ilike(term))

    total = query.distinct().count()
    items = query.offset((page - 1) * limit).limit(limit).all()

    rows = []
    for sale in items:
        for item in sale.items:
            rows.append(
                {
                    "sale_id": sale.id,
                    "product": item.product.name if item.product else None,
                    "quantity": item.quantity,
                    "price": item.unit_price,
                    "total": item.total_price,
                    "created_at": sale.created_at,
                    "payment_type": sale.payment_type.value if sale.payment_type else None,
                    "status": sale.status.value if sale.status else None,
                }
            )

    return {
        "items": rows,
        "page": page,
        "limit": limit,
        "total": total,
        "period": period,
    }


@router.get("/export")
def export_transactions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
):
    start_dt, end_dt = _range_for_period(period)

    sales = (
        db.query(models.Sale)
        .options(joinedload(models.Sale.items).joinedload(models.SaleItem.product))
        .filter(models.Sale.created_at >= start_dt, models.Sale.created_at < end_dt)
        .order_by(models.Sale.created_at.desc())
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["sale_id", "product", "quantity", "price", "total", "created_at", "payment_type", "status"])

    for sale in sales:
        for item in sale.items:
            writer.writerow([
                sale.id,
                item.product.name if item.product else "",
                item.quantity,
                item.unit_price,
                item.total_price,
                sale.created_at.isoformat() if sale.created_at else "",
                sale.payment_type.value if sale.payment_type else "",
                sale.status.value if sale.status else "",
            ])

    buffer.seek(0)
    filename = f"{period}_transactions.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
