from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from .. import models, schemas
from .dependencies import get_current_user

router = APIRouter()


@router.get("/today", response_model=list[schemas.SaleOut])
def today_sales(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(models.Sale)
        .options(joinedload(models.Sale.items).joinedload(models.SaleItem.product))
        .filter(models.Sale.sold_at >= today)
        .order_by(models.Sale.sold_at.desc())
        .all()
    )


@router.get("/today/revenue")
def today_revenue(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total = (
        db.query(func.sum(models.Sale.total_amount))
        .filter(
            models.Sale.status == models.SaleStatus.sold,
            models.Sale.sold_at >= today,
        )
        .scalar()
        or 0.0
    )
    return {"total_revenue": round(float(total), 2)}


@router.get("/search-product")
def search_product(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    products = (
        db.query(models.Product)
        .filter(
            models.Product.is_active == True,  # noqa: E712
            models.Product.name.ilike(f"%{q}%"),
            models.Product.quantity > 0,
        )
        .limit(10)
        .all()
    )
    return products


@router.post("/", response_model=schemas.SaleOut, status_code=201)
def create_sale(
    data: schemas.SaleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sale = models.Sale(
        user_id=current_user.id,
        payment_type=data.payment_type,
        notes=data.notes,
    )
    db.add(sale)
    db.flush()

    total = 0.0
    for item_data in data.items:
        product = (
            db.query(models.Product)
            .filter(models.Product.id == item_data.product_id)
            .with_for_update()
            .first()
        )
        if not product:
            raise HTTPException(status_code=404, detail=f"Mahsulot #{item_data.product_id} topilmadi")
        if product.quantity < item_data.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"'{product.name}' uchun yetarli miqdor yo'q. Mavjud: {product.quantity}",
            )

        product.quantity -= item_data.quantity
        line_total = item_data.quantity * product.sell_price
        total += line_total
        sale_item = models.SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity=item_data.quantity,
            unit_price=product.sell_price,
            total_price=line_total,
        )
        db.add(sale_item)

    sale.total_amount = total
    db.commit()
    db.refresh(sale)
    return sale


@router.post("/{sale_id}/return", response_model=schemas.SaleOut)
def return_sale(
    sale_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sale = (
        db.query(models.Sale)
        .options(joinedload(models.Sale.items).joinedload(models.SaleItem.product))
        .filter(models.Sale.id == sale_id)
        .first()
    )
    if not sale:
        raise HTTPException(status_code=404, detail="Sotuv topilmadi")
    if sale.status == models.SaleStatus.returned:
        raise HTTPException(status_code=400, detail="Bu sotuv allaqachon qaytarilgan")

    sale.status = models.SaleStatus.returned
    for item in sale.items:
        if item.product:
            item.product.quantity += item.quantity
    db.commit()
    db.refresh(sale)
    return sale


@router.get("/", response_model=list[schemas.SaleOut])
def list_sales(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = db.query(models.Sale).options(joinedload(models.Sale.items).joinedload(models.SaleItem.product))
    if status:
        try:
            q = q.filter(models.Sale.status == models.SaleStatus(status))
        except Exception:
            raise HTTPException(status_code=400, detail="Noto'g'ri status")
    return q.order_by(models.Sale.sold_at.desc()).offset(skip).limit(limit).all()
