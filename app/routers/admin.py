from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
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
    owners = db.query(Owner).order_by(Owner.created_at.desc()).all()
    total_revenue = db.query(func.sum(Transaction.amount_pence)).filter(
        Transaction.status == TransactionStatus.paid
    ).scalar() or 0
    total_commission = db.query(func.sum(Transaction.commission_pence)).filter(
        Transaction.status == TransactionStatus.paid
    ).scalar() or 0
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "owners": owners,
        "total_revenue": total_revenue,
        "total_commission": total_commission,
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
        name=name,
        email=email,
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
