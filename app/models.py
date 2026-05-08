from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum

class UserRole(str, enum.Enum):
    admin = "admin"
    sales = "sales"
    manager = "manager"

class PaymentType(str, enum.Enum):
    cash = "cash"
    card = "card"

class SaleStatus(str, enum.Enum):
    sold = "sold"
    returned = "returned"

class DebtStatus(str, enum.Enum):
    overdue = "overdue"
    upcoming = "upcoming"
    normal = "normal"

class Department(str, enum.Enum):
    sales = "Savdo"
    it = "IT"
    finance = "Moliya"
    marketing = "Marketing"

class Unit(str, enum.Enum):
    piece = "dona"
    kg = "kg"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.sales)
    department = Column(Enum(Department), default=Department.sales)
    company_name = Column(String(100))
    avatar_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    two_factor_enabled = Column(Boolean, default=False)
    email_notifications = Column(Boolean, default=True)
    dark_mode = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    sales = relationship("Sale", back_populates="user")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    image_url = Column(String(500))
    cost_price = Column(Float, nullable=False)
    sell_price = Column(Float, nullable=False)
    quantity = Column(Float, default=0)
    unit = Column(Enum(Unit), default=Unit.piece)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    category = relationship("Category", back_populates="products")
    sale_items = relationship("SaleItem", back_populates="product")

    @property
    def profit_per_unit(self):
        return self.sell_price - self.cost_price

    @property
    def is_low_stock(self):
        return self.quantity <= 5

class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    payment_type = Column(Enum(PaymentType), default=PaymentType.cash)
    status = Column(Enum(SaleStatus), default=SaleStatus.sold)
    total_amount = Column(Float, default=0)
    notes = Column(Text)
    sold_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")

class SaleItem(Base):
    __tablename__ = "sale_items"
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    sale = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")

class Debtor(Base):
    __tablename__ = "debtors"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20))
    debt_amount = Column(Float, nullable=False)
    paid_amount = Column(Float, default=0)
    debt_date = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    @property
    def remaining_amount(self):
        return self.debt_amount - self.paid_amount

    @property
    def status(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        due = self.due_date
        if due.tzinfo is None:
            from datetime import timezone as tz
            due = due.replace(tzinfo=tz.utc)
        days_diff = (due - now).days
        if days_diff < 0:
            return DebtStatus.overdue
        elif days_diff <= 7:
            return DebtStatus.upcoming
        else:
            return DebtStatus.normal

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String(500), unique=True, index=True)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
