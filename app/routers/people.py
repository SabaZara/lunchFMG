"""Card (people) management API. Gated by the tunnel middleware (remote-only).

Works with card_id only; name/department are kept in the DB but not surfaced.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..config import get_settings
from ..db import get_session
from ..importer import import_cards
from ..models import NAME_PLACEHOLDER, Person, Scan
from ..scan_service import normalize_card_id
from ..security import get_current_admin
from ..timeutil import local_date_for, utc_now

router = APIRouter(prefix="/api/people", tags=["people"], dependencies=[Depends(get_current_admin)])

DUPLICATE_MSG = "ეს ბარათი უკვე მინიჭებულია."


class PersonOut(BaseModel):
    id: int
    card_id: str
    active: bool
    ate_today: bool
    # Present but hidden in the UI for now (kept so re-enabling is trivial).
    full_name: str
    department: str | None = None


class PersonCreate(BaseModel):
    card_id: str
    active: bool = True


class PersonUpdate(BaseModel):
    card_id: str | None = None
    active: bool | None = None
    full_name: str | None = None
    department: str | None = None


def _ate_today_ids(session: Session) -> set[int]:
    tz = get_settings().tz
    today = local_date_for(utc_now(), tz)
    rows = session.exec(select(Scan.person_id).where(Scan.local_date == today)).all()
    return set(rows)


def _to_out(p: Person, ate_today: bool) -> PersonOut:
    return PersonOut(
        id=p.id,
        card_id=p.card_id,
        active=p.active,
        ate_today=ate_today,
        full_name=p.full_name,
        department=p.department,
    )


@router.get("", response_model=list[PersonOut])
def list_people(
    q: str | None = None,
    session: Session = Depends(get_session),
) -> list[PersonOut]:
    stmt = select(Person)
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(Person.card_id.like(needle))
    stmt = stmt.order_by(Person.card_id)
    people = session.exec(stmt).all()
    ate = _ate_today_ids(session)
    return [_to_out(p, p.id in ate) for p in people]


@router.post("", response_model=PersonOut, status_code=201)
def create_person(
    payload: PersonCreate,
    session: Session = Depends(get_session),
) -> PersonOut:
    card_id = normalize_card_id(payload.card_id)
    if not card_id:
        raise HTTPException(status_code=422, detail="ბარათის ID სავალდებულოა.")
    person = Person(card_id=card_id, full_name=NAME_PLACEHOLDER, active=payload.active)
    session.add(person)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE_MSG)
    session.refresh(person)
    return _to_out(person, False)


@router.put("/{person_id}", response_model=PersonOut)
def update_person(
    person_id: int,
    payload: PersonUpdate,
    session: Session = Depends(get_session),
) -> PersonOut:
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="ბარათი ვერ მოიძებნა.")

    if payload.card_id is not None:
        new_id = normalize_card_id(payload.card_id)
        if not new_id:
            raise HTTPException(status_code=422, detail="ბარათის ID სავალდებულოა.")
        person.card_id = new_id
    if payload.active is not None:
        person.active = payload.active
    if payload.full_name is not None:
        person.full_name = payload.full_name
    if payload.department is not None:
        person.department = payload.department

    session.add(person)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE_MSG)
    session.refresh(person)
    ate = _ate_today_ids(session)
    return _to_out(person, person.id in ate)


@router.delete("/{person_id}")
def delete_person(person_id: int, session: Session = Depends(get_session)) -> Response:
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="ბარათი ვერ მოიძებნა.")
    # Remove the person's scan history too (delete = full removal).
    for s in session.exec(select(Scan).where(Scan.person_id == person_id)).all():
        session.delete(s)
    session.delete(person)
    session.commit()
    return Response(status_code=204)


@router.post("/import")
async def import_people(
    file: UploadFile,
    session: Session = Depends(get_session),
) -> dict:
    data = await file.read()
    report = import_cards(session, file.filename or "", data)
    return report.as_dict()
