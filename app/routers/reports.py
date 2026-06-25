"""Reports API. Gated by the tunnel middleware (remote-only)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlmodel import Session

from .. import reports as R
from ..db import get_session
from ..security import get_current_admin

router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_admin)],
)


def _parse_date(s: str, field: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"არასწორი თარიღი ({field}).")


def _check_range(frm: date, to: date) -> None:
    if frm > to:
        raise HTTPException(status_code=422, detail="საწყისი თარიღი ბოლოზე გვიანია.")


@router.get("/today")
def today(session: Session = Depends(get_session)) -> dict:
    return R.today_summary(session)


@router.get("/daily")
def daily(
    frm: str = Query(alias="from"),
    to: str = Query(alias="to"),
    session: Session = Depends(get_session),
) -> dict:
    f, t = _parse_date(frm, "from"), _parse_date(to, "to")
    _check_range(f, t)
    return {"from": f.isoformat(), "to": t.isoformat(), "rows": R.daily_counts(session, f, t)}


@router.get("/day")
def day(date_str: str = Query(alias="date"), session: Session = Depends(get_session)) -> dict:
    d = _parse_date(date_str, "date")
    rows = R.day_detail(session, d)
    return {
        "date": d.isoformat(),
        "people": len(rows),                      # distinct people who ate
        "meals": sum(r.count for r in rows),      # total meals
        "rows": [
            {"card_id": r.card_id, "count": r.count, "times": r.times}
            for r in rows
        ],
    }


def _filename(prefix: str, frm: date, to: date, ext: str) -> str:
    if frm == to:
        return f"{prefix}_{frm.isoformat()}.{ext}"
    return f"{prefix}_{frm.isoformat()}_{to.isoformat()}.{ext}"


@router.get("/export")
def export_detail(
    frm: str = Query(alias="from"),
    to: str = Query(alias="to"),
    format: str = Query(default="xlsx"),
    session: Session = Depends(get_session),
) -> Response:
    f, t = _parse_date(frm, "from"), _parse_date(to, "to")
    _check_range(f, t)
    rows = R.detail_rows(session, f, t)
    if format == "csv":
        body = R.detail_csv(rows)
        media = "text/csv; charset=utf-8"
        fname = _filename("detail", f, t, "csv")
    else:
        body = R.detail_xlsx(rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        fname = _filename("detail", f, t, "xlsx")
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/attendance")
def export_attendance(
    frm: str = Query(alias="from"),
    to: str = Query(alias="to"),
    format: str = Query(default="xlsx"),
    session: Session = Depends(get_session),
) -> Response:
    f, t = _parse_date(frm, "from"), _parse_date(to, "to")
    _check_range(f, t)
    data = R.attendance(session, f, t)
    if format == "csv":
        body = R.attendance_csv(data)
        media = "text/csv; charset=utf-8"
        fname = _filename("attendance", f, t, "csv")
    else:
        body = R.attendance_xlsx(data)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        fname = _filename("attendance", f, t, "xlsx")
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
