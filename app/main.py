from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import admin, auth, manager, public, public_export, test
from app.seed import init_db
from app.services.site_settings import get_all_settings

app = FastAPI(title="SPVT — Система предвахтового тестирования", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app.include_router(public_export.router)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(test.router)
app.include_router(manager.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    site = get_all_settings(db)
    try:
        opacity = float(site.get("hero_overlay_opacity") or "0.75")
    except ValueError:
        opacity = 0.75
    opacity = max(0.0, min(1.0, opacity))
    hero_top = opacity
    hero_bottom = min(opacity + 0.1, 1.0)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "site": site,
            "hero_top": hero_top,
            "hero_bottom": hero_bottom,
        },
    )


@app.get("/worker")
def worker_page():
    return FileResponse(STATIC_DIR / "worker.html")


@app.get("/manager")
def manager_page():
    return FileResponse(STATIC_DIR / "manager.html")
