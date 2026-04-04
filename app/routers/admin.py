import csv
import io
from collections import Counter
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from jose import JWTError

from ..database import get_db
from ..models import AdminUser, Owner, CarPark, Transaction, TransactionStatus
from ..auth import hash_password, verify_password, create_token, decode_token

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


def current_admin(request: Request, db: Session) -> AdminUser:
    token = request.cookies.get("admin_token")
    if not token:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    try:
        payload = decode_token(token)
        if payload.get("role") != "admin":
            raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
        admin = db.query(AdminUser).filter(AdminUser.id == int(payload["sub"])).first()
        if not admin:
            raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
        return admin
    except JWTError:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})


def make_aware(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# ── Auth ─────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request, "error": None})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = db.query(AdminUser).filter(AdminUser.email == email).first()
    if not admin or not verify_password(password, admin.password_hash):
        return templates.TemplateResponse("admin/login.html", {
            "request": request, "error": "Invalid credentials"
        })
    token = create_token({"sub": str(admin.id), "role": "admin"})
    response = RedirectResponse("/admin/dashboard", status_code=303)
    response.set_cookie("admin_token", token, httponly=True, max_age=43200)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie("admin_token")
    return response


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    current_admin(request, db)
    today = date.today()
    month_start = today.replace(day=1)
    now_utc = datetime.now(timezone.utc)

    # ── Platform totals ──────────────────────────────────────────────────────
    total_revenue = db.query(func.sum(Transaction.amount_pence)).filter(
        Transaction.status == TransactionStatus.paid
    ).scalar() or 0
    total_commission = db.query(func.sum(Transaction.commission_pence)).filter(
        Transaction.status == TransactionStatus.paid
    ).scalar() or 0
    total_txns = db.query(func.count(Transaction.id)).filter(
        Transaction.status == TransactionStatus.paid
    ).scalar() or 0
    avg_txn = round(total_revenue / total_txns / 100, 2) if total_txns else 0
    active_parks = db.query(func.count(CarPark.id)).filter(CarPark.is_active == True).scalar() or 0

    # ── Live car count ───────────────────────────────────────────────────────
    all_paid = db.query(Transaction).filter(Transaction.status == TransactionStatus.paid).all()
    live_count = 0
    for t in all_paid:
        if t.is_all_day:
            pa = make_aware(t.parked_at)
            if pa and (now_utc - pa).days == 0:
                live_count += 1
        else:
            exp = make_aware(t.expires_at)
            if exp and exp > now_utc:
                live_count += 1

    # ── Commission chart (last 6 months) ────────────────────────────────────
    chart_labels = []
    chart_data = []
    for m in range(5, -1, -1):
        month_offset = today.month - m
        year_offset = today.year
        while month_offset <= 0:
            month_offset += 12
            year_offset -= 1
        m_start = date(year_offset, month_offset, 1)
        m_end = date(year_offset, month_offset + 1, 1) if month_offset < 12 else date(year_offset + 1, 1, 1)
        comm = db.query(func.sum(Transaction.commission_pence)).filter(
            Transaction.status == TransactionStatus.paid,
            Transaction.parked_at >= m_start,
            Transaction.parked_at < m_end,
        ).scalar() or 0
        chart_labels.append(m_start.strftime("%b"))
        chart_data.append(round(comm / 100, 2))

    # ── Recent activity (last 20) ────────────────────────────────────────────
    recent_raw = (
        db.query(Transaction)
        .join(CarPark)
        .filter(Transaction.status == TransactionStatus.paid)
        .order_by(Transaction.parked_at.desc())
        .limit(20)
        .all()
    )
    recent = []
    for t in recent_raw:
        pa = make_aware(t.parked_at)
        exp = make_aware(t.expires_at)
        is_live = (
            (t.is_all_day and pa and (now_utc - pa).days == 0) or
            (not t.is_all_day and exp and exp > now_utc)
        )
        recent.append({
            "plate": t.number_plate,
            "duration": "All day" if t.is_all_day else f"{t.duration_hours}h",
            "amount": f"£{t.amount_pence / 100:.2f}",
            "car_park": t.car_park.name,
            "time": pa.strftime("%d %b %H:%M") if pa else "—",
            "live": is_live,
        })

    # ── Intelligence ─────────────────────────────────────────────────────────
    day_counter = Counter()
    days_map = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
    for t in all_paid:
        if t.parked_at:
            day_counter[make_aware(t.parked_at).weekday()] += 1
    busiest_day = days_map[day_counter.most_common(1)[0][0]] if day_counter else "—"

    best_cp_row = (
        db.query(CarPark.name, func.sum(Transaction.amount_pence).label("rev"))
        .join(Transaction)
        .filter(Transaction.status == TransactionStatus.paid, Transaction.parked_at >= month_start)
        .group_by(CarPark.id)
        .order_by(func.sum(Transaction.amount_pence).desc())
        .first()
    )
    best_cp = {"name": best_cp_row[0], "rev": f"£{best_cp_row[1]/100:.2f}"} if best_cp_row else None

    # ── Owner stats ───────────────────────────────────────────────────────────
    owners = db.query(Owner).order_by(Owner.created_at.desc()).all()
    owner_stats = []
    for o in owners:
        rev_all = db.query(func.sum(Transaction.owner_amount_pence)).join(CarPark).filter(
            CarPark.owner_id == o.id, Transaction.status == TransactionStatus.paid
        ).scalar() or 0
        comm_all = db.query(func.sum(Transaction.commission_pence)).join(CarPark).filter(
            CarPark.owner_id == o.id, Transaction.status == TransactionStatus.paid
        ).scalar() or 0
        txn_count = db.query(func.count(Transaction.id)).join(CarPark).filter(
            CarPark.owner_id == o.id, Transaction.status == TransactionStatus.paid
        ).scalar() or 0
        month_rev = db.query(func.sum(Transaction.owner_amount_pence)).join(CarPark).filter(
            CarPark.owner_id == o.id, Transaction.status == TransactionStatus.paid,
            Transaction.parked_at >= month_start,
        ).scalar() or 0
        month_comm = db.query(func.sum(Transaction.commission_pence)).join(CarPark).filter(
            CarPark.owner_id == o.id, Transaction.status == TransactionStatus.paid,
            Transaction.parked_at >= month_start,
        ).scalar() or 0
        owner_stats.append({
            "id": o.id,
            "name": o.name,
            "email": o.email,
            "commission_pct": o.commission_pct,
            "is_active": o.is_active,
            "car_park_count": len(o.car_parks),
            "total_revenue": rev_all,
            "commission": comm_all,
            "txn_count": txn_count,
            "month_rev": month_rev,
            "month_comm": month_comm,
        })

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "total_revenue": total_revenue,
        "total_commission": total_commission,
        "total_txns": total_txns,
        "avg_txn": avg_txn,
        "active_parks": active_parks,
        "live_count": live_count,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
        "recent": recent,
        "busiest_day": busiest_day,
        "best_cp": best_cp,
        "owner_stats": owner_stats,
        "owner_count": len(owners),
        "current_month": today.strftime("%B %Y"),
    })


