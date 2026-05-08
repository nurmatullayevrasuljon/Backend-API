from __future__ import annotations

import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from .dependencies import get_current_user

router = APIRouter()
UPLOAD_DIR = "uploads/products"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(models.Category).all()


@router.post("/categories", response_model=schemas.CategoryOut, status_code=201)
def create_category(data: schemas.CategoryCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if db.query(models.Category).filter(models.Category.name == data.name).first():
        raise HTTPException(status_code=400, detail="Bu kategoriya allaqachon mavjud")
    cat = models.Category(name=data.name)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/categories/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Kategoriya topilmadi")
    db.delete(cat)
    db.commit()
    return {"message": "O'chirildi"}


@router.get("/", response_model=list[schemas.ProductOut])
def list_products(
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    low_stock: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = db.query(models.Product).filter(models.Product.is_active == True)  # noqa: E712
    if search:
        q = q.filter(models.Product.name.ilike(f"%{search}%"))
    if category_id:
        q = q.filter(models.Product.category_id == category_id)
    if low_stock:
        q = q.filter(models.Product.quantity <= 5)
    return q.order_by(models.Product.created_at.desc()).all()


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    p = db.query(models.Product).filter(models.Product.id == product_id, models.Product.is_active == True).first()  # noqa: E712
    if not p:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    return p


@router.post("/", response_model=schemas.ProductOut, status_code=201)
async def create_product(
    name: str = Form(...),
    category_id: Optional[int] = Form(None),
    cost_price: float = Form(...),
    sell_price: float = Form(...),
    quantity: float = Form(...),
    unit: str = Form("dona"),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if sell_price < cost_price:
        raise HTTPException(status_code=400, detail="Sotish narxi kelgan narxdan kam bo'lmasin")

    image_url = None
    if image and image.filename:
        ext = image.filename.rsplit(".", 1)[-1] if "." in image.filename else "jpg"
        filename = f"{uuid.uuid4()}.{ext}"
        path = os.path.join(UPLOAD_DIR, filename)
        with open(path, "wb") as f:
            shutil.copyfileobj(image.file, f)
        image_url = f"/{path}"

    unit_enum = models.Unit(unit) if unit in {u.value for u in models.Unit} else models.Unit.piece

    product = models.Product(
        name=name,
        category_id=category_id,
        cost_price=cost_price,
        sell_price=sell_price,
        quantity=quantity,
        unit=unit_enum,
        image_url=image_url,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int,
    data: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    p = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    for field, val in data.model_dump(exclude_none=True).items():
        setattr(p, field, val)

    db.commit()
    db.refresh(p)
    return p


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    p = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    p.is_active = False
    db.commit()
    return {"message": "Mahsulot o'chirildi"}


@router.get("/{product_id}/weekly-sales")
def weekly_sales(product_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    result = (
        db.query(func.sum(models.SaleItem.quantity))
        .join(models.Sale)
        .filter(
            models.SaleItem.product_id == product_id,
            models.Sale.status == models.SaleStatus.sold,
            models.Sale.sold_at >= week_ago,
        )
        .scalar()
    )
    return {"product_id": product_id, "weekly_sold": result or 0}
