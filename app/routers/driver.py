from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta, timezone
import stripe
import os

from ..database import get_db
from ..models import CarPark, Transaction, TransactionStatus
from ..pricing import get_active_rule, calculate_price, build_duration_options

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/payment/{slug}", response_class=HTMLResponse)
def payment_page(slug: str, request: Request, db: Session = Depends(get_db)):
    car_park = db.query(CarPark).filter(CarPark.slug == slug).first()
    estate_name = car_park.owner.name if car_park else ""
    car_park_name = car_park.name if car_park else ""
    logo_url = (getattr(car_park, "logo_url", None) or "") if car_park else ""
    accent = (car_park.brand_accent or "#8B3A2A") if car_park else "#8B3A2A"
    return templates.TemplateResponse("driver/payment_mockup.html", {
        "request": request,
        "slug": slug,
        "estate_name": estate_name,
        "car_park_name": car_park_name,
        "logo_url": logo_url,
        "brand": {"accent": accent},
    })


@router.get("/receipt/{slug}", response_class=HTMLResponse)
def receipt_page(slug: str, request: Request, db: Session = Depends(get_db)):
    car_park = db.query(CarPark).filter(CarPark.slug == slug).first()
    estate_name = car_park.owner.name if car_park else ""
    car_park_name = car_park.name if car_park else ""
    logo_url = (getattr(car_park, "logo_url", None) or "") if car_park else ""
    accent = (car_park.brand_accent or "#8B3A2A") if car_park else "#8B3A2A"
    return templates.TemplateResponse("driver/receipt_placeholder.html", {
        "request": request,
        "slug": slug,
        "estate_name": estate_name,
        "car_park_name": car_park_name,
        "logo_url": logo_url,
        "brand": {"accent": accent},
    })


@router.get("/mockup", response_class=HTMLResponse)
def payment_mockup(request: Request):
    return templates.TemplateResponse("driver/payment_mockup.html", {"request": request})


@router.get("/park/{slug}", response_class=HTMLResponse)
def park_landing(slug: str, request: Request, db: Session = Depends(get_db)):
    car_park = db.query(CarPark).filter(CarPark.slug == slug, CarPark.is_active == True).first()
    if not car_park:
        raise HTTPException(status_code=404, detail="Car park not found")

    rule = get_active_rule(db, car_park.id, date.today())
    if not rule:
        raise HTTPException(status_code=503, detail="No pricing available for today")

    options = build_duration_options(rule)
    # Extract values while session is open — TemplateResponse renders lazily after session closes
    brand = {
        "primary": car_park.brand_primary or "#1e3a1e",
        "accent": car_park.brand_accent or "#b8963e",
        "text": car_park.brand_text or "#ffffff",
    }
    context = {
        "request": request,
        "car_park_name": car_park.name,
        "car_park_slug": car_park.slug,
        "car_park_tagline": car_park.tagline,
        "estate_name": car_park.owner.name,
        "logo_url": getattr(car_park, 'logo_url', None) or "",
        "welcome_text": getattr(car_park, 'welcome_text', None) or "",
        "brand": brand,
        "options": options,
    }
    return templates.TemplateResponse("driver/park.html", context)


