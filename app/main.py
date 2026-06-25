"""FastAPI application entrypoint.

Wires routers, the remote-only tunnel gate, static assets, and the page routes.
On startup it creates the DB and seeds the admin. Validation of unsafe config
happens here too, so importing the app with a weak password fails loudly.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import ConfigError, get_settings, validate_settings
from .db import init_db
from .routers import auth, people, reports, scan
from .seed import run_startup_seed
from .tunnel_gate import TunnelGateMiddleware

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    # Fail loudly on unsafe configuration before serving anything.
    validate_settings(settings)
    init_db()
    run_startup_seed()
    yield


app = FastAPI(title="LUNCH meal-access", lifespan=lifespan, docs_url=None, redoc_url=None)

# Remote-only gate FIRST so it sees every request.
app.add_middleware(TunnelGateMiddleware)

# API routers.
app.include_router(scan.router)      # always-open (offline kiosk)
app.include_router(auth.router)      # gated
app.include_router(people.router)    # gated
app.include_router(reports.router)   # gated

# Static assets (css/js). The gate always allows /static/.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _page(name: str) -> FileResponse:
    return FileResponse(STATIC_DIR / name)


# --- Pages ---------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
def kiosk_page() -> FileResponse:
    # Always-open: the kiosk scan screen.
    return _page("kiosk.html")


@app.get("/kiosk-test", include_in_schema=False)
def kiosk_test_page() -> FileResponse:
    # Local-only helper for testing the real kiosk flow without a card reader.
    return _page("kiosk-test.html")


@app.get("/login", include_in_schema=False)
def login_page() -> FileResponse:
    return _page("login.html")


@app.get("/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    return _page("admin.html")


@app.get("/reports", include_in_schema=False)
def reports_page() -> FileResponse:
    return _page("reports.html")


@app.get("/healthz", include_in_schema=False)
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.get("/api/version", include_in_schema=False)
def version() -> JSONResponse:
    from . import __version__
    return JSONResponse({"version": __version__})
