from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from .database import Base


class DayType(str, enum.Enum):
    weekday = "weekday"
    weekend = "weekend"
    bank_holiday = "bank_holiday"


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    # Commission ParCark takes, e.g. 10 = 10%
    commission_pct = Column(Integer, nullable=False, default=10)
    stripe_account_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    car_parks = relationship("CarPark", back_populates="owner")


class CarPark(Base):
    __tablename__ = "car_parks"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    name = Column(String, nullable=False)
    # URL slug: name.parcark.co.uk or /park/{slug}
    slug = Column(String, unique=True, nullable=False)
    address = Column(String, nullable=True)
    description = Column(String, nullable=True)
    tagline = Column(String, nullable=True)
    brand_primary = Column(String, nullable=False, default="#1a3a2a")   # header bg
    brand_accent = Column(String, nullable=False, default="#c8a84b")    # buttons
    brand_text = Column(String, nullable=False, default="#ffffff")      # header text
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner = relationship("Owner", back_populates="car_parks")
    pricing_rules = relationship("PricingRule", back_populates="car_park")
    transactions = relationship("Transaction", back_populates="car_park")


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id = Column(Integer, primary_key=True)
    car_park_id = Column(Integer, ForeignKey("car_parks.id"), nullable=False)
    day_type = Column(Enum(DayType), nullable=False)
    # Hourly rate in pence (e.g. 200 = £2.00/hr)
    hourly_rate_pence = Column(Integer, nullable=False)
    # Cap hourly charging at this many hours (e.g. 4 = max £8 at £2/hr)
    max_hourly_hours = Column(Integer, nullable=True)
    # Flat all-day rate in pence (e.g. 800 = £8.00)
    all_day_pence = Column(Integer, nullable=True)
    valid_from = Column(Date, nullable=False)
    # Null = open-ended (current rule)
    valid_to = Column(Date, nullable=True)

    car_park = relationship("CarPark", back_populates="pricing_rules")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    car_park_id = Column(Integer, ForeignKey("car_parks.id"), nullable=False)
    number_plate = Column(String, nullable=False)
    duration_hours = Column(Integer, nullable=True)   # None = all day
    is_all_day = Column(Boolean, default=False)
    amount_pence = Column(Integer, nullable=False)
    commission_pence = Column(Integer, nullable=False)
    owner_amount_pence = Column(Integer, nullable=False)
    stripe_payment_intent_id = Column(String, nullable=True)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.pending)
    parked_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    car_park = relationship("CarPark", back_populates="transactions")
