from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import models as models


def utcnow() -> datetime:
    return datetime.utcnow()


def start_of_day(dt: Optional[datetime] = None) -> datetime:
    dt = dt or utcnow()
    return datetime(dt.year, dt.month, dt.day)


def start_of_month(dt: Optional[datetime] = None) -> datetime:
    dt = dt or utcnow()
    return datetime(dt.year, dt.month, 1)


def start_of_next_month(dt: Optional[datetime] = None) -> datetime:
    dt = dt or utcnow()
    if dt.month == 12:
        return datetime(dt.year + 1, 1, 1)
    return datetime(dt.year, dt.month + 1, 1)


def prev_month_range(dt: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    dt = dt or utcnow()
    first_this_month = start_of_month(dt)
    if dt.month == 1:
        first_prev_month = datetime(dt.year - 1, 12, 1)
    else:
        first_prev_month = datetime(dt.year, dt.month - 1, 1)
    return first_prev_month, first_this_month


def pct_change(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0 if current <= 0 else 100.0
    return round(((current - previous) / previous) * 100.0, 2)


def debtor_status(debtor: models.Debtor) -> str:
    now = utcnow()
    remaining = (debtor.debt_amount or 0) - (debtor.paid_amount or 0)
    due = debtor.due_date
    if due and due.tzinfo is None:
        due = due.replace(tzinfo=now.tzinfo)

    if remaining <= 0:
        return "oddiy"
    if due and due < now:
        return "muddati_otgan"
    if due and due <= now + timedelta(days=7):
        return "yaqinlashib_qolgan"
    return "oddiy"


def product_status(product: models.Product) -> str:
    if not product.is_active:
        return "inactive"
    if product.quantity <= 5:
        return "low_stock"
    return "active"


def serialize_category(category: models.Category) -> Dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "created_at": category.created_at,
    }


def serialize_product(product: models.Product) -> Dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "category": serialize_category(product.category) if product.category else None,
        "category_id": product.category_id,
        "image_url": product.image_url,
        "cost_price": product.cost_price,
        "sell_price": product.sell_price,
        "profit_per_unit": round((product.sell_price or 0) - (product.cost_price or 0), 2),
        "quantity": product.quantity,
        "unit": product.unit.value if getattr(product, "unit", None) else None,
        "is_low_stock": product.quantity <= 5,
        "is_active": product.is_active,
        "status": product_status(product),
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


def serialize_sale_item(item: models.SaleItem) -> Dict[str, Any]:
    return {
        "id": item.id,
        "product_id": item.product_id,
        "product_name": item.product.name if item.product else None,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "total_price": item.total_price,
    }


def serialize_sale(sale: models.Sale) -> Dict[str, Any]:
    return {
        "id": sale.id,
        "user_id": sale.user_id,
        "user_name": sale.user.full_name if sale.user else None,
        "payment_type": sale.payment_type.value if getattr(sale, "payment_type", None) else None,
        "total_amount": sale.total_amount,
        "status": sale.status.value if getattr(sale, "status", None) else None,
        "notes": sale.notes,
        "created_at": sale.created_at,
        "items": [serialize_sale_item(i) for i in sale.items] if sale.items else [],
    }


def serialize_debtor(debtor: models.Debtor) -> Dict[str, Any]:
    remaining = round((debtor.debt_amount or 0) - (debtor.paid_amount or 0), 2)
    return {
        "id": debtor.id,
        "full_name": debtor.full_name,
        "phone": debtor.phone,
        "debt_amount": debtor.debt_amount,
        "paid_amount": debtor.paid_amount,
        "remaining_debt": remaining,
        "debt_date": debtor.debt_date,
        "due_date": debtor.due_date,
        "notes": debtor.notes,
        "sms_sent": getattr(debtor, "sms_sent", False),
        "is_deleted": getattr(debtor, "is_deleted", False),
        "status": debtor_status(debtor),
        "created_at": debtor.created_at,
        "updated_at": debtor.updated_at,
    }
