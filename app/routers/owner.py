import csv
import io
import json
import qrcode

from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timezone
from jose import JWTError

from ..database import get_db
from ..models import Owner, CarPark, PricingRule, Transaction, TransactionStatus, DayType, SlugRedirect
from ..auth import hash_password, verify_password, create_token, decode_token

router = APIRouter(prefix="/owner")
templates = Jinja2Templates(directory="app/templates")


def current_owner(request: Request, db: Session) -> Owner:
    token = request.cookies.get("owner_token")
    if not token:
        raise HTTPException(status_code=302, headers={"Location": "/owner/login"})
    try:
        payload = decode_token(token)
        owner = db.query(Owner).filter(Owner.id == int(payload["sub"])).first()
        if not owner or not owner.is_active:
            raise HTTPException(status_code=302, headers={"Location": "/owner/login"})
        return owner
    except JWTError:
        raise HTTPException(status_code=302, headers={"Location": "/owner/login"})


def _is_active_txn(t, now_utc):
    """Return True if transaction is currently active."""
    def make_aware(dt):
        if dt is None:
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    if t.is_all_day:
        pa = make_aware(t.parked_at)
        return pa is not None and (now_utc - pa).days == 0
    exp = make_aware(t.expires_at)
    return exp is not None and exp > now_utc


# ── Auth ────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, pw_ok: bool = Query(False), pw_error: bool = Query(False)):
    return templates.TemplateResponse("owner/login.html", {"request": request, "error": None, "pw_ok": pw_ok, "pw_error": pw_error})


