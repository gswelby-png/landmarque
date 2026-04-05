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
                    "description": [
                        "Start at the village car park, one of only a handful of spaces available in this small but perpetually busy village. Shere is consistently voted one of the most beautiful villages in England, and it is easy to see why — the streets are lined with timber-framed houses, many dating from the 15th and 16th centuries, and there is not a chain shop or supermarket in sight.",
                        "From the car park, follow the path toward the village centre. You will cross a small bridge over the Tillingbourne, the chalk stream that has shaped life in Shere for centuries. Look down into the crystal-clear water and you may spot brown trout hovering in the current, barely moving in their effortless way against the flow.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "St James' Church",
                    "description": [
                        "St James' Church is the undisputed heart of Shere and one of the finest Norman churches in Surrey. The main structure dates from around 1190, though there have been places of worship on this site for much longer. The square flint tower is a landmark for miles around, and the interior contains remarkable medieval features including a 13th-century font and fine stained glass.",
                        "Look for the small window set into the north wall of the chancel — this is the anchorite's cell, home to Christine Carpenter, who in 1329 had herself voluntarily enclosed within the cell to live a life of prayer and contemplation. She was given food through a small hatch and could see the altar through this little window. Christine's story has fascinated visitors for centuries and was the inspiration for a well-known novel.",
                        "The churchyard is well worth exploring. Several inscribed stones date from the 17th century, and the eastern end offers fine views back across the rooftops toward the wooded hills beyond.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Middle Street",
                    "description": [
                        "Middle Street is the main thoroughfare of Shere and one of the most photographed streets in England. The combination of timber-framed buildings, hanging flower baskets and the gentle sound of the Tillingbourne running alongside makes it particularly picturesque in spring and summer, though it has a quiet charm in every season.",
                        "The street is home to a good selection of independent shops and eating places. The William Bray tea rooms offer excellent homemade cakes and cream teas. The White Horse pub, which dates from the 14th century, is one of the oldest buildings in the village and a perennial favourite with walkers coming in off the hills. There is also a village stores, a pottery, and several small artisan businesses occupying the old farm buildings at the eastern end.",
                        "Look up as you walk — many of the upper storeys and roof lines predate the current shopfronts by several centuries, and the overall streetscape has changed remarkably little since the 18th century. Film crews have used it repeatedly as a stand-in for various periods of English history.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "The Tillingbourne",
                    "description": [
                        "The Tillingbourne is a chalk stream rising on the southern slopes of the North Downs near Albury and flowing westward through the Surrey Hills to join the River Wey at Shalford. Chalk streams are among the rarest and most biodiverse freshwater habitats in the world — only around 200 exist globally, and the vast majority are in southern England.",
                        "The shallow ford in the centre of the village is enormously popular with families, particularly in summer, when children paddle in the clear, cold water and attempt the stepping stones alongside. The stream supports brown trout, water voles, kingfishers and a rich variety of aquatic insects, and the water quality is among the best in the county.",
                        "Follow the stream back toward the car park, passing the old mill building on your left. The mill was in operation from at least the 16th century and was last used commercially in the early 20th century. The millpond behind it is now a tranquil wildlife area and worth a few quiet minutes before returning to the car.",
                    ],
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
                    "description": [
                        "The walk begins at the village car park and heads west along the valley bottom. Cross the ford or stepping stones over the Tillingbourne and follow the signed footpath along the south bank of the stream. The path is well maintained and straightforward to follow, though it can be muddy after wet weather — stout shoes or walking boots are recommended.",
                        "As you leave the village behind, the path passes through a succession of classic Surrey countryside — ancient hedgerows, water meadows grazed by cattle in season, and veteran oak trees that would have been saplings when Elizabeth I was on the throne. The valley narrows gently and the sound of traffic fades within a few minutes of leaving the car park.",
                        "Keep an eye out for the old mill leat running parallel to the stream on your right. This man-made channel dates from at least the 13th century and was used to power a succession of mills along the Tillingbourne, which was once one of the most intensively industrialised river valleys in southern England — producing iron, gunpowder and paper at various points in its history.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Tillingbourne Valley",
                    "description": [
                        "The path follows the Tillingbourne west through open water meadows with fine views across the valley — the wooded escarpment of the North Downs to the north and the greensand ridge to the south create a gentle bowl of countryside that has remained largely unchanged for centuries. This stretch is particularly good for birds: kingfishers are regularly seen darting low along the stream, grey herons stand motionless in the shallows, and in summer the meadows ring with skylarks.",
                        "The river here is a textbook chalk stream — gin-clear, cold, and fast-flowing over a clean gravel bed. Chalk streams are among the rarest freshwater habitats in the world; only around 200 exist globally, and most are in southern England. This one is in unusually fine condition, largely because the valley has escaped the intensive drainage and fertiliser run-off that has degraded so many comparable rivers. Brown trout are visible most days, rising to take flies on summer evenings.",
                        "About halfway along this section you will pass the remains of an old watermill, its wheel pit and sluice gates still discernible in the undergrowth by the bank. The Tillingbourne drove dozens of mills from the medieval period onward, and the remnants of that industrial past are scattered all along the valley floor for those who look carefully.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "Albury Park",
                    "description": [
                        "The path skirts the edge of Albury Park, a historic private estate at the centre of the valley. The park was laid out in the late 17th century by John Evelyn — diarist, polymath, and one of the founding fellows of the Royal Society — who was a close friend of the then owner. Evelyn's design incorporated a remarkable series of terraced gardens cut into the hillside to the north, some of which survive in altered form and can be glimpsed through the trees.",
                        "The estate passed through several hands before being acquired by Henry Drummond in the early 19th century, who commissioned Augustus Pugin — the architect responsible for the interiors of the Houses of Parliament — to carry out extensive work on the house and estate buildings. Pugin's Catholic chapel, with its elaborate Gothic interior, stands near the estate entrance and is occasionally open to visitors.",
                        "The old parish church of St Peter and St Paul stands within the park boundary and is worth a detour if it is open. It is notable for its Saxon chancel arch, an early Norman apse, and the extraordinary series of painted wooden grave covers in the churchyard. The church is no longer in regular use and is maintained by the Churches Conservation Trust.",
                    ],
                    "image_url": ""
                },
                {
                    "title": "William IV",
                    "description": [
                        "Your destination is the William IV pub, tucked away in the hamlet of Little London near Albury Heath. Despite its somewhat remote location — there are no road signs pointing to it and first-time visitors often overshoot — it has built a serious reputation over the past decade as one of the finest country pubs in Surrey. A booking is strongly recommended for weekend lunches and dinners. The building itself is a classic Surrey cottage, low-ceilinged, beamed and with an open fire that makes it especially welcoming on cold days.",
                        "The menu changes regularly to reflect seasonal and local produce, and the kitchen has close relationships with several nearby farms. The game dishes are outstanding in autumn and winter, and the puddings are the kind that make you glad you walked here rather than drove. The wine list is thoughtfully assembled and the beer selection includes several good ales from Surrey and Sussex breweries.",
                        "To return, retrace your steps east along the Tillingbourne valley — the walk back is, if anything, even better than the outward leg, since the light is different and the views open up from directions you did not see on the way out. Allow around 50 minutes for the return to Shere.",
                    ],
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
