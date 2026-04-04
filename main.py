from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from datetime import date

from app.database import engine, SessionLocal
from app import models
from app.routers import driver, owner, admin
from app.auth import hash_password

models.Base.metadata.create_all(bind=engine)


def seed():
    db = SessionLocal()
    try:
        if db.query(models.AdminUser).first():
            return  # Already seeded

        # Admin
        db.add(models.AdminUser(
            email="admin@parcark.co.uk",
            password_hash=hash_password("admin123"),
        ))

        # Owner
        owner_obj = models.Owner(
            name="Shere Manor Estate",
            email="demo@estate.co.uk",
            password_hash=hash_password("demo123"),
            commission_pct=10,
        )
        db.add(owner_obj)
        db.flush()

        # Car park
        cp = models.CarPark(
            owner_id=owner_obj.id,
            name="Walking Bottom Car Park",
            slug="shere-manor",
            address="Shere, Surrey, GU5",
            tagline="Welcome to Shere Manor Estate",
            brand_primary="#1e3a1e",
            brand_accent="#8B3A2A",
            brand_text="#f5f0e8",
        )
        db.add(cp)
        db.flush()

        # Pricing
        db.add(models.PricingRule(
            car_park_id=cp.id,
            day_type=models.DayType.weekday,
            hourly_rate_pence=300,
            max_hourly_hours=4,
            all_day_pence=1200,
            valid_from=date(2026, 1, 1),
        ))
        db.add(models.PricingRule(
            car_park_id=cp.id,
            day_type=models.DayType.weekend,
            hourly_rate_pence=300,
            max_hourly_hours=4,
            all_day_pence=1200,
            valid_from=date(2026, 1, 1),
        ))
        db.commit()
    finally:
        db.close()


seed()

app = FastAPI(title="ParCark")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(driver.router)
app.include_router(owner.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return RedirectResponse("/admin/login")
