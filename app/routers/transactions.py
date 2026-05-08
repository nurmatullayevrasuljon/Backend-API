from __future__ import annotations

import csv
import io
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from .. import models
from .dependencies import get_current_user

router = APIRouter()


@router.get("/")
def list_transactions(
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    search: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        start = now - timedelta(days=7)
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    q = db.query(models.Sale).options(joinedload(models.Sale.items).joinedload(models.SaleItem.product)).filter(
        models.Sale.sold_at >= start
    )
    if search:
        q = q.join(models.SaleItem).join(models.Product).filter(models.Product.name.ilike(f"%{search}%"))
    sales = q.order_by(models.Sale.sold_at.desc()).offset(skip).limit(limit).all()
    return [_format_sale(s) for s in sales]


@router.get("/stats")
def transaction_stats(
    period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        start = now - timedelta(days=7)
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_revenue = (
        db.query(func.sum(models.Sale.total_amount))
        .filter(models.Sale.status == models.SaleStatus.sold, models.Sale.sold_at >= start)
        .scalar()
        or 0.0
    )

    count = (
        db.query(func.count(models.Sale.id))
        .filter(models.Sale.sold_at >= start)
        .scalar()
        or 0
    )

    unpaid = (
        db.query(func.sum(models.Debtor.debt_amount - models.Debtor.paid_amount))
        .filter(models.Debtor.is_active == True)  # noqa: E712
        .scalar()
        or 0.0
    )

    return {
        "total_revenue": round(float(total_revenue), 2),
        "transaction_count": int(count),
        "unpaid_debt": round(float(unpaid), 2),
    }


@router.get("/export")
def export_transactions(
    period: str = Query("daily"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        start = now - timedelta(days=7)
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    sales = db.query(models.Sale).options(joinedload(models.Sale.items).joinedload(models.SaleItem.product)).filter(models.Sale.sold_at >= start).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Mahsulotlar", "Jami (UZS)", "To'lov turi", "Status", "Sana"])
    for s in sales:
        names = ", ".join(i.product.name for i in s.items if i.product)
        writer.writerow([
            s.id,
            names,
            s.total_amount,
            s.payment_type.value if s.payment_type else "",
            s.status.value if s.status else "",
            s.sold_at.strftime("%d.%m.%Y %H:%M") if s.sold_at else "",
        ])

    content = output.getvalue().encode("utf-8-sig")
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=tranzaksiyalar_{period}.csv"},
    )


def _format_sale(sale):
    items = []
    for item in sale.items:
        if item.product:
            items.append(
                {
                    "product_name": item.product.name,
                    "quantity": item.quantity,
                    "unit": item.product.unit.value if item.product.unit else None,
                    "unit_price": item.unit_price,
                    "total": item.total_price,
                }
            )
    return {
        "id": sale.id,
        "items": items,
        "total_amount": sale.total_amount,
        "payment_type": sale.payment_type.value if sale.payment_type else None,
        "status": sale.status.value if sale.status else None,
        "sold_at": sale.sold_at,
    }
