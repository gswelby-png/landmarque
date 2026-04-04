from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.database import engine
from app import models
from app.routers import driver, owner, admin

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ParCark")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(driver.router)
app.include_router(owner.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return RedirectResponse("/admin/login")
