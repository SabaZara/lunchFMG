"""Automated acceptance tests covering spec section 16 (Definition of Done).

Card IDs are typed (no physical reader), exactly as in production testing.
"""
from __future__ import annotations

import io
import threading
from datetime import date, timedelta

import pytest
from openpyxl import Workbook, load_workbook
from sqlmodel import Session, select


# --------------------------- helpers --------------------------------------- #
def _login(ctx):
    r = ctx["client"].post(
        "/api/login",
        headers=ctx["headers"],
        json={"username": ctx["admin_user"], "password": ctx["admin_pass"]},
    )
    assert r.status_code == 200, r.text


def _seed_cards(ctx):
    with Session(ctx["db"].engine) as s:
        ctx["seed"].seed_sample_cards(s)


def _make_xlsx(values, header=None):
    wb = Workbook()
    ws = wb.active
    if header:
        ws.append([header])
    for v in values:
        ws.append([v])  # one card id per line, first column
    # Force text format so openpyxl doesn't coerce to number on read-back.
    for row in ws.iter_rows(min_col=1, max_col=1):
        for c in row:
            c.number_format = "@"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --------------------------- scan behaviour -------------------------------- #
def test_known_active_card_allowed_and_records(app_ctx):
    ctx = app_ctx
    _seed_cards(ctx)
    r = ctx["client"].post("/api/scan", json={"card_id": "1001"})
    j = r.json()
    assert j["status"] == "ALLOWED"
    assert j["scanned_at"]  # local time string present


def test_same_card_same_day_denied(app_ctx):
    ctx = app_ctx
    _seed_cards(ctx)
    ctx["client"].post("/api/scan", json={"card_id": "1001"})
    j = ctx["client"].post("/api/scan", json={"card_id": "1001"}).json()
    assert j["status"] == "DENIED"
    assert j["reason"] == "დღეს უკვე ნაჭამია"


def test_unknown_card_denied(app_ctx):
    ctx = app_ctx
    _seed_cards(ctx)
    j = ctx["client"].post("/api/scan", json={"card_id": "DOES-NOT-EXIST"}).json()
    assert j["status"] == "DENIED"
    assert j["reason"] == "უცნობი ბარათი"


def test_inactive_card_denied(app_ctx):
    ctx = app_ctx
    _seed_cards(ctx)
    j = ctx["client"].post("/api/scan", json={"card_id": "9999"}).json()
    assert j["status"] == "DENIED"
    assert j["reason"] == "ბარათი გათიშულია"


def test_midnight_reset(app_ctx):
    """A card allowed 'yesterday' is allowed again 'today'.

    We simulate by inserting a scan row with yesterday's local_date directly,
    then a fresh scan today must be ALLOWED.
    """
    ctx = app_ctx
    _seed_cards(ctx)
    from app.models import Person, Scan
    from app.timeutil import local_date_for, utc_now

    with Session(ctx["db"].engine) as s:
        p = s.exec(select(Person).where(Person.card_id == "1002")).first()
        tz = ctx["settings"].tz
        today = local_date_for(utc_now(), tz)
        yesterday = today - timedelta(days=1)
        s.add(Scan(person_id=p.id, card_id="1002", scanned_at=utc_now(), local_date=yesterday))
        s.commit()

    # Today's scan should still be allowed.
    j = ctx["client"].post("/api/scan", json={"card_id": "1002"}).json()
    assert j["status"] == "ALLOWED"


