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

# Known estate slugs — extend as new estates are onboarded
ESTATES = {
    "shere-manor-estate": {
        "name": "Shere Manor Estate",
        "tagline": "A private estate in the heart of the Surrey Hills.",
        "car_park_slug": "shere-manor",
    },
}


def _get_estate(slug: str):
    return ESTATES.get(slug)


# ── Estate information pages ──────────────────────────────────────────────────

@router.get("/{slug}", response_class=HTMLResponse)
def location_home(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/home.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/parking", response_class=HTMLResponse)
def location_parking(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/parking.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/walking-routes", response_class=HTMLResponse)
def location_walking(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/walking.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/cycle-routes", response_class=HTMLResponse)
def location_cycling(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/cycling.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/places-of-interest", response_class=HTMLResponse)
def location_places(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/places.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/legacies", response_class=HTMLResponse)
def location_legacies(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/legacies.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/benches", response_class=HTMLResponse)
def location_benches(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/benches.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/trees", response_class=HTMLResponse)
def location_trees(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/trees.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/about", response_class=HTMLResponse)
def location_about(request: Request, slug: str):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/about.html", {"request": request, "slug": slug, "estate": estate})


@router.get("/{slug}/contact", response_class=HTMLResponse)
def location_contact(request: Request, slug: str, sent: bool = False):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("location/contact.html", {"request": request, "slug": slug, "estate": estate, "sent": sent})


# ── Visitor / on-site pages ───────────────────────────────────────────────────

@router.get("/{slug}/visitor/welcome", response_class=HTMLResponse)
def visitor_welcome(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    brand = {
        "primary": (car_park.brand_primary or "#1e3a1e") if car_park else "#1e3a1e",
        "accent": (car_park.brand_accent or "#B89A5A") if car_park else "#B89A5A",
        "text": (car_park.brand_text or "#ffffff") if car_park else "#ffffff",
    }
    return templates.TemplateResponse("location/visitor/welcome.html", {
        "request": request,
        "slug": slug,
        "estate": estate,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "welcome_text": (getattr(car_park, "welcome_text", None) or "") if car_park else "",
        "car_park_tagline": (car_park.tagline or "") if car_park else estate["tagline"],
        "brand": brand,
    })


@router.get("/{slug}/visitor/parking-start", response_class=HTMLResponse)
def visitor_parking_start(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug, CarPark.is_active == True).first()
    if not car_park:
        raise HTTPException(status_code=503, detail="Car park not available")
    rule = get_active_rule(db, car_park.id, date.today())
    if not rule:
        raise HTTPException(status_code=503, detail="No pricing available for today")
    options = build_duration_options(rule)
    brand = {
        "primary": car_park.brand_primary or "#1e3a1e",
        "accent": car_park.brand_accent or "#b8963e",
        "text": car_park.brand_text or "#ffffff",
    }
    return templates.TemplateResponse("driver/park.html", {
        "request": request,
        "car_park_name": car_park.name,
        "car_park_slug": cp_slug,
        "car_park_tagline": car_park.tagline,
        "estate_name": car_park.owner.name,
        "logo_url": getattr(car_park, "logo_url", None) or "",
        "welcome_text": getattr(car_park, "welcome_text", None) or "",
        "brand": brand,
        "options": options,
        "slug": slug,
        "checkout_url": f"/location/{slug}/visitor/parking-start/checkout",
    })


@router.post("/{slug}/visitor/parking-start/checkout")
async def visitor_checkout(
    slug: str,
    request: Request,
    number_plate: str = Form(...),
    duration: str = Form(...),
    db: Session = Depends(get_db),
):
    estate = _get_estate(slug)
    if not estate:
        raise HTTPException(status_code=404)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug, CarPark.is_active == True).first()
    if not car_park:
        raise HTTPException(status_code=404)
    rule = get_active_rule(db, car_park.id, date.today())
    if not rule:
        raise HTTPException(status_code=503)

    is_all_day = duration == "all_day"
    duration_hours = None if is_all_day else int(duration)
    amount_pence = calculate_price(rule, duration_hours, is_all_day)
    duration_label = "All day" if is_all_day else f"{duration_hours} hour{'s' if duration_hours > 1 else ''}"

    brand = {
        "primary": car_park.brand_primary or "#1e3a1e",
        "accent": car_park.brand_accent or "#8B3A2A",
        "text": car_park.brand_text or "#ffffff",
    }
    context = {
        "request": request,
        "estate_name": car_park.owner.name,
        "car_park_name": car_park.name,
        "car_park_slug": cp_slug,
        "number_plate": number_plate.upper().replace(" ", ""),
        "duration_label": duration_label,
        "amount": f"£{amount_pence / 100:.2f}",
        "logo_url": getattr(car_park, "logo_url", None) or "",
        "welcome_text": getattr(car_park, "welcome_text", None) or "",
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
        success_url=f"{base_url}/location/{slug}/visitor/parking-receipt?txn={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/location/{slug}/visitor/parking-start",
        metadata={"txn_id": str(txn.id)},
    )

    txn.stripe_payment_intent_id = session.payment_intent
    db.commit()

    return RedirectResponse(session.url, status_code=303)


@router.get("/{slug}/visitor/parking-payment", response_class=HTMLResponse)
def visitor_parking_payment(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    accent = (car_park.brand_accent or "#8B3A2A") if car_park else "#8B3A2A"
    return templates.TemplateResponse("driver/payment_mockup.html", {
        "request": request,
        "slug": cp_slug,
        "estate_name": car_park.owner.name if car_park else "",
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "brand": {"accent": accent},
    })


@router.get("/{slug}/visitor/parking-receipt", response_class=HTMLResponse)
def visitor_parking_receipt(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    accent = (car_park.brand_accent or "#8B3A2A") if car_park else "#8B3A2A"
    return templates.TemplateResponse("driver/receipt_placeholder.html", {
        "request": request,
        "slug": cp_slug,
        "estate_name": car_park.owner.name if car_park else "",
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "brand": {"accent": accent},
    })
