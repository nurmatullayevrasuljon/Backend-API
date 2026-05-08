from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from .models import DebtStatus, Department, PaymentType, SaleStatus, Unit, UserRole

# ─── AUTH ───────────────────────────────────────────
class RegisterSchema(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    password: str = Field(..., min_length=8)
    company_name: Optional[str] = None


class LoginSchema(BaseModel):
    email: EmailStr
    password: str


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshSchema(BaseModel):
    refresh_token: str


class ChangePasswordSchema(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


# ─── USER / SETTINGS ─────────────────────────────────
class UserUpdateSchema(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    department: Optional[Department] = None
    company_name: Optional[str] = None


class SystemSettingsSchema(BaseModel):
    email_notifications: Optional[bool] = None
    dark_mode: Optional[bool] = None


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str]
    role: UserRole
    department: Optional[Department]
    company_name: Optional[str]
    avatar_url: Optional[str]
    email_notifications: bool
    dark_mode: bool
    two_factor_enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── CATEGORY ────────────────────────────────────────
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CategoryOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


# ─── PRODUCT ─────────────────────────────────────────
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category_id: Optional[int] = None
    cost_price: float = Field(..., gt=0)
    sell_price: float = Field(..., gt=0)
    quantity: float = Field(..., ge=0)
    unit: Unit = Unit.piece


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    cost_price: Optional[float] = Field(None, gt=0)
    sell_price: Optional[float] = Field(None, gt=0)
    quantity: Optional[float] = Field(None, ge=0)
    unit: Optional[Unit] = None


class ProductOut(BaseModel):
    id: int
    name: str
    category: Optional[CategoryOut]
    image_url: Optional[str]
    cost_price: float
    sell_price: float
    profit_per_unit: float
    quantity: float
    unit: Unit
    is_low_stock: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── SALE ─────────────────────────────────────────────
class SaleItemCreate(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)


class SaleCreate(BaseModel):
    items: List[SaleItemCreate]
    payment_type: PaymentType = PaymentType.cash
    notes: Optional[str] = None


class SaleItemOut(BaseModel):
    id: int
    product_id: int
    product: Optional[ProductOut]
    quantity: float
    unit_price: float
    total_price: float

    class Config:
        from_attributes = True


class SaleOut(BaseModel):
    id: int
    payment_type: PaymentType
    status: SaleStatus
    total_amount: float
    notes: Optional[str]
    sold_at: datetime
    items: List[SaleItemOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class SaleReturn(BaseModel):
    sale_id: int


# ─── TRANSACTION ──────────────────────────────────────
class TransactionFilter(BaseModel):
    period: Optional[str] = "daily"
    search: Optional[str] = None


# ─── DEBTOR ──────────────────────────────────────────
class DebtorCreate(BaseModel):
    full_name: str = Field(..., min_length=2)
    phone: Optional[str] = None
    debt_amount: float = Field(..., gt=0)
    debt_date: datetime
    due_date: datetime
    notes: Optional[str] = None


class DebtorUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class DebtPaymentSchema(BaseModel):
    amount: float = Field(..., gt=0)


class DebtorOut(BaseModel):
    id: int
    full_name: str
    phone: Optional[str]
    debt_amount: float
    paid_amount: float
    remaining_amount: float
    status: DebtStatus
    debt_date: datetime
    due_date: datetime
    notes: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── DASHBOARD ────────────────────────────────────────
class DashboardStats(BaseModel):
    monthly_revenue: float
    monthly_revenue_growth: float
    daily_sales: float
    daily_sales_change: float
    monthly_profit: float
    inventory_balance: float
    overdue_payments: float
    overdue_count: int
    low_stock_count: int


class WeeklyTrend(BaseModel):
    day: str
    amount: float


class DailyRevenue(BaseModel):
    hour: str
    amount: float
