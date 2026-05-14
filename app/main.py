from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import auth, manager, public_export, test
from app.seed import init_db

app = FastAPI(title="SPVT — Система предвахтового тестирования", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"

app.include_router(public_export.router)
app.include_router(auth.router)
app.include_router(test.router)
app.include_router(manager.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/worker")
def worker_page():
    return FileResponse(STATIC_DIR / "worker.html")


@app.get("/manager")
def manager_page():
    return FileResponse(STATIC_DIR / "manager.html")