def test_concurrent_taps_exactly_one_allowed(app_ctx):
    """Once-per-day holds under concurrency: exactly one ALLOWED."""
    ctx = app_ctx
    _seed_cards(ctx)
    results = []
    lock = threading.Lock()

    def tap():
        r = ctx["client"].post("/api/scan", json={"card_id": "1003"})
        with lock:
            results.append(r.json()["status"])

    threads = [threading.Thread(target=tap) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    allowed = sum(1 for s in results if s == "ALLOWED")
    assert allowed == 1, f"expected exactly one ALLOWED, got {allowed}: {results}"


def test_leading_zeros_preserved_through_scan(app_ctx):
    ctx = app_ctx
    _seed_cards(ctx)
    j = ctx["client"].post("/api/scan", json={"card_id": "0573856032"}).json()
    assert j["status"] == "ALLOWED"
    # And it must be denied on a second tap by the SAME exact string.
    j2 = ctx["client"].post("/api/scan", json={"card_id": "0573856032"}).json()
    assert j2["status"] == "DENIED"


# --------------------------- admin / CRUD ---------------------------------- #
def test_admin_crud_and_unique_enforcement(app_ctx):
    ctx = app_ctx
    _login(ctx)
    H = ctx["headers"]
    c = ctx["client"]

    # add
    r = c.post("/api/people", headers=H, json={"card_id": "AAA111"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["full_name"] == "----"  # placeholder default

    # duplicate rejected with Georgian error
    r = c.post("/api/people", headers=H, json={"card_id": "AAA111"})
    assert r.status_code == 409
    assert "მინიჭებულია" in r.json()["detail"]

    # edit (reassign card id)
    r = c.put(f"/api/people/{pid}", headers=H, json={"card_id": "BBB222"})
    assert r.status_code == 200 and r.json()["card_id"] == "BBB222"

    # deactivate
    r = c.put(f"/api/people/{pid}", headers=H, json={"active": False})
    assert r.json()["active"] is False

    # delete
    r = c.delete(f"/api/people/{pid}", headers=H)
    assert r.status_code == 204


def test_import_250_xlsx_leading_zeros(app_ctx):
    ctx = app_ctx
    _login(ctx)
    H = ctx["headers"]
    c = ctx["client"]

    ids = [f"{i:010d}" for i in range(1, 251)]  # 250 ids, all with leading zeros
    data = _make_xlsx(ids, header="card_id")  # tolerate header
    r = c.post(
        "/api/people/import",
        headers=H,
        files={"file": ("cards.xlsx", data,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    rep = r.json()
    assert rep["added"] == 250, rep
    assert rep["duplicate_count"] == 0

    # leading zeros preserved in DB
    listed = c.get("/api/people?q=0000000001", headers=H).json()
    assert any(p["card_id"] == "0000000001" for p in listed)

    # re-import same file -> all duplicates, none added
    r2 = c.post(
        "/api/people/import",
        headers=H,
        files={"file": ("cards.xlsx", data,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r2.json()["added"] == 0
    assert r2.json()["duplicate_count"] == 250


def test_import_reports_failures_by_row(app_ctx):
    ctx = app_ctx
    _login(ctx)
    H = ctx["headers"]
    c = ctx["client"]
    # rows: header, A, blank(skip), A(dup), B
    wb = Workbook(); ws = wb.active
    ws.append(["card_id"])
    ws.append(["A001"])
    ws.append([""])         # blank skipped
    ws.append(["A001"])     # duplicate within file -> row 4
    ws.append(["B002"])
    buf = io.BytesIO(); wb.save(buf)
    r = c.post("/api/people/import", headers=H,
               files={"file": ("c.xlsx", buf.getvalue(), "application/octet-stream")})
    rep = r.json()
    assert rep["added"] == 2
    assert rep["duplicate_count"] == 1
    assert rep["duplicates"][0]["row"] == 4


def test_csv_import_bom_tolerant(app_ctx):
    ctx = app_ctx
    _login(ctx)
    H = ctx["headers"]
    c = ctx["client"]
    csv_bytes = "﻿card_id\n0012\n0034\n".encode("utf-8")
    r = c.post("/api/people/import", headers=H,
               files={"file": ("c.csv", csv_bytes, "text/csv")})
    rep = r.json()
    assert rep["added"] == 2
    listed = c.get("/api/people?q=0012", headers=H).json()
    assert any(p["card_id"] == "0012" for p in listed)


# --------------------------- reports / exports ----------------------------- #
def test_today_report_counts(app_ctx):
    ctx = app_ctx
    _seed_cards(ctx)
    _login(ctx)
    ctx["client"].post("/api/scan", json={"card_id": "1001"})
    t = ctx["client"].get("/api/reports/today", headers=ctx["headers"]).json()
    assert t["ate"] == 1
    assert t["active"] >= 1
    assert t["remaining"] == t["active"] - t["ate"]


def test_attendance_xlsx_is_georgian_and_by_cardid(app_ctx):
    ctx = app_ctx
    _seed_cards(ctx)
    _login(ctx)
    H = ctx["headers"]
    ctx["client"].post("/api/scan", json={"card_id": "1001"})
    today = date.today().isoformat()
    r = ctx["client"].get(f"/api/reports/attendance?from={today}&to={today}&format=xlsx", headers=H)
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    wb = load_workbook(io.BytesIO(r.content))
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert "ბარათის ID" in headers and "სტატუსი" in headers
    # status cells use Georgian "ჭამა" / "არ უჭამია"
    statuses = {ws.cell(row=i, column=2).value for i in range(2, ws.max_row + 1)}
    assert statuses & {"ჭამა", "არ უჭამია"}


def test_detail_csv_export(app_ctx):
    ctx = app_ctx
    _seed_cards(ctx)
    _login(ctx)
    H = ctx["headers"]
    ctx["client"].post("/api/scan", json={"card_id": "0573856032"})
    today = date.today().isoformat()
    r = ctx["client"].get(f"/api/reports/export?from={today}&to={today}&format=csv", headers=H)
    assert r.status_code == 200
    text = r.content.decode("utf-8-sig")
    assert "ბარათის ID" in text
    assert "0573856032" in text  # leading zeros preserved in export


# --------------------------- security / gating ----------------------------- #
def test_admin_blocked_without_tunnel_secret(app_ctx):
    ctx = app_ctx
    c = ctx["client"]
    # No secret header -> 403 on all protected surfaces.
    assert c.get("/admin").status_code == 403
    assert c.get("/reports").status_code == 403
    assert c.post("/api/login", json={"username": "x", "password": "y"}).status_code == 403
    assert c.get("/api/people").status_code == 403
    assert c.get("/api/reports/today").status_code == 403


def test_scan_page_and_api_always_open(app_ctx):
    ctx = app_ctx
    c = ctx["client"]
    # No secret header, kiosk still works (offline behaviour).
    assert c.get("/").status_code == 200
    assert c.post("/api/scan", json={"card_id": "whatever"}).status_code == 200


def test_login_rate_limit(app_ctx):
    ctx = app_ctx
    H = ctx["headers"]
    c = ctx["client"]
    last = None
    for _ in range(6):
        last = c.post("/api/login", headers=H,
                      json={"username": ctx["admin_user"], "password": "wrong"})
    # After 5 failures the 6th is locked out (429).
    assert last.status_code == 429
    assert "მცდელობა" in last.json()["detail"]


def test_weak_password_refused():
    """validate_settings refuses a weak admin password."""
    from app.config import ConfigError, Settings, validate_settings

    s = Settings(
        timezone="Asia/Tbilisi",
        admin_username="admin",
        admin_password="changeme",
        secret_key="x" * 48,
        tunnel_secret="t" * 16,
        host="127.0.0.1",
        port=8000,
        db_path=__import__("pathlib").Path("x.db"),
    )
    with pytest.raises(ConfigError):
        validate_settings(s)


def test_missing_secret_key_refused():
    from app.config import ConfigError, Settings, validate_settings

    s = Settings(
        timezone="Asia/Tbilisi",
        admin_username="admin",
        admin_password="StrongPass!123",
        secret_key="short",
        tunnel_secret="t" * 16,
        host="127.0.0.1",
        port=8000,
        db_path=__import__("pathlib").Path("x.db"),
    )
    with pytest.raises(ConfigError):
        validate_settings(s)
