"""
LandMarque Visitor App
======================
Completely separate FastAPI application for the consumer-facing side:

  /explore/*         — Estate discovery portal (map, estate list, estate pages)
  /location/*        — Individual estate visitor apps (parking, walking, etc.)
  /park, /payment, /receipt, /check  — Driver payment & receipt flows

Deployed as a separate Railway service from main.py (the B2B owner site).
Both services share the same DATABASE_URL / PostgreSQL instance.
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import HTTPException

from app.database import engine, SessionLocal
from app import models
from app.routers import driver, location
from app.data.estates import ESTATES

# Ensure tables exist (safe to call on every startup — CREATE IF NOT EXISTS)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="LandMarque Visitor")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# ── Estate visitor apps ───────────────────────────────────────────────────────

app.include_router(location.router, prefix="/location")

# ── Driver payment / receipt flows ────────────────────────────────────────────

app.include_router(driver.router)

# ── Consumer estate discovery portal ─────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def visitor_root(request: Request):
    return RedirectResponse(url="/explore", status_code=301)


@app.get("/explore", response_class=HTMLResponse)
def explore_home(request: Request):
    featured_slugs = [
        "shere-manor-estate", "chatsworth-estate", "blenheim-palace",
        "holkham-estate", "castle-howard", "culzean-castle",
    ]
    featured = [{"slug": s, **ESTATES[s]} for s in featured_slugs if s in ESTATES]
    return templates.TemplateResponse(
        "explore/home.html", {"request": request, "featured": featured}
    )


@app.get("/explore/estates", response_class=HTMLResponse)
def explore_estates(request: Request):
    estates_list = [{"slug": slug, **data} for slug, data in ESTATES.items()]
    return templates.TemplateResponse(
        "explore/estates.html", {"request": request, "estates": estates_list}
    )


@app.get("/explore/{slug}", response_class=HTMLResponse)
def explore_estate(request: Request, slug: str):
    estate = ESTATES.get(slug)
    if not estate:
        return RedirectResponse(url="/explore/estates", status_code=302)
    return templates.TemplateResponse(
        "explore/estate.html", {"request": request, "slug": slug, "estate": estate}
    )


# ── Convenience redirects ─────────────────────────────────────────────────────

@app.get("/payment")
def payment_redirect():
    return RedirectResponse("/payment/shere-manor", status_code=302)


@app.get("/receipt")
def receipt_redirect():
    return RedirectResponse("/receipt/shere-manor", status_code=302)


# ── Crawlers ──────────────────────────────────────────────────────────────────

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nAllow: /explore/\nAllow: /\nDisallow: /check/\n"


# ── Error pages ───────────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found(request: Request, exc: HTTPException):
    return HTMLResponse(
        templates.get_template("errors/404.html").render({"request": request}),
        status_code=404,
    )
