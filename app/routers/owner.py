from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timezone
from jose import JWTError

from ..database import get_db
from ..models import Owner, CarPark, PricingRule, Transaction, TransactionStatus, DayType
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


# ── Auth ────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("owner/login.html", {"request": request, "error": None})


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
def dashboard(request: Request, db: Session = Depends(get_db)):
    owner = current_owner(request, db)
    today = date.today()
    month_start = today.replace(day=1)

    year_start = today.replace(month=1, day=1)

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
    car_parks = db.query(CarPark).filter(CarPark.owner_id == owner.id).all()

    # Gather pricing rules and recent transactions per car park while session is open
    cp_data = []
    for cp in car_parks:
        rules = db.query(PricingRule).filter(PricingRule.car_park_id == cp.id).order_by(PricingRule.valid_from.desc()).all()
        txns = (
            db.query(Transaction)
            .filter(Transaction.car_park_id == cp.id, Transaction.status == TransactionStatus.paid)
            .order_by(Transaction.parked_at.desc())
            .limit(20)
            .all()
        )
        cp_data.append({
            "id": cp.id,
            "name": cp.name,
            "address": cp.address or "",
            "slug": cp.slug,
            "is_active": cp.is_active,
            "rules": [
                {
                    "day_type": r.day_type.value.title(),
                    "hourly": f"£{r.hourly_rate_pence/100:.2f}/hr",
                    "max_hours": r.max_hourly_hours or "—",
                    "all_day": f"£{r.all_day_pence/100:.2f}" if r.all_day_pence else "—",
                    "valid_from": str(r.valid_from),
                    "valid_to": str(r.valid_to) if r.valid_to else "Open",
                }
                for r in rules
            ],
            "transactions": [
                {
                    "plate": t.number_plate,
                    "duration": "All day" if t.is_all_day else f"{t.duration_hours}hr",
                    "amount": f"£{t.amount_pence/100:.2f}",
                    "share": f"£{t.owner_amount_pence/100:.2f}",
                    "time": t.parked_at.strftime("%d %b %H:%M") if t.parked_at else "—",
                }
                for t in txns
            ],
        })

    return templates.TemplateResponse("owner/dashboard.html", {
        "request": request,
        "owner_name": owner.name,
        "today_revenue": today_revenue,
        "month_revenue": month_revenue,
        "ytd_revenue": ytd_revenue,
        "cp_data": cp_data,
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
    return RedirectResponse(f"/owner/car-parks/{cp_id}/pricing", status_code=303)


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
