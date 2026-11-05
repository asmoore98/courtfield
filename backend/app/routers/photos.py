"""Photos on leads and estimates, straight from a phone's camera roll.

The phone shrinks each photo and makes a small preview before sending them,
so a photo is a few hundred KB. They're kept in the database for now; when
the company Google Drive is connected they can move there (`storage`).
An estimate also shows the photos on the lead it came from.
"""
import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from ..activity import iso, log
from ..auth import EDITS_JOBS, SALES_SIDE, current_user
from ..db import get_db
from ..models import JobTask, Photo, Role, User, utcnow

router = APIRouter(prefix="/api/photos", tags=["photos"])
# Leads and estimates: the sales side. Jobs: the crew lead on it and the office.
WHO = {"lead": SALES_SIDE, "estimate": SALES_SIDE, "job": EDITS_JOBS | {Role.crew_lead, Role.owner},
       "task": EDITS_JOBS | {Role.crew_lead, Role.owner}}  # a task on a job: done or partly done

MAX_PHOTO = 4 * 1024 * 1024   # after the phone shrinks it; well over what it sends
MAX_THUMB = 400 * 1024
MAX_PER_SUBJECT = 300
KINDS = ("lead", "estimate", "job", "task")


class PhotoIn(BaseModel):
    kind: str = Field(pattern="^(lead|estimate|job|task)$")
    subject_id: str = Field(min_length=1, max_length=36)
    name: str = Field(default="", max_length=200)
    caption: str = Field(default="", max_length=500)
    data: str = Field(min_length=10)   # base64
    thumb: str = Field(min_length=10)  # base64


class RemoveIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


def _image_type(raw: bytes) -> str | None:
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def _decode(text: str, limit: int, what: str) -> tuple[bytes, str]:
    if len(text) > limit * 4 // 3 + 16:
        raise HTTPException(413, f"That {what} is too big. Try again; the app shrinks photos before sending.")
    try:
        raw = base64.b64decode(text.split(",", 1)[-1], validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, f"That {what} didn't come through. Try adding it again.")
    kind = _image_type(raw)
    if kind is None:
        raise HTTPException(422, "Only photos (JPEG, PNG or WebP) can be added.")
    return raw, kind


def check_subject(db: Session, user: User, kind: str, subject_id: str):
    """The lead, estimate or job, if this person can see it (sales: their
    own leads; a crew lead: the jobs sent to them)."""
    if user.role not in WHO.get(kind, ()):
        raise HTTPException(403, "Your role can't do that")
    if kind == "job":
        from .jobs import load_job
        return load_job(db, user, subject_id)
    if kind == "task":
        from ..models import JobTask
        from .jobs import load_job
        t = db.scalar(select(JobTask).where(JobTask.id == subject_id, JobTask.company_id == user.company_id))
        if t is None:
            raise HTTPException(404, "Task not found")
        load_job(db, user, t.job_id)  # a crew lead: only their own jobs
        return t
    if kind == "lead":
        from .leads import load_lead
        return load_lead(db, user, subject_id)
    if kind == "estimate":
        from .estimates import load_estimate
        return load_estimate(db, user, subject_id)
    raise HTTPException(422, "Photos go on a lead, an estimate or a job")


def photo_out(p: Photo, user: User, source: str | None = None) -> dict:
    return {"id": p.id, "name": p.name, "caption": p.caption, "size": p.size, "by": p.created_by.name,
            "at": iso(p.created_at), "from": source,  # "lead" when shown on an estimate
            "can_remove": user.role == Role.gm or p.created_by_id == user.id}


def _live(db: Session, company_id: str, kind: str, subject_id: str) -> list[Photo]:
    return list(db.scalars(select(Photo).where(Photo.company_id == company_id, Photo.kind == kind, Photo.subject_id == subject_id,
                                               Photo.removed_at.is_(None)).order_by(Photo.created_at)))


@router.get("")
def list_photos(kind: str = Query(pattern="^(lead|estimate|job|task)$"), id: str = Query(max_length=36),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    subject = check_subject(db, user, kind, id)
    out = [photo_out(p, user) for p in _live(db, user.company_id, kind, id)]
    if kind == "estimate" and subject.lead_id:  # what sales took on site comes along
        out = [photo_out(p, user, "lead") for p in _live(db, user.company_id, "lead", subject.lead_id)] + out
    return out


@router.post("", status_code=201)
def add_photo(body: PhotoIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    subject = check_subject(db, user, body.kind, body.subject_id)
    if len(_live(db, user.company_id, body.kind, body.subject_id)) >= MAX_PER_SUBJECT:
        raise HTTPException(409, f"This {body.kind} already has {MAX_PER_SUBJECT} photos.")
    data, kind = _decode(body.data, MAX_PHOTO, "photo")
    thumb, _ = _decode(body.thumb, MAX_THUMB, "preview")
    p = Photo(company_id=user.company_id, kind=body.kind, subject_id=body.subject_id, name=body.name.strip(),
              caption=body.caption.strip(), content_type=kind, size=len(data), data=data, thumb=thumb, created_by_id=user.id)
    db.add(p)
    db.flush()
    if body.kind == "task":  # in the job's history, saying which task
        log(db, user, "job", subject.job_id, f"Added a photo to {subject.name}", p.name)
    else:
        log(db, user, body.kind, body.subject_id, "Added a photo", p.name)
    db.commit()
    return photo_out(p, user)


def _load(db: Session, user: User, photo_id: str) -> Photo:
    p = db.scalar(select(Photo).where(Photo.id == photo_id, Photo.company_id == user.company_id))
    if p is None:
        raise HTTPException(404, "Photo not found")
    check_subject(db, user, p.kind, p.subject_id)  # only people who can see the lead or estimate
    return p


@router.get("/{photo_id}")
def get_photo(photo_id: str, size: str = Query(default="full", pattern="^(full|thumb)$"),
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _load(db, user, photo_id)
    if p.removed_at is not None:
        raise HTTPException(404, "That photo was removed")
    raw = db.scalar(select(Photo).where(Photo.id == p.id).options(undefer(Photo.data if size == "full" else Photo.thumb)))
    body = raw.data if size == "full" else raw.thumb
    return Response(body, media_type=p.content_type if size == "full" else _image_type(body) or "image/jpeg",
                    headers={"Cache-Control": "private, max-age=86400"})


@router.post("/{photo_id}/remove")
def remove_photo(photo_id: str, body: RemoveIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Taken off the lead, never deleted: the GM, or whoever added it."""
    p = _load(db, user, photo_id)
    if user.role != Role.gm and p.created_by_id != user.id:
        raise HTTPException(403, "Only the GM or whoever added a photo can remove it.")
    if p.removed_at is None:
        p.removed_at, p.removed_by_id, p.removed_reason = utcnow(), user.id, body.reason.strip()
        where = ("job", db.get(JobTask, p.subject_id).job_id) if p.kind == "task" else (p.kind, p.subject_id)
        log(db, user, *where, "Removed a photo", f"{p.name}: {body.reason.strip()}" if p.name else body.reason.strip())
        db.commit()
    return {"ok": True}
