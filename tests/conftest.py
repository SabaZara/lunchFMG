"""Test fixtures: a fresh temp DB + configured env per test session.

We set environment variables BEFORE importing the app so config picks them up,
then build a TestClient (which runs the lifespan: init_db + seed admin).
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ADMIN_USER = "admin"
ADMIN_PASS = "StrongTestPass!2026"


@pytest.fixture()
def app_ctx(monkeypatch):
    """Yield (client, settings, modules) with a fresh DB for each test."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")

    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("TIMEZONE", "Asia/Tbilisi")
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN_USER)
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASS)
    monkeypatch.setenv("SECRET_KEY", "x" * 48)
    monkeypatch.setenv("TUNNEL_SECRET", "tunnel-secret-value-123456")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "8000")

    # Reload config/db/app so the new env + fresh engine take effect.
    import app.config as config
    importlib.reload(config)
    config.get_settings.cache_clear()
    settings = config.get_settings()

    import app.db as db
    importlib.reload(db)
    import app.security as security
    importlib.reload(security)
    import app.scan_service as scan_service
    importlib.reload(scan_service)
    import app.seed as seed
    importlib.reload(seed)
    import app.tunnel_gate as tunnel_gate
    importlib.reload(tunnel_gate)
    import app.importer as importer
    importlib.reload(importer)
    import app.reports as reports
    importlib.reload(reports)
    # Routers import the reloaded modules.
    import app.routers.scan, app.routers.auth, app.routers.people, app.routers.reports  # noqa
    importlib.reload(app.routers.scan)
    importlib.reload(app.routers.auth)
    importlib.reload(app.routers.people)
    importlib.reload(app.routers.reports)
    import app.main as main
    importlib.reload(main)

    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        yield {
            "client": client,
            "settings": settings,
            "db": db,
            "seed": seed,
            "importer": importer,
            "reports": reports,
            "scan_service": scan_service,
            "headers": {"x-tunnel-secret": settings.tunnel_secret},
            "admin_user": ADMIN_USER,
            "admin_pass": ADMIN_PASS,
        }
