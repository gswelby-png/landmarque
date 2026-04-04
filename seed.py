"""
Run once to create the admin user and a demo owner + car park.
  python seed.py
"""
from dotenv import load_dotenv
load_dotenv()

from datetime import date
from app.database import SessionLocal, engine
from app import models
from app.auth import hash_password

models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Admin
if not db.query(models.AdminUser).filter_by(email="admin@landmarque.co.uk").first():
    db.add(models.AdminUser(
        email="admin@landmarque.co.uk",
        password_hash=hash_password("admin123"),
    ))
    print("Created admin: admin@landmarque.co.uk / admin123")

# Demo owner
owner = db.query(models.Owner).filter_by(email="demo@estate.co.uk").first()
if not owner:
    owner = models.Owner(
        name="Demo Estate",
        email="demo@estate.co.uk",
        password_hash=hash_password("demo123"),
        commission_pct=10,
    )
    db.add(owner)
    db.flush()
    print("Created owner: demo@estate.co.uk / demo123")

# Demo car park
cp = db.query(models.CarPark).filter_by(slug="demo-estate").first()
if not cp:
    cp = models.CarPark(
        owner_id=owner.id,
        name="Demo Estate Car Park",
        slug="demo-estate",
        address="Surrey, UK",
        description="Main visitor car park",
    )
    db.add(cp)
    db.flush()
    print("Created car park: /park/demo-estate")

# Pricing rules
if not db.query(models.PricingRule).filter_by(car_park_id=cp.id).first():
    db.add(models.PricingRule(
        car_park_id=cp.id,
        day_type=models.DayType.weekday,
        hourly_rate_pence=200,
        max_hourly_hours=4,
        all_day_pence=800,
        valid_from=date(2026, 1, 1),
    ))
    db.add(models.PricingRule(
        car_park_id=cp.id,
        day_type=models.DayType.weekend,
        hourly_rate_pence=300,
        max_hourly_hours=4,
        all_day_pence=1000,
        valid_from=date(2026, 1, 1),
    ))
    print("Created pricing rules (weekday £2/hr, weekend £3/hr)")

db.commit()
db.close()
print("\nDone. Run: uvicorn main:app --reload")
