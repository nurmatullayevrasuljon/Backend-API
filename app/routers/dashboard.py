from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from .. import models, schemas
from .dependencies import get_current_user

router = APIRouter()


@router.get("/stats", response_model=schemas.DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    def revenue_in_range(start, end):
        result = (
            db.query(func.sum(models.Sale.total_amount))
            .filter(
                models.Sale.status == models.SaleStatus.sold,
                models.Sale.sold_at >= start,
                models.Sale.sold_at < end,
            )
            .scalar()
        )
        return result or 0.0

    monthly_revenue = revenue_in_range(month_start, now)
    prev_monthly_revenue = revenue_in_range(prev_month_start, month_start)
    growth = 0.0
    if prev_monthly_revenue > 0:
        growth = ((monthly_revenue - prev_monthly_revenue) / prev_monthly_revenue) * 100

    daily_sales = revenue_in_range(today_start, now)
    yesterday_sales = revenue_in_range(yesterday_start, today_start)
    daily_change = 0.0
    if yesterday_sales > 0:
        daily_change = ((daily_sales - yesterday_sales) / yesterday_sales) * 100

    monthly_profit = _calc_monthly_profit(db, month_start, now)

    inventory_balance = (
        db.query(func.sum(models.Product.cost_price * models.Product.quantity))
        .filter(models.Product.is_active == True)  # noqa: E712
        .scalar()
        or 0.0
    )

    overdue = (
        db.query(models.Debtor)
        .filter(models.Debtor.is_active == True, models.Debtor.due_date < now)  # noqa: E712
        .all()
    )
    overdue_total = sum(d.remaining_amount for d in overdue)

    low_stock = (
        db.query(models.Product)
        .filter(models.Product.is_active == True, models.Product.quantity <= 5)  # noqa: E712
        .count()
    )

    return schemas.DashboardStats(
        monthly_revenue=monthly_revenue,
        monthly_revenue_growth=round(growth, 2),
        daily_sales=daily_sales,
        daily_sales_change=round(daily_change, 2),
        monthly_profit=monthly_profit,
        inventory_balance=inventory_balance,
        overdue_payments=overdue_total,
        overdue_count=len(overdue),
        low_stock_count=low_stock,
    )


@router.get("/weekly-trend")
def get_weekly_trend(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    days_uz = ["Du", "Se", "Chor", "Pay", "Ju", "Sha", "Yak"]
    result = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        amount = (
            db.query(func.sum(models.Sale.total_amount))
            .filter(
                models.Sale.status == models.SaleStatus.sold,
                models.Sale.sold_at >= start,
                models.Sale.sold_at < end,
            )
            .scalar()
            or 0.0
        )
        result.append({"day": days_uz[day.weekday()], "date": day.strftime("%d.%m"), "amount": amount})
    return result


@router.get("/daily-revenue")
def get_daily_revenue(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = []
    for hour in range(0, now.hour + 1, 2):
        start = today_start + timedelta(hours=hour)
        end = start + timedelta(hours=2)
        amount = (
            db.query(func.sum(models.Sale.total_amount))
            .filter(
                models.Sale.status == models.SaleStatus.sold,
                models.Sale.sold_at >= start,
                models.Sale.sold_at < end,
            )
            .scalar()
            or 0.0
        )
        result.append({"hour": f"{hour:02d}:00", "amount": amount})
    return result


@router.get("/low-stock-alerts")
def get_low_stock_alerts(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    products = (
        db.query(models.Product)
        .filter(models.Product.is_active == True, models.Product.quantity <= 5)  # noqa: E712
        .all()
    )
    return [{"id": p.id, "name": p.name, "quantity": p.quantity, "unit": p.unit.value} for p in products]


@router.get("/overdue-payments")
def get_overdue_payments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    debtors = (
        db.query(models.Debtor)
        .filter(models.Debtor.is_active == True, models.Debtor.due_date < now)  # noqa: E712
        .all()
    )
    return [{"id": d.id, "name": d.full_name, "remaining": d.remaining_amount, "due_date": d.due_date} for d in debtors]


def _calc_monthly_profit(db: Session, start, end):
    sales = (
        db.query(models.Sale)
        .options(joinedload(models.Sale.items).joinedload(models.SaleItem.product))
        .filter(
            models.Sale.status == models.SaleStatus.sold,
            models.Sale.sold_at >= start,
            models.Sale.sold_at < end,
        )
        .all()
    )
    total_profit = 0.0
    for sale in sales:
        for item in sale.items:
            if item.product:
                profit = (item.unit_price - item.product.cost_price) * item.quantity
                total_profit += profit
    return total_profit
