from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, delete, func, insert, select, update

from ..dependencies import get_current_user, get_db, require_role
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..tables import band_members, bands, users

router = APIRouter(prefix="/bands", tags=["bands"])


class BandCreateRequest(BaseModel):
    name: str
    description: str | None = None
    genres: list[str] | None = None


class BandUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    genres: list[str] | None = None


class AddMemberRequest(BaseModel):
    user_id: int
    instruments: list[str] | None = None


@router.get("")
def list_bands(
    user_id: int | None = None,
    page: int | None = None,
    limit: int | None = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if current_user["role"] not in {"MUSICIAN", "ADMIN"}:
        raise_app_error("FORBIDDEN", "Musicians only", status_code=403)
    if user_id is None:
        user_id = current_user["user_id"]
    if current_user["role"] != "ADMIN" and user_id != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "User lacks permission", status_code=403)

    band_ids_subq = (
        select(bands.c.band_id)
        .where(bands.c.leader_id == user_id)
        .union(select(band_members.c.band_id).where(band_members.c.user_id == user_id))
    ).subquery()

    member_counts = (
        select(band_members.c.band_id, func.count().label("member_count"))
        .group_by(band_members.c.band_id)
        .subquery()
    )

    page, limit, offset = get_pagination(page, limit)

    stmt = (
        select(
            bands.c.band_id,
            bands.c.band_name,
            bands.c.bio,
            bands.c.genre,
            bands.c.created_at,
            func.coalesce(member_counts.c.member_count, 0).label("member_count"),
        )
        .select_from(
            bands.outerjoin(member_counts, bands.c.band_id == member_counts.c.band_id)
        )
        .where(bands.c.band_id.in_(select(band_ids_subq.c.band_id)))
        .order_by(bands.c.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    total = (
        db.execute(select(func.count()).select_from(band_ids_subq)).scalar_one() or 0
    )
    rows = db.execute(stmt).mappings().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "bands": [
            {
                "band_id": row["band_id"],
                "name": row["band_name"],
                "description": row["bio"],
                "genres": [row["genre"]] if row.get("genre") else [],
                "member_count": row["member_count"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
            for row in rows
        ],
    }


@router.post("", status_code=201, dependencies=[Depends(require_role("MUSICIAN", "ADMIN"))])
def create_band(payload: BandCreateRequest, current_user=Depends(get_current_user), db=Depends(get_db)):
    existing = (
        db.execute(
            select(bands.c.band_id).where(
                and_(
                    bands.c.leader_id == current_user["user_id"],
                    bands.c.band_name == payload.name,
                )
            )
        ).first()
    )
    if existing:
        raise_app_error("CONFLICT", "Band name already exists", status_code=409)

    genre_value = ", ".join(payload.genres) if payload.genres else None

    stmt = (
        insert(bands)
        .values(
            band_name=payload.name,
            bio=payload.description,
            leader_id=current_user["user_id"],
            genre=genre_value or "Unknown",
        )
        .returning(bands.c.band_id, bands.c.band_name, bands.c.created_at)
    )
    row = db.execute(stmt).mappings().first()

    db.execute(
        insert(band_members).values(
            band_id=row["band_id"],
            user_id=current_user["user_id"],
        )
    )

    return {
        "band_id": row["band_id"],
        "name": row["band_name"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.get("/{band_id}")
def get_band(band_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    band = db.execute(select(bands).where(bands.c.band_id == band_id)).mappings().first()
    if not band:
        raise_app_error("NOT_FOUND", "Band not found", status_code=404)

    member_rows = (
        db.execute(
            select(
                band_members.c.member_id,
                band_members.c.user_id,
                band_members.c.joined_date,
                band_members.c.instrument,
                users.c.first_name,
                users.c.last_name,
            )
            .select_from(
                band_members.join(users, band_members.c.user_id == users.c.user_id)
            )
            .where(band_members.c.band_id == band_id)
        )
        .mappings()
        .all()
    )
    return {
        "band_id": band["band_id"],
        "name": band["band_name"],
        "description": band["bio"],
        "genres": [band["genre"]] if band.get("genre") else [],
        "members": [
            {
                "member_id": row["member_id"],
                "user_id": row["user_id"],
                "name": f"{row['first_name']} {row['last_name']}".strip(),
                "instruments": [row["instrument"]] if row.get("instrument") else [],
                "joined_at": (
                    row["joined_date"].isoformat() if row.get("joined_date") else None
                ),
            }
            for row in member_rows
        ],
        "created_at": band["created_at"].isoformat() if band.get("created_at") else None,
        "created_by": band["leader_id"],
    }


@router.get("/{band_id}/members")
def list_band_members(band_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    band = db.execute(select(bands).where(bands.c.band_id == band_id)).mappings().first()
    if not band:
        raise_app_error("NOT_FOUND", "Band not found", status_code=404)

    member_rows = (
        db.execute(
            select(
                band_members.c.member_id,
                band_members.c.user_id,
                band_members.c.joined_date,
                band_members.c.instrument,
                users.c.first_name,
                users.c.last_name,
            )
            .select_from(
                band_members.join(users, band_members.c.user_id == users.c.user_id)
            )
            .where(band_members.c.band_id == band_id)
        )
        .mappings()
        .all()
    )
    return {
        "band_id": band_id,
        "members": [
            {
                "member_id": row["member_id"],
                "user_id": row["user_id"],
                "name": f"{row['first_name']} {row['last_name']}".strip(),
                "instruments": [row["instrument"]] if row.get("instrument") else [],
                "joined_at": (
                    row["joined_date"].isoformat() if row.get("joined_date") else None
                ),
            }
            for row in member_rows
        ],
    }


@router.put("/{band_id}")
def update_band(
    band_id: int,
    payload: BandUpdateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    band = db.execute(select(bands).where(bands.c.band_id == band_id)).mappings().first()
    if not band:
        raise_app_error("NOT_FOUND", "Band not found", status_code=404)
    if current_user["role"] != "ADMIN" and band["leader_id"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Band creator only", status_code=403)

    update_values = {}
    if payload.name is not None:
        update_values["band_name"] = payload.name
    if payload.description is not None:
        update_values["bio"] = payload.description
    if payload.genres is not None:
        update_values["genre"] = ", ".join(payload.genres) if payload.genres else None

    now = datetime.now(timezone.utc)
    if update_values:
        update_values["last_updated"] = now
        db.execute(update(bands).where(bands.c.band_id == band_id).values(**update_values))

    return {"band_id": band_id, "updated_at": now.isoformat()}


@router.post("/{band_id}/members", status_code=201)
def add_band_member(
    band_id: int,
    payload: AddMemberRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    band = db.execute(select(bands).where(bands.c.band_id == band_id)).mappings().first()
    if not band:
        raise_app_error("NOT_FOUND", "Band not found", status_code=404)
    if current_user["role"] != "ADMIN" and band["leader_id"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Band creator only", status_code=403)

    user = db.execute(select(users.c.user_id).where(users.c.user_id == payload.user_id)).first()
    if not user:
        raise_app_error("NOT_FOUND", "User not found", status_code=404)

    existing = (
        db.execute(
            select(band_members.c.member_id).where(
                and_(band_members.c.band_id == band_id, band_members.c.user_id == payload.user_id)
            )
        ).first()
    )
    if existing:
        raise_app_error("CONFLICT", "User is already a member", status_code=409)

    row = (
        db.execute(
            insert(band_members)
            .values(
                band_id=band_id,
                user_id=payload.user_id,
                instrument=(payload.instruments[0] if payload.instruments else None),
            )
            .returning(band_members.c.member_id)
        )
        .mappings()
        .first()
    )

    return {
        "member_id": row["member_id"],
        "band_id": band_id,
        "user_id": payload.user_id,
    }


@router.delete("/{band_id}/members/{member_id}")
def remove_band_member(
    band_id: int,
    member_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    band = db.execute(select(bands).where(bands.c.band_id == band_id)).mappings().first()
    if not band:
        raise_app_error("NOT_FOUND", "Band not found", status_code=404)
    if current_user["role"] != "ADMIN" and band["leader_id"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Band creator only", status_code=403)

    result = db.execute(
        delete(band_members).where(
            and_(band_members.c.band_id == band_id, band_members.c.user_id == member_id)
        )
    )
    if result.rowcount == 0:
        raise_app_error("NOT_FOUND", "Member not found", status_code=404)

    return {"message": "Member removed"}