@router.post("/park/{slug}/checkout")
async def create_checkout(
    slug: str,
    request: Request,
    number_plate: str = Form(...),
    duration: str = Form(...),
    db: Session = Depends(get_db),
):
    car_park = db.query(CarPark).filter(CarPark.slug == slug, CarPark.is_active == True).first()
    if not car_park:
        raise HTTPException(status_code=404)

    rule = get_active_rule(db, car_park.id, date.today())
    if not rule:
        raise HTTPException(status_code=503)

    is_all_day = duration == "all_day"
    duration_hours = None if is_all_day else int(duration)
    amount_pence = calculate_price(rule, duration_hours, is_all_day)
    duration_label = "All day" if is_all_day else f"{duration_hours} hour{'s' if duration_hours > 1 else ''}"

    # Extract values while session is open
    brand = {
        "primary": car_park.brand_primary or "#1e3a1e",
        "accent": car_park.brand_accent or "#8B3A2A",
        "text": car_park.brand_text or "#ffffff",
    }
    context = {
        "request": request,
        "estate_name": car_park.owner.name,
        "car_park_name": car_park.name,
        "car_park_slug": car_park.slug,
        "number_plate": number_plate.upper().replace(" ", ""),
        "duration_label": duration_label,
        "amount": f"£{amount_pence / 100:.2f}",
        "logo_url": getattr(car_park, 'logo_url', None) or "",
        "welcome_text": getattr(car_park, 'welcome_text', None) or "",
        "brand": brand,
    }
    return templates.TemplateResponse("driver/payment_mockup.html", context)

    # -- Stripe (live -- replace mockup block above when keys are ready) --
    commission_pence = int(amount_pence * car_park.owner.commission_pct / 100)
    owner_amount_pence = amount_pence - commission_pence

    txn = Transaction(
        car_park_id=car_park.id,
        number_plate=number_plate.upper().replace(" ", ""),
        duration_hours=duration_hours,
        is_all_day=is_all_day,
        amount_pence=amount_pence,
        commission_pence=commission_pence,
        owner_amount_pence=owner_amount_pence,
        status=TransactionStatus.pending,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "gbp",
                "product_data": {
                    "name": f"Parking — {car_park.name}",
                    "description": f"{duration_label} | {number_plate.upper()}",
                },
                "unit_amount": amount_pence,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{base_url}/park/{slug}/success?txn={txn.id}&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/park/{slug}",
        metadata={"txn_id": str(txn.id)},
    )

    txn.stripe_payment_intent_id = session.payment_intent
    db.commit()

    return RedirectResponse(session.url, status_code=303)


@router.get("/park/{slug}/success", response_class=HTMLResponse)
def park_success(slug: str, txn: int, session_id: str, request: Request, db: Session = Depends(get_db)):
    car_park = db.query(CarPark).filter(CarPark.slug == slug).first()
    transaction = db.query(Transaction).filter(Transaction.id == txn).first()

    if not transaction:
        raise HTTPException(status_code=404)

    # Mark paid and set times
    if transaction.status == TransactionStatus.pending:
        now = datetime.now(timezone.utc)
        transaction.status = TransactionStatus.paid
        transaction.parked_at = now
        if not transaction.is_all_day and transaction.duration_hours:
            transaction.expires_at = now + timedelta(hours=transaction.duration_hours)
        db.commit()

    return templates.TemplateResponse("driver/confirmation.html", {
        "request": request,
        "car_park": car_park,
        "transaction": transaction,
    })


@router.get("/check/{slug}", response_class=HTMLResponse)
def warden_check_page(slug: str, request: Request, db: Session = Depends(get_db)):
    car_park = db.query(CarPark).filter(CarPark.slug == slug).first()
    if not car_park:
        raise HTTPException(status_code=404)
    cp = {"id": car_park.id, "name": car_park.name, "slug": car_park.slug}
    return templates.TemplateResponse("driver/check.html", {"request": request, "car_park": cp, "result": None})


@router.post("/check/{slug}", response_class=HTMLResponse)
def warden_check(slug: str, request: Request, number_plate: str = Form(...), db: Session = Depends(get_db)):
    car_park = db.query(CarPark).filter(CarPark.slug == slug).first()
    if not car_park:
        raise HTTPException(status_code=404)
    plate = number_plate.upper().replace(" ", "")
    now_utc = datetime.now(timezone.utc)

    def make_aware(dt):
        if dt is None:
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    txn = (
        db.query(Transaction)
        .filter(
            Transaction.car_park_id == car_park.id,
            Transaction.number_plate == plate,
            Transaction.status == TransactionStatus.paid,
        )
        .order_by(Transaction.parked_at.desc())
        .first()
    )

    is_active = False
    expires_str = None
    duration_str = None
    if txn:
        if txn.is_all_day:
            pa = make_aware(txn.parked_at)
            is_active = pa is not None and (now_utc - pa).days == 0
            expires_str = "End of day (23:59)"
            duration_str = "All day"
        else:
            exp = make_aware(txn.expires_at)
            is_active = exp is not None and exp > now_utc
            expires_str = exp.strftime("%d %b %Y %H:%M") if exp else None
            duration_str = f"{txn.duration_hours} hour{'s' if txn.duration_hours != 1 else ''}"

    cp = {"id": car_park.id, "name": car_park.name, "slug": car_park.slug}
    result = {
        "plate": plate,
        "is_active": is_active,
        "found": txn is not None,
        "expires": expires_str,
        "duration": duration_str,
    }
    return templates.TemplateResponse("driver/check.html", {"request": request, "car_park": cp, "result": result})
