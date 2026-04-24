from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ContactEnquiry

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def site_home(request: Request):
    return templates.TemplateResponse("site/home.html", {"request": request})


@router.get("/landowners", response_class=HTMLResponse)
def site_landowners(request: Request):
    return templates.TemplateResponse("site/landowners.html", {"request": request})


@router.get("/landowners/parking", response_class=HTMLResponse)
def site_landowners_parking(request: Request):
    return templates.TemplateResponse("site/landowners_parking.html", {"request": request})


@router.get("/landowners/legacies", response_class=HTMLResponse)
def site_landowners_legacies(request: Request):
    return templates.TemplateResponse("site/landowners_legacies.html", {"request": request})


@router.get("/landowners/benches", response_class=HTMLResponse)
def site_landowners_benches(request: Request):
    return templates.TemplateResponse("site/landowners_benches.html", {"request": request})


@router.get("/landowners/trees", response_class=HTMLResponse)
def site_landowners_trees(request: Request):
    return templates.TemplateResponse("site/landowners_trees.html", {"request": request})


@router.get("/visitors", response_class=HTMLResponse)
def site_visitors(request: Request):
    return templates.TemplateResponse("site/visitors.html", {"request": request})


@router.get("/visitors/parking", response_class=HTMLResponse)
def site_visitors_parking(request: Request):
    return templates.TemplateResponse("site/visitors_parking.html", {"request": request})


@router.get("/visitors/legacies", response_class=HTMLResponse)
def site_visitors_legacies(request: Request):
    return templates.TemplateResponse("site/visitors_legacies.html", {"request": request})


@router.get("/visitors/benches", response_class=HTMLResponse)
def site_visitors_benches(request: Request):
    return templates.TemplateResponse("site/visitors_benches.html", {"request": request})


@router.get("/visitors/trees", response_class=HTMLResponse)
def site_visitors_trees(request: Request):
    return templates.TemplateResponse("site/visitors_trees.html", {"request": request})


@router.get("/about", response_class=HTMLResponse)
def site_about(request: Request):
    return templates.TemplateResponse("site/about.html", {"request": request})


@router.get("/contact", response_class=HTMLResponse)
def site_contact(request: Request, sent: str = ""):
    return templates.TemplateResponse("site/contact.html", {"request": request, "sent": bool(sent)})


@router.post("/contact", response_class=HTMLResponse)
def site_contact_post(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(""),
    message: str = Form(...),
    db: Session = Depends(get_db),
):
    enquiry = ContactEnquiry(name=name, email=email, subject=subject or None, message=message)
    db.add(enquiry)
    db.commit()
    return RedirectResponse(url="/contact?sent=1", status_code=303)
