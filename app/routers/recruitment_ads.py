from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, delete, func, insert, or_, select, update

from ..dependencies import get_current_user, get_db, require_role
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..tables import recruitment_ad_genres, recruitment_ad_instruments, recruitment_ads, user_instruments, users

router = APIRouter(prefix="/recruitment-ads", tags=["recruitment_ads"])


class RecruitmentAdCreateRequest(BaseModel):
    title: str
    description: str | None = None
    instruments_needed: list[str]
    genres: list[str] | None = None
    city: str


class RecruitmentAdUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    instruments_needed: list[str] | None = None
    status: str | None = None


@router.get("/browse")
def browse_ads(
    instrument: str | None = None,
    genre: str | None = None,
    city: str | None = None,
    search: str | None = None,
    sort_by: str | None = "newest",
    page: int | None = None,
    limit: int | None = None,
    db=Depends(get_db),
):
    page, limit, offset = get_pagination(page, limit)

    stmt = (
        select(
            recruitment_ads.c.ad_id,
            recruitment_ads.c.title,
            users.c.name.label("posted_by"),
            recruitment_ads.c.city,
            recruitment_ads.c.posted_at,
        )
        .select_from(recruitment_ads.join(users, recruitment_ads.c.posted_by == users.c.user_id))
    )

    if instrument:
        stmt = stmt.select_from(
            recruitment_ads.join(
                recruitment_ad_instruments, recruitment_ads.c.ad_id == recruitment_ad_instruments.c.ad_id
            ).join(users, recruitment_ads.c.posted_by == users.c.user_id)
        ).where(recruitment_ad_instruments.c.instrument == instrument)

    if genre:
        stmt = stmt.select_from(
            recruitment_ads.join(
                recruitment_ad_genres, recruitment_ads.c.ad_id == recruitment_ad_genres.c.ad_id
            ).join(users, recruitment_ads.c.posted_by == users.c.user_id)
        ).where(recruitment_ad_genres.c.genre == genre)

    filters = []
    if city:
        filters.append(recruitment_ads.c.city == city)
    if search:
        filters.append(
            or_(
                recruitment_ads.c.title.ilike(f"%{search}%"),
                recruitment_ads.c.description.ilike(f"%{search}%"),
            )
        )
    if filters:
        stmt = stmt.where(and_(*filters))

    if sort_by == "oldest":
        stmt = stmt.order_by(recruitment_ads.c.posted_at.asc())
    else:
        stmt = stmt.order_by(recruitment_ads.c.posted_at.desc())

    count_stmt = select(func.count(func.distinct(recruitment_ads.c.ad_id))).select_from(recruitment_ads)
    if instrument:
        count_stmt = count_stmt.select_from(
            recruitment_ads.join(
                recruitment_ad_instruments, recruitment_ads.c.ad_id == recruitment_ad_instruments.c.ad_id
            )
        ).where(recruitment_ad_instruments.c.instrument == instrument)
    if genre:
        count_stmt = count_stmt.select_from(
            recruitment_ads.join(
                recruitment_ad_genres, recruitment_ads.c.ad_id == recruitment_ad_genres.c.ad_id
            )
        ).where(recruitment_ad_genres.c.genre == genre)
    if filters:
        count_stmt = count_stmt.where(and_(*filters))

    total = db.execute(count_stmt).scalar_one() or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).mappings().all()

    ad_ids = [row["ad_id"] for row in rows]
    instruments_map = {}
    genres_map = {}
    if ad_ids:
        instr_rows = (
            db.execute(
                select(recruitment_ad_instruments.c.ad_id, recruitment_ad_instruments.c.instrument).where(
                    recruitment_ad_instruments.c.ad_id.in_(ad_ids)
                )
            )
            .mappings()
            .all()
        )
        for row in instr_rows:
            instruments_map.setdefault(row["ad_id"], []).append(row["instrument"])

        genre_rows = (
            db.execute(
                select(recruitment_ad_genres.c.ad_id, recruitment_ad_genres.c.genre).where(
                    recruitment_ad_genres.c.ad_id.in_(ad_ids)
                )
            )
            .mappings()
            .all()
        )
        for row in genre_rows:
            genres_map.setdefault(row["ad_id"], []).append(row["genre"])

    return {
        "total": total,
        "page": page,
        "ads": [
            {
                "ad_id": row["ad_id"],
                "title": row["title"],
                "posted_by": row["posted_by"],
                "instruments_needed": instruments_map.get(row["ad_id"], []),
                "genres": genres_map.get(row["ad_id"], []),
                "city": row["city"],
                "posted_at": row["posted_at"].isoformat() if row.get("posted_at") else None,
            }
            for row in rows
        ],
    }


