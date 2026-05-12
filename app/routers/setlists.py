from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, func, insert, select, update

from ..dependencies import get_current_user, get_db
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..tables import band_members, bands, setlist_songs, setlists

router = APIRouter(prefix="", tags=["setlists"])


class SetlistCreateRequest(BaseModel):
    band_id: int
    name: str
    gig_id: int | None = None


class SetlistUpdateRequest(BaseModel):
    name: str | None = None
    gig_id: int | None = None


class SetlistSongCreateRequest(BaseModel):
    title: str
    artist: str | None = None
    duration_minutes: float


class SetlistSongUpdateRequest(BaseModel):
    title: str | None = None
    artist: str | None = None
    duration_minutes: float | None = None
    order: int | None = None


def _ensure_band_member(band_id: int, current_user, db):
    if current_user["role"] == "ADMIN":
        return
    member = (
        db.execute(
            select(band_members.c.member_id).where(
                band_members.c.band_id == band_id,
                band_members.c.user_id == current_user["user_id"],
            )
        ).first()
    )
    if not member:
        raise_app_error("FORBIDDEN", "Band member only", status_code=403)


@router.get("/bands/{band_id}/setlists")
def list_setlists(
    band_id: int,
    page: int | None = None,
    limit: int | None = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    _ensure_band_member(band_id, current_user, db)
    page, limit, offset = get_pagination(page, limit)

    stmt = (
        select(
            setlists.c.setlist_id,
            setlists.c.setlist_name,
            setlists.c.gig_id,
            setlists.c.created_at,
        )
        .where(setlists.c.band_id == band_id)
        .order_by(setlists.c.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    total = (
        db.execute(select(func.count()).select_from(setlists).where(setlists.c.band_id == band_id))
        .scalar_one()
        or 0
    )
    rows = db.execute(stmt).mappings().all()

    song_counts = {}
    if rows:
        ids = [row["setlist_id"] for row in rows]
        count_rows = (
            db.execute(
                select(setlist_songs.c.setlist_id, func.count().label("song_count"))
                .where(setlist_songs.c.setlist_id.in_(ids))
                .group_by(setlist_songs.c.setlist_id)
            )
            .mappings()
            .all()
        )
        for row in count_rows:
            song_counts[row["setlist_id"]] = row["song_count"]

    return {
        "total": total,
        "page": page,
        "setlists": [
            {
                "setlist_id": row["setlist_id"],
                "name": row["setlist_name"],
                "gig_id": row["gig_id"],
                "song_count": song_counts.get(row["setlist_id"], 0),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
            for row in rows
        ],
    }


@router.post("/setlists", status_code=201)
def create_setlist(
    payload: SetlistCreateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    _ensure_band_member(payload.band_id, current_user, db)

    row = (
        db.execute(
            insert(setlists)
            .values(band_id=payload.band_id, setlist_name=payload.name, gig_id=payload.gig_id)
            .returning(setlists.c.setlist_id, setlists.c.setlist_name, setlists.c.created_at)
        )
        .mappings()
        .first()
    )

    return {
        "setlist_id": row["setlist_id"],
        "name": row["setlist_name"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.get("/setlists/{setlist_id}")
def get_setlist(
    setlist_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    setlist = db.execute(select(setlists).where(setlists.c.setlist_id == setlist_id)).mappings().first()
    if not setlist:
        raise_app_error("NOT_FOUND", "Setlist not found", status_code=404)
    _ensure_band_member(setlist["band_id"], current_user, db)

    song_rows = (
        db.execute(
            select(setlist_songs)
            .where(setlist_songs.c.setlist_id == setlist_id)
            .order_by(setlist_songs.c.song_order.asc())
        )
        .mappings()
        .all()
    )
    total_duration = sum(float(row["duration_minutes"]) for row in song_rows)

    return {
        "setlist_id": setlist["setlist_id"],
        "name": setlist["setlist_name"],
        "band_id": setlist["band_id"],
        "gig_id": setlist["gig_id"],
        "songs": [
            {
                "song_id": row["song_id"],
                "title": row["song_title"],
                "artist": row["artist_name"],
                "duration_minutes": float(row["duration_minutes"]),
                "order": row["song_order"],
            }
            for row in song_rows
        ],
        "total_duration": total_duration,
    }


@router.get("/setlists/{setlist_id}/songs")
def list_setlist_songs(
    setlist_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    setlist = db.execute(select(setlists).where(setlists.c.setlist_id == setlist_id)).mappings().first()
    if not setlist:
        raise_app_error("NOT_FOUND", "Setlist not found", status_code=404)
    _ensure_band_member(setlist["band_id"], current_user, db)

    song_rows = (
        db.execute(
            select(setlist_songs)
            .where(setlist_songs.c.setlist_id == setlist_id)
            .order_by(setlist_songs.c.song_order.asc())
        )
        .mappings()
        .all()
    )
    return {
        "setlist_id": setlist_id,
        "songs": [
            {
                "song_id": row["song_id"],
                "title": row["song_title"],
                "artist": row["artist_name"],
                "duration_minutes": float(row["duration_minutes"]),
                "order": row["song_order"],
            }
            for row in song_rows
        ],
    }


@router.put("/setlists/{setlist_id}")
def update_setlist(
    setlist_id: int,
    payload: SetlistUpdateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    setlist = db.execute(select(setlists).where(setlists.c.setlist_id == setlist_id)).mappings().first()
    if not setlist:
        raise_app_error("NOT_FOUND", "Setlist not found", status_code=404)
    _ensure_band_member(setlist["band_id"], current_user, db)

    update_values = {}
    if payload.name is not None:
        update_values["setlist_name"] = payload.name
    if payload.gig_id is not None:
        update_values["gig_id"] = payload.gig_id

    now = datetime.now(timezone.utc)
    if update_values:
        update_values["last_updated"] = now
        db.execute(update(setlists).where(setlists.c.setlist_id == setlist_id).values(**update_values))

    return {"setlist_id": setlist_id, "updated_at": now.isoformat()}


@router.delete("/setlists/{setlist_id}")
def delete_setlist(
    setlist_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    setlist = db.execute(select(setlists).where(setlists.c.setlist_id == setlist_id)).mappings().first()
    if not setlist:
        raise_app_error("NOT_FOUND", "Setlist not found", status_code=404)
    _ensure_band_member(setlist["band_id"], current_user, db)

    db.execute(delete(setlist_songs).where(setlist_songs.c.setlist_id == setlist_id))
    db.execute(delete(setlists).where(setlists.c.setlist_id == setlist_id))
    return {"message": "Setlist deleted"}


@router.post("/setlists/{setlist_id}/songs", status_code=201)
def add_song(
    setlist_id: int,
    payload: SetlistSongCreateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    setlist = db.execute(select(setlists).where(setlists.c.setlist_id == setlist_id)).mappings().first()
    if not setlist:
        raise_app_error("NOT_FOUND", "Setlist not found", status_code=404)
    _ensure_band_member(setlist["band_id"], current_user, db)

    max_order = (
        db.execute(
            select(func.coalesce(func.max(setlist_songs.c.song_order), 0)).where(
                setlist_songs.c.setlist_id == setlist_id
            )
        )
        .scalar_one()
        or 0
    )
    row = (
        db.execute(
            insert(setlist_songs)
            .values(
                setlist_id=setlist_id,
                song_title=payload.title,
                artist_name=payload.artist,
                duration_minutes=payload.duration_minutes,
                song_order=max_order + 1,
            )
            .returning(setlist_songs.c.song_id, setlist_songs.c.created_at)
        )
        .mappings()
        .first()
    )

    return {
        "song_id": row["song_id"],
        "setlist_id": setlist_id,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.put("/setlists/{setlist_id}/songs/{song_id}")
def update_song(
    setlist_id: int,
    song_id: int,
    payload: SetlistSongUpdateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    setlist = db.execute(select(setlists).where(setlists.c.setlist_id == setlist_id)).mappings().first()
    if not setlist:
        raise_app_error("NOT_FOUND", "Setlist not found", status_code=404)
    _ensure_band_member(setlist["band_id"], current_user, db)

    update_values = {}
    if payload.title is not None:
        update_values["song_title"] = payload.title
    if payload.artist is not None:
        update_values["artist_name"] = payload.artist
    if payload.duration_minutes is not None:
        update_values["duration_minutes"] = payload.duration_minutes
    if payload.order is not None:
        update_values["song_order"] = payload.order

    now = datetime.now(timezone.utc)
    if update_values:
        db.execute(
            update(setlist_songs)
            .where(setlist_songs.c.song_id == song_id)
            .values(**update_values)
        )

    return {"song_id": song_id, "updated_at": now.isoformat()}


@router.delete("/setlists/{setlist_id}/songs/{song_id}")
def delete_song(
    setlist_id: int,
    song_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    setlist = db.execute(select(setlists).where(setlists.c.setlist_id == setlist_id)).mappings().first()
    if not setlist:
        raise_app_error("NOT_FOUND", "Setlist not found", status_code=404)
    _ensure_band_member(setlist["band_id"], current_user, db)

    db.execute(delete(setlist_songs).where(setlist_songs.c.song_id == song_id))
    return {"message": "Song removed"}
