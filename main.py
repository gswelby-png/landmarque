from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import HTTPException
from datetime import date, datetime, timedelta, timezone
import random

from app.database import engine, SessionLocal
from app import models
from app.routers import driver, owner, admin
from app.auth import hash_password

models.Base.metadata.create_all(bind=engine)


def migrate():
    """Add new columns to existing tables without dropping data."""
    import logging
    from sqlalchemy import inspect, text
    log = logging.getLogger("parcark.migrate")
    try:
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("car_parks")]
        log.info(f"migrate(): existing car_parks columns: {columns}")
        with engine.connect() as conn:
            if "logo_url" not in columns:
                conn.execute(text("ALTER TABLE car_parks ADD COLUMN logo_url VARCHAR"))
                conn.commit()
                log.info("migrate(): added logo_url column")
            if "welcome_text" not in columns:
                conn.execute(text("ALTER TABLE car_parks ADD COLUMN welcome_text VARCHAR"))
                conn.commit()
                log.info("migrate(): added welcome_text column")
        # Backfill Shere Manor logo and welcome text if not set
        with engine.connect() as conn:
            conn.execute(text(
                "UPDATE car_parks SET logo_url = 'https://sheremanorestate.co.uk/images/default/logo_sticky.svg' "
                "WHERE slug = 'shere-manor' AND (logo_url IS NULL OR logo_url = '')"
            ))
            conn.execute(text(
                "UPDATE car_parks SET welcome_text = 'Welcome! We would be very grateful if you could make secure payment for parking on this app. Your contribution will go towards the upkeep of the public facilities that we provide around Shere and Holmbury Hill.' "
                "WHERE slug = 'shere-manor'"
            ))
            conn.commit()
    except Exception as e:
        log.error(f"migrate() failed: {e}")


def seed():
    db = SessionLocal()
    try:
        if db.query(models.AdminUser).first():
            return  # Already seeded

        # Admin
        db.add(models.AdminUser(
            email="admin@landmarque.co.uk",
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
            logo_url="https://sheremanorestate.co.uk/images/default/logo_sticky.svg",
            welcome_text="Welcome! We would be very grateful if you could make secure payment for parking on this app. Your contribution will go towards the upkeep of the public facilities that we provide around Shere and Holmbury Hill.",
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
        # Second car park
        cp2 = models.CarPark(
            owner_id=owner_obj.id,
            name="Holmbury Hill Car Park",
            slug="holmbury-hill",
            address="Holmbury St Mary, Surrey, RH5",
            tagline="Holmbury Hill — Surrey Hills",
            brand_primary="#1e3a1e",
            brand_accent="#8B3A2A",
            brand_text="#f5f0e8",
        )
        db.add(cp2)
        db.flush()
        db.add(models.PricingRule(car_park_id=cp2.id, day_type=models.DayType.weekday, hourly_rate_pence=300, max_hourly_hours=4, all_day_pence=1200, valid_from=date(2026, 1, 1)))
        db.add(models.PricingRule(car_park_id=cp2.id, day_type=models.DayType.weekend, hourly_rate_pence=350, max_hourly_hours=4, all_day_pence=1400, valid_from=date(2026, 1, 1)))
        db.commit()

        # Dummy transactions
        plates = ["AB12CDE","XY98ZZZ","LM45NOP","QR67STU","VW23ABC","EF89GHI",
                  "JK34LMN","PQ56RST","UV78WXY","CD11EFG","HI22JKL","MN33OPQ",
                  "RS44TUV","WX55YZA","BC66DEF","GH77IJK","LM88NOP","QR99STU",
                  "VW00XYZ","AB33CDE","XY44ZZZ","LM55NOP","QR66STU","VW77ABC",
                  "EF00GHI","JK11LMN","PQ22RST","UV33WXY","CD44EFG","HI55JKL"]
        now = datetime.now(timezone.utc)
        for i in range(38):
            is_all_day = random.choice([True, False, False])
            dur = None if is_all_day else random.choice([1, 2, 3, 4])
            amount = 1200 if is_all_day else 300 * dur
            commission = int(amount * 10 / 100)
            parked_at = now - timedelta(days=random.randint(1, 30), hours=random.randint(0, 10), minutes=random.randint(0, 59))
            db.add(models.Transaction(car_park_id=cp.id, number_plate=random.choice(plates), duration_hours=dur, is_all_day=is_all_day, amount_pence=amount, commission_pence=commission, owner_amount_pence=amount - commission, status=models.TransactionStatus.paid, parked_at=parked_at, expires_at=None if is_all_day else parked_at + timedelta(hours=dur)))
        for i in range(12):
            dur = random.choice([1, 2, 3, 4])
            amount = 300 * dur
            commission = int(amount * 10 / 100)
            parked_at = now - timedelta(minutes=random.randint(5, 90))
            db.add(models.Transaction(car_park_id=cp.id, number_plate=random.choice(plates), duration_hours=dur, is_all_day=False, amount_pence=amount, commission_pence=commission, owner_amount_pence=amount - commission, status=models.TransactionStatus.paid, parked_at=parked_at, expires_at=parked_at + timedelta(hours=dur)))
        db.commit()
    finally:
        db.close()


migrate()
seed()

# Backfill data that seed() can't set on existing DBs
from sqlalchemy import text as _text
with engine.connect() as _conn:
    _conn.execute(_text("UPDATE car_parks SET logo_url='https://sheremanorestate.co.uk/images/default/logo_sticky.svg' WHERE slug='shere-manor' AND (logo_url IS NULL OR logo_url='')"))
    _conn.execute(_text("UPDATE car_parks SET welcome_text='Welcome! We would be very grateful if you could make secure payment for parking on this app. Your contribution will go towards the upkeep of the public facilities that we provide around Shere and Holmbury Hill.' WHERE slug='shere-manor'"))
    _conn.commit()

app = FastAPI(title="LandMarque")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(driver.router)
app.include_router(owner.router)
app.include_router(admin.router)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/contact", response_class=HTMLResponse)
def contact_get(request: Request, sent: bool = False):
    return templates.TemplateResponse("contact.html", {"request": request, "sent": sent})


@app.post("/contact")
async def contact_post(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    organisation: str = Form(""),
    message: str = Form(""),
):
    # Log enquiry — email sending to be wired in later
    print(f"ENQUIRY | {name} | {email} | {organisation} | {message}")
    return RedirectResponse("/contact?sent=1", status_code=303)


@app.get("/payment")
def payment_redirect():
    return RedirectResponse("/payment/shere-manor", status_code=302)


@app.get("/receipt")
def receipt_redirect():
    return RedirectResponse("/receipt/shere-manor", status_code=302)




@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nDisallow: /admin/\nDisallow: /owner/\nDisallow: /check/\nAllow: /park/\nAllow: /\n"


@app.exception_handler(404)
async def not_found(request: Request, exc: HTTPException):
    return HTMLResponse(
        templates.get_template("errors/404.html").render({"request": request}),
        status_code=404,
    )


@app.exception_handler(503)
async def service_unavailable(request: Request, exc: HTTPException):
    return HTMLResponse(
        templates.get_template("errors/503.html").render({"request": request}),
        status_code=503,
    )
