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

# Walk data — keyed by estate slug then walk slug
WALKS = {
    "shere-manor-estate": [
        {
            "slug": "shere-village",
            "title": "Shere Village",
            "distance": "0.5 km",
            "duration": "15 min",
            "difficulty": "Easy",
            "summary": "A short walk around the village, taking in various interesting buildings, the church, stores, restaurants.",
            "image_url": "",
            "center": [51.2164, -0.4444],
            "zoom": 16,
            "waypoint_zoom": 17,
            "route": [
                [51.2167, -0.4451], [51.2170, -0.4443], [51.2168, -0.4437],
                [51.2163, -0.4434], [51.2158, -0.4440], [51.2161, -0.4450],
                [51.2167, -0.4451]
            ],
            "waypoint_coords": [
                [51.2167, -0.4451], [51.2170, -0.4443], [51.2163, -0.4434], [51.2158, -0.4440]
            ],
            "waypoints": [
                {
                    "title": "Shere Car Park",
                    "description": "Start at the village car park. The picturesque centre of Shere is just a short stroll away.",
                    "image_url": ""
                },
                {
                    "title": "St James' Church",
                    "description": "The beautiful 12th-century St James' Church is one of the finest in Surrey. Look out for the anchorite's cell on the north wall.",
                    "image_url": ""
                },
                {
                    "title": "Middle Street",
                    "description": "Wander along Middle Street past the village stores, tea rooms and the White Horse pub, a favourite with walkers.",
                    "image_url": ""
                },
                {
                    "title": "The Tillingbourne",
                    "description": "Follow the stream back through the village. The shallow ford and stepping stones are a favourite with children.",
                    "image_url": ""
                },
            ],
        },
        {
            "slug": "william-iv",
            "title": "William IV",
            "distance": "4 km",
            "duration": "1 hr",
            "difficulty": "Moderate",
            "summary": "A lovely walk along the river and through parkland to the quaint and rather upmarket William IV pub.",
            "image_url": "",
            "center": [51.2165, -0.4530],
            "zoom": 14,
            "waypoint_zoom": 16,
            "route": [
                [51.2167, -0.4451], [51.2172, -0.4465], [51.2178, -0.4490],
                [51.2182, -0.4515], [51.2178, -0.4555], [51.2170, -0.4590],
                [51.2158, -0.4618]
            ],
            "waypoint_coords": [
                [51.2167, -0.4451], [51.2178, -0.4490], [51.2182, -0.4515], [51.2158, -0.4618]
            ],
            "waypoints": [
                {
                    "title": "Shere Village",
                    "description": "Head west out of the village along the Tillingbourne. The path follows the stream through water meadows.",
                    "image_url": ""
                },
                {
                    "title": "Tillingbourne Valley",
                    "description": "The river path winds through open countryside with views across the Surrey Hills. Listen for kingfishers along this stretch.",
                    "image_url": ""
                },
                {
                    "title": "Albury Park",
                    "description": "Pass through the edge of Albury Park, a private estate with a remarkable ornamental garden designed by John Evelyn in the 17th century.",
                    "image_url": ""
                },
                {
                    "title": "William IV",
                    "description": "Your destination — a charming country pub in the hamlet of Little London, Albury. Deservedly popular, so worth booking a table in advance.",
                    "image_url": ""
                },
            ],
        },
    ]
}


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


@router.get("/{slug}/visitor/walking", response_class=HTMLResponse)
def visitor_walking_list(request: Request, slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    walks = WALKS.get(slug, [])
    return templates.TemplateResponse("location/visitor/walking_list.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "walks": walks,
    })


@router.get("/{slug}/visitor/walking/{walk_slug}", response_class=HTMLResponse)
def visitor_walking_detail(request: Request, slug: str, walk_slug: str, db: Session = Depends(get_db)):
    estate = _get_estate(slug)
    if not estate:
        return RedirectResponse(url="/", status_code=302)
    cp_slug = estate["car_park_slug"]
    car_park = db.query(CarPark).filter(CarPark.slug == cp_slug).first()
    walks = WALKS.get(slug, [])
    walk = next((w for w in walks if w["slug"] == walk_slug), None)
    if not walk:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("location/visitor/walking_detail.html", {
        "request": request,
        "slug": slug,
        "estate_name": car_park.owner.name if car_park else estate["name"],
        "car_park_name": car_park.name if car_park else "",
        "logo_url": (getattr(car_park, "logo_url", None) or "") if car_park else "",
        "walk": walk,
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