@router.get("/{ad_id}")
def get_ad(ad_id: int, db=Depends(get_db)):
    ad = (
        db.execute(
            select(recruitment_ads, users.c.name.label("posted_by"))
            .select_from(recruitment_ads.join(users, recruitment_ads.c.posted_by == users.c.user_id))
            .where(recruitment_ads.c.ad_id == ad_id)
        )
        .mappings()
        .first()
    )
    if not ad:
        raise_app_error("NOT_FOUND", "Recruitment ad not found", status_code=404)

    instruments = (
        db.execute(
            select(recruitment_ad_instruments.c.instrument).where(
                recruitment_ad_instruments.c.ad_id == ad_id
            )
        )
        .scalars()
        .all()
    )
    genres = (
        db.execute(select(recruitment_ad_genres.c.genre).where(recruitment_ad_genres.c.ad_id == ad_id))
        .scalars()
        .all()
    )

    return {
        "ad_id": ad["ad_id"],
        "title": ad["title"],
        "description": ad["description"],
        "posted_by": {
            "user_id": ad["posted_by"],
            "name": ad["posted_by"],
            "instruments": instruments,
        },
        "instruments_needed": instruments,
        "genres": genres,
        "city": ad["city"],
        "posted_at": ad["posted_at"].isoformat() if ad.get("posted_at") else None,
    }


@router.post("", status_code=201, dependencies=[Depends(require_role("MUSICIAN", "ADMIN"))])
def create_ad(
    payload: RecruitmentAdCreateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    row = (
        db.execute(
            insert(recruitment_ads)
            .values(
                title=payload.title,
                description=payload.description,
                posted_by=current_user["user_id"],
                city=payload.city,
                status="ACTIVE",
            )
            .returning(recruitment_ads.c.ad_id, recruitment_ads.c.posted_at)
        )
        .mappings()
        .first()
    )

    for instrument in payload.instruments_needed:
        db.execute(
            insert(recruitment_ad_instruments).values(ad_id=row["ad_id"], instrument=instrument)
        )
    if payload.genres:
        for genre in payload.genres:
            db.execute(insert(recruitment_ad_genres).values(ad_id=row["ad_id"], genre=genre))

    return {
        "ad_id": row["ad_id"],
        "created_at": row["posted_at"].isoformat() if row.get("posted_at") else None,
    }


@router.put("/{ad_id}")
def update_ad(
    ad_id: int,
    payload: RecruitmentAdUpdateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ad = db.execute(select(recruitment_ads).where(recruitment_ads.c.ad_id == ad_id)).mappings().first()
    if not ad:
        raise_app_error("NOT_FOUND", "Recruitment ad not found", status_code=404)
    if current_user["role"] != "ADMIN" and ad["posted_by"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Ad creator only", status_code=403)

    update_values = {}
    if payload.title is not None:
        update_values["title"] = payload.title
    if payload.description is not None:
        update_values["description"] = payload.description
    if payload.status is not None:
        update_values["status"] = payload.status

    now = datetime.now(timezone.utc)
    if update_values:
        update_values["updated_at"] = now
        db.execute(update(recruitment_ads).where(recruitment_ads.c.ad_id == ad_id).values(**update_values))

    if payload.instruments_needed is not None:
        db.execute(delete(recruitment_ad_instruments).where(recruitment_ad_instruments.c.ad_id == ad_id))
        for instrument in payload.instruments_needed:
            db.execute(
                insert(recruitment_ad_instruments).values(ad_id=ad_id, instrument=instrument)
            )

    return {"ad_id": ad_id, "updated_at": now.isoformat()}


@router.delete("/{ad_id}")
def delete_ad(ad_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    ad = db.execute(select(recruitment_ads).where(recruitment_ads.c.ad_id == ad_id)).mappings().first()
    if not ad:
        raise_app_error("NOT_FOUND", "Recruitment ad not found", status_code=404)
    if current_user["role"] != "ADMIN" and ad["posted_by"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Ad creator only", status_code=403)

    db.execute(delete(recruitment_ad_instruments).where(recruitment_ad_instruments.c.ad_id == ad_id))
    db.execute(delete(recruitment_ad_genres).where(recruitment_ad_genres.c.ad_id == ad_id))
    db.execute(delete(recruitment_ads).where(recruitment_ads.c.ad_id == ad_id))

    return {"message": "Ad deleted"}