# ── Owners ────────────────────────────────────────────────────────────────────

@router.get("/owners/new", response_class=HTMLResponse)
def new_owner_page(request: Request, db: Session = Depends(get_db)):
    current_admin(request, db)
    return templates.TemplateResponse("admin/owner_form.html", {
        "request": request, "owner": None, "error": None
    })


@router.post("/owners/new")
def create_owner(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    commission_pct: int = Form(...),
    db: Session = Depends(get_db),
):
    current_admin(request, db)
    if db.query(Owner).filter(Owner.email == email).first():
        return templates.TemplateResponse("admin/owner_form.html", {
            "request": request, "owner": None, "error": "Email already registered"
        })
    owner = Owner(
        name=name, email=email,
        password_hash=hash_password(password),
        commission_pct=commission_pct,
    )
    db.add(owner)
    db.commit()
    return RedirectResponse("/admin/dashboard", status_code=303)


@router.get("/owners/{owner_id}/edit", response_class=HTMLResponse)
def edit_owner_page(owner_id: int, request: Request, db: Session = Depends(get_db)):
    current_admin(request, db)
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("admin/owner_form.html", {
        "request": request, "owner": owner, "error": None
    })


@router.post("/owners/{owner_id}/edit")
def update_owner(
    owner_id: int,
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    commission_pct: int = Form(...),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    current_admin(request, db)
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404)
    owner.name = name
    owner.email = email
    owner.commission_pct = commission_pct
    owner.is_active = is_active
    db.commit()
    return RedirectResponse("/admin/dashboard", status_code=303)


@router.post("/owners/{owner_id}/reset-password")
def reset_owner_password(
    owner_id: int,
    request: Request,
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    current_admin(request, db)
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404)
    owner.password_hash = hash_password(new_password)
    db.commit()
    return RedirectResponse("/admin/dashboard", status_code=303)


# ── Export ────────────────────────────────────────────────────────────────────

@router.get("/export-csv")
def export_all_csv(request: Request, db: Session = Depends(get_db)):
    current_admin(request, db)
    txns = (
        db.query(Transaction)
        .join(CarPark)
        .filter(Transaction.status == TransactionStatus.paid)
        .order_by(Transaction.parked_at.desc())
        .all()
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Car Park", "Plate", "Duration", "Amount (£)", "Commission (£)", "Owner Amount (£)"])
    for t in txns:
        pa = make_aware(t.parked_at)
        writer.writerow([
            pa.strftime("%Y-%m-%d %H:%M") if pa else "",
            t.car_park.name,
            t.number_plate,
            "All day" if t.is_all_day else f"{t.duration_hours}h",
            f"{t.amount_pence / 100:.2f}",
            f"{t.commission_pence / 100:.2f}",
            f"{t.owner_amount_pence / 100:.2f}",
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="parcark-transactions.csv"'},
    )