@router.post("/reset-password")
def reset_password(
    request: Request,
    email: str = Form(...),
    current_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    owner = db.query(Owner).filter(Owner.email == email).first()
    if not owner or not verify_password(current_password, owner.password_hash):
        return RedirectResponse("/owner/login?pw_error=1", status_code=303)
    if len(new_password) < 6:
        return RedirectResponse("/owner/login?pw_error=1", status_code=303)
    owner.password_hash = hash_password(new_password)
    db.commit()
    return RedirectResponse("/owner/login?pw_ok=1", status_code=303)


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    owner = db.query(Owner).filter(Owner.email == email).first()
    if not owner or not verify_password(password, owner.password_hash):
        return templates.TemplateResponse("owner/login.html", {
            "request": request, "error": "Invalid email or password"
        })
    token = create_token({"sub": str(owner.id), "role": "owner"})
    response = RedirectResponse("/owner/dashboard", status_code=303)
    response.set_cookie("owner_token", token, httponly=True, max_age=43200)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/owner/login", status_code=303)
    response.delete_cookie("owner_token")
    return response


# ── Dashboard ───────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), pw_ok: bool = Query(False), pw_error: bool = Query(False)):
    owner = current_owner(request, db)
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    now_utc = datetime.now(timezone.utc)

    def make_aware(dt):
        if dt is None:
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    # ── Overall revenue stats ────────────────────────────────────────────────
    today_revenue = (
        db.query(func.sum(Transaction.owner_amount_pence))
        .join(CarPark)
        .filter(
            CarPark.owner_id == owner.id,
            Transaction.status == TransactionStatus.paid,
            func.date(Transaction.parked_at) == today,
        )
        .scalar() or 0
    )
    month_revenue = (
        db.query(func.sum(Transaction.owner_amount_pence))
        .join(CarPark)
        .filter(
            CarPark.owner_id == owner.id,
            Transaction.status == TransactionStatus.paid,
            Transaction.parked_at >= month_start,
        )
        .scalar() or 0
    )
    ytd_revenue = (
        db.query(func.sum(Transaction.owner_amount_pence))
        .join(CarPark)
        .filter(
            CarPark.owner_id == owner.id,
            Transaction.status == TransactionStatus.paid,
            Transaction.parked_at >= year_start,
        )
        .scalar() or 0
    )




    # ── Per car park data ────────────────────────────────────────────────────
    car_parks = db.query(CarPark).filter(CarPark.owner_id == owner.id).all()

    cp_data = []
    for cp in car_parks:
        rules = db.query(PricingRule).filter(PricingRule.car_park_id == cp.id).order_by(PricingRule.valid_from.desc()).all()

        txns = (
            db.query(Transaction)
            .filter(Transaction.car_park_id == cp.id, Transaction.status == TransactionStatus.paid)
            .all()
        )

        # Per-car-park live count
        cp_live = sum(1 for t in txns if _is_active_txn(t, now_utc))

        # Per-car-park revenue
        cp_today_rev = sum(
            t.owner_amount_pence for t in txns
            if t.parked_at and (make_aware(t.parked_at).date() == today)
        )
        cp_month_rev = sum(
            t.owner_amount_pence for t in txns
            if t.parked_at and (make_aware(t.parked_at).date() >= month_start)
        )
        cp_ytd_rev = sum(
            t.owner_amount_pence for t in txns
            if t.parked_at and (make_aware(t.parked_at).date() >= year_start)
        )

        def exp_ts(t):
            if t.is_all_day and t.parked_at:
                pa = make_aware(t.parked_at)
                return pa.replace(hour=23, minute=59, second=0, microsecond=0).timestamp()
            exp = make_aware(t.expires_at)
            return exp.timestamp() if exp else 0

        def sort_key(t):
            active = _is_active_txn(t, now_utc)
            ts = exp_ts(t)
            return (0 if active else 1, ts if active else -ts)

        txns_sorted = sorted(txns, key=sort_key)[:100]

        cp_data.append({
            "id": cp.id,
            "name": cp.name,
            "address": cp.address or "",
            "description": cp.description or "",
            "slug": cp.slug,
            "is_active": cp.is_active,
            "live_count": cp_live,
            "today_rev": cp_today_rev,
            "month_rev": cp_month_rev,
            "ytd_rev": cp_ytd_rev,
            "rules": [
                {
                    "id": r.id,
                    "day_type": r.day_type.value.title(),
                    "hourly": f"£{r.hourly_rate_pence/100:.2f}/hr",
                    "max_hours": r.max_hourly_hours or "—",
                    "all_day": f"£{r.all_day_pence/100:.2f}" if r.all_day_pence else "—",
                    "valid_from": str(r.valid_from),
                    "valid_to": str(r.valid_to) if r.valid_to else "Open",
                    # Raw values for edit form pre-population
                    "day_type_raw": r.day_type.value,
                    "hourly_raw": f"{r.hourly_rate_pence/100:.2f}",
                    "max_hours_raw": r.max_hourly_hours or "",
                    "all_day_raw": f"{r.all_day_pence/100:.2f}" if r.all_day_pence else "",
                    "valid_from_raw": str(r.valid_from),
                    "valid_to_raw": str(r.valid_to) if r.valid_to else "",
                }
                for r in rules
            ],
            "transactions": [
                {
                    "plate": t.number_plate,
                    "duration": "All day" if t.is_all_day else f"{t.duration_hours} hour{'s' if t.duration_hours > 1 else ''}",
                    "amount": f"£{t.owner_amount_pence / 100:.2f}",
                    "expires": (
                        make_aware(t.parked_at).replace(hour=23, minute=59, second=0).strftime("%d %b %Y %H:%M")
                        if t.is_all_day and t.parked_at
                        else (make_aware(t.expires_at).strftime("%d %b %Y %H:%M") if t.expires_at else "—")
                    ),
                    "active": _is_active_txn(t, now_utc),
                }
                for t in txns_sorted
            ],
        })

    return templates.TemplateResponse("owner/dashboard.html", {
        "request": request,
        "owner_name": owner.name,
        "today_revenue": today_revenue,
        "month_revenue": month_revenue,
        "ytd_revenue": ytd_revenue,
        "cp_data": cp_data,
        "pw_ok": pw_ok,
        "pw_error": pw_error,
    })


# ── Car Parks ────────────────────────────────────────────────────────────────

@router.get("/car-parks/new", response_class=HTMLResponse)
def new_car_park_page(request: Request, db: Session = Depends(get_db)):
    owner = current_owner(request, db)
    return templates.TemplateResponse("owner/car_park_form.html", {
        "request": request, "owner": owner, "car_park": None, "error": None
    })


@router.post("/car-parks/new")
def create_car_park(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    address: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    owner = current_owner(request, db)
    slug = slug.lower().replace(" ", "-")
    if db.query(CarPark).filter(CarPark.slug == slug).first():
        return templates.TemplateResponse("owner/car_park_form.html", {
            "request": request, "owner": owner, "car_park": None,
            "error": f"Slug '{slug}' is already taken"
        })
    cp = CarPark(owner_id=owner.id, name=name, slug=slug, address=address, description=description)
    db.add(cp)
    db.commit()
    return RedirectResponse("/owner/dashboard", status_code=303)


@router.get("/car-parks/{cp_id}/edit", response_class=HTMLResponse)
def edit_car_park_page(cp_id: int, request: Request, db: Session = Depends(get_db)):
    owner = current_owner(request, db)
    cp = db.query(CarPark).filter(CarPark.id == cp_id, CarPark.owner_id == owner.id).first()
    if not cp:
        raise HTTPException(status_code=404)
    data = {"id": cp.id, "name": cp.name, "address": cp.address or "", "description": cp.description or ""}
    return templates.TemplateResponse("owner/car_park_form.html", {
        "request": request, "owner": owner, "car_park": data, "error": None
    })


@router.post("/car-parks/{cp_id}/edit")
def edit_car_park(
    cp_id: int,
    request: Request,
    name: str = Form(...),
    address: str = Form(""),
    description: str = Form(""),
    slug: str = Form(""),
    db: Session = Depends(get_db),
):
    owner = current_owner(request, db)
    cp = db.query(CarPark).filter(CarPark.id == cp_id, CarPark.owner_id == owner.id).first()
    if not cp:
        raise HTTPException(status_code=404)
    cp.name = name
    cp.address = address
    cp.description = description
    if slug and slug != cp.slug:
        old_slug = cp.slug
        # Check new slug not already taken
        if not db.query(CarPark).filter(CarPark.slug == slug, CarPark.id != cp_id).first():
            cp.slug = slug
            # Preserve the old slug as a redirect (upsert)
            existing = db.query(SlugRedirect).filter(SlugRedirect.old_slug == old_slug).first()
            if not existing:
                db.add(SlugRedirect(old_slug=old_slug, car_park_id=cp_id))
    db.commit()
    return RedirectResponse("/owner/dashboard", status_code=303)


@router.get("/car-parks/{cp_id}/qr")
def download_qr(cp_id: int, request: Request, db: Session = Depends(get_db)):
    owner = current_owner(request, db)
    cp = db.query(CarPark).filter(CarPark.id == cp_id, CarPark.owner_id == owner.id).first()
    if not cp:
        raise HTTPException(status_code=404)
    base_url = str(request.base_url).rstrip("/")
    park_url = f"{base_url}/park/{cp.slug}"
    img = qrcode.make(park_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    filename = f"{cp.slug}-qr.png"
    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/car-parks/{cp_id}/pricing", response_class=HTMLResponse)
def pricing_page(cp_id: int, request: Request, db: Session = Depends(get_db)):
    owner = current_owner(request, db)
    cp = db.query(CarPark).filter(CarPark.id == cp_id, CarPark.owner_id == owner.id).first()
    if not cp:
        raise HTTPException(status_code=404)
    rules = db.query(PricingRule).filter(PricingRule.car_park_id == cp_id).order_by(
        PricingRule.valid_from.desc()
    ).all()
    return templates.TemplateResponse("owner/pricing.html", {
        "request": request, "owner": owner, "car_park": cp, "rules": rules,
        "day_types": [d.value for d in DayType], "error": None,
    })


@router.post("/car-parks/{cp_id}/pricing")
def add_pricing_rule(
    cp_id: int,
    request: Request,
    day_type: str = Form(...),
    hourly_rate: float = Form(...),
    max_hourly_hours: int = Form(None),
    all_day_price: float = Form(None),
    valid_from: date = Form(...),
    valid_to: date = Form(None),
    db: Session = Depends(get_db),
):
    owner = current_owner(request, db)
    cp = db.query(CarPark).filter(CarPark.id == cp_id, CarPark.owner_id == owner.id).first()
    if not cp:
        raise HTTPException(status_code=404)
    rule = PricingRule(
        car_park_id=cp_id,
        day_type=DayType(day_type),
        hourly_rate_pence=int(hourly_rate * 100),
        max_hourly_hours=max_hourly_hours or None,
        all_day_pence=int(all_day_price * 100) if all_day_price else None,
        valid_from=valid_from,
        valid_to=valid_to or None,
    )
    db.add(rule)
    db.commit()
    return RedirectResponse("/owner/dashboard", status_code=303)


@router.post("/car-parks/{cp_id}/pricing/{rule_id}/delete")
def delete_pricing_rule(
    cp_id: int,
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    owner = current_owner(request, db)
    cp = db.query(CarPark).filter(CarPark.id == cp_id, CarPark.owner_id == owner.id).first()
    if not cp:
        raise HTTPException(status_code=404)
    rule = db.query(PricingRule).filter(PricingRule.id == rule_id, PricingRule.car_park_id == cp_id).first()
    if rule:
        db.delete(rule)
        db.commit()
    return RedirectResponse("/owner/dashboard", status_code=303)


@router.post("/car-parks/{cp_id}/pricing/{rule_id}/update")
def update_pricing_rule(
    cp_id: int,
    rule_id: int,
    request: Request,
    day_type: str = Form(...),
    hourly_rate: float = Form(...),
    max_hourly_hours: int = Form(None),
    all_day_price: float = Form(None),
    valid_from: str = Form(...),
    valid_to: str = Form(None),
    db: Session = Depends(get_db),
):
    owner = current_owner(request, db)
    cp = db.query(CarPark).filter(CarPark.id == cp_id, CarPark.owner_id == owner.id).first()
    if not cp:
        raise HTTPException(status_code=404)
    rule = db.query(PricingRule).filter(PricingRule.id == rule_id, PricingRule.car_park_id == cp_id).first()
    if rule:
        rule.day_type = day_type
        rule.hourly_rate_pence = int(hourly_rate * 100)
        rule.max_hourly_hours = max_hourly_hours
        rule.all_day_pence = int(all_day_price * 100) if all_day_price else None
        from datetime import date as _date
        rule.valid_from = _date.fromisoformat(valid_from)
        rule.valid_to = _date.fromisoformat(valid_to) if valid_to else None
        db.commit()
    return RedirectResponse("/owner/dashboard", status_code=303)


@router.post("/car-parks/{cp_id}/toggle")
def toggle_car_park(cp_id: int, request: Request, db: Session = Depends(get_db)):
    owner = current_owner(request, db)
    cp = db.query(CarPark).filter(CarPark.id == cp_id, CarPark.owner_id == owner.id).first()
    if not cp:
        raise HTTPException(status_code=404)
    cp.is_active = not cp.is_active
    db.commit()
    return RedirectResponse("/owner/dashboard", status_code=303)


@router.post("/change-password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    owner = current_owner(request, db)
    if not verify_password(current_password, owner.password_hash):
        return RedirectResponse("/owner/dashboard?pw_error=1", status_code=303)
    if len(new_password) < 6:
        return RedirectResponse("/owner/dashboard?pw_error=1", status_code=303)
    owner.password_hash = hash_password(new_password)
    db.commit()
    return RedirectResponse("/owner/dashboard?pw_ok=1", status_code=303)


# ── Transactions ─────────────────────────────────────────────────────────────

@router.get("/transactions", response_class=HTMLResponse)
def transactions(request: Request, db: Session = Depends(get_db)):
    owner = current_owner(request, db)
    txns = (
        db.query(Transaction)
        .join(CarPark)
        .filter(CarPark.owner_id == owner.id, Transaction.status == TransactionStatus.paid)
        .order_by(Transaction.parked_at.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse("owner/transactions.html", {
        "request": request, "owner": owner, "transactions": txns,
    })


@router.get("/car-parks/{cp_id}/export-csv")
def export_csv(cp_id: int, request: Request, db: Session = Depends(get_db)):
    owner = current_owner(request, db)
    cp = db.query(CarPark).filter(CarPark.id == cp_id, CarPark.owner_id == owner.id).first()
    if not cp:
        raise HTTPException(status_code=404)
    txns = (
        db.query(Transaction)
        .filter(Transaction.car_park_id == cp_id, Transaction.status == TransactionStatus.paid)
        .order_by(Transaction.parked_at.desc())
        .all()
    )

    def make_aware(dt):
        if dt is None:
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Plate", "Duration", "Amount (£)", "Owner Amount (£)", "Parked At", "Expires At"])
    for t in txns:
        pa = make_aware(t.parked_at)
        ex = make_aware(t.expires_at)
        duration = "All day" if t.is_all_day else f"{t.duration_hours}h"
        writer.writerow([
            t.number_plate,
            duration,
            f"{t.amount_pence / 100:.2f}",
            f"{t.owner_amount_pence / 100:.2f}",
            pa.strftime("%Y-%m-%d %H:%M") if pa else "",
            ex.strftime("%Y-%m-%d %H:%M") if ex else ("All day" if t.is_all_day else ""),
        ])

    output.seek(0)
    filename = f"{cp.slug}-transactions.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Estate page editor ───────────────────────────────────────────────────────

def _estate_slug_for_cp(cp_slug: str) -> str | None:
    """Find the estate slug in ESTATES that has car_park_slug == cp_slug."""
    from ..data.estates import ESTATES
    for estate_slug, data in ESTATES.items():
        if data.get("car_park_slug") == cp_slug:
            return estate_slug
    return None


@router.get("/estate/edit/{cp_slug}", response_class=HTMLResponse)
def edit_estate_page(request: Request, cp_slug: str, db: Session = Depends(get_db)):
    owner = current_owner(request, db)
    cp = db.query(CarPark).filter(CarPark.slug == cp_slug, CarPark.owner_id == owner.id).first()
    if not cp:
        return RedirectResponse("/owner/dashboard", status_code=302)

    from ..data.estates import ESTATES
    estate_slug = _estate_slug_for_cp(cp_slug)
    estate = ESTATES.get(estate_slug, {}) if estate_slug else {}

    # Determine currently active features: custom_features overrides ESTATES dict
    if cp.custom_features:
        try:
            active_features = set(json.loads(cp.custom_features))
        except Exception:
            active_features = set(estate.get("features", []))
    else:
        active_features = set(estate.get("features", []))

    return templates.TemplateResponse("owner/edit_estate.html", {
        "request": request,
        "cp": cp,
        "estate_slug": estate_slug,
        "active_features": active_features,
    })


@router.post("/estate/edit/{cp_slug}")
async def save_estate_page(
    request: Request,
    cp_slug: str,
    db: Session = Depends(get_db),
    logo_url: str = Form(""),
    brand_primary: str = Form("#1a3a2a"),
    brand_accent: str = Form("#c8a84b"),
    brand_text: str = Form("#ffffff"),
    welcome_text: str = Form(""),
    custom_tagline: str = Form(""),
    custom_description: str = Form(""),
):
    owner = current_owner(request, db)
    cp = db.query(CarPark).filter(CarPark.slug == cp_slug, CarPark.owner_id == owner.id).first()
    if not cp:
        return RedirectResponse("/owner/dashboard", status_code=302)

    # Collect checkbox features from raw form data
    form_data = await request.form()
    features = list(form_data.getlist("features"))

    cp.logo_url = logo_url or cp.logo_url
    cp.brand_primary = brand_primary
    cp.brand_accent = brand_accent
    cp.brand_text = brand_text
    cp.welcome_text = welcome_text
    cp.custom_tagline = custom_tagline or None
    cp.custom_description = custom_description or None
    cp.custom_features = json.dumps(features) if features else None
    db.commit()

    return RedirectResponse(f"/owner/estate/edit/{cp_slug}?saved=1", status_code=303)
