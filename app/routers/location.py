from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Known estate slugs — extend as new estates are onboarded
ESTATES = {
    "shere-manor-estate": {
        "name": "Shere Manor Estate",
        "tagline": "A private estate in the heart of the Surrey Hills.",
    },
}


def _get_estate(slug: str):
    return ESTATES.get(slug)


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
