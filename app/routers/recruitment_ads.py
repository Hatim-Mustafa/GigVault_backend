from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, delete, func, insert, or_, select, update

from ..dependencies import get_current_user, get_db, require_role
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..tables import recruitment_ads, users

router = APIRouter(prefix="/recruitment-ads", tags=["recruitment_ads"])


class RecruitmentAdCreateRequest(BaseModel):
    band_id: int
    title: str
    description: str | None = None
    instruments_needed: list[str]
    genres: list[str] | None = None
    city: str


class RecruitmentAdUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    instruments_needed: list[str] | None = None
    genres: list[str] | None = None
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
            recruitment_ads.c.recruitment_id,
            recruitment_ads.c.title,
            users.c.first_name,
            users.c.last_name,
            recruitment_ads.c.city,
            recruitment_ads.c.created_at,
            recruitment_ads.c.instruments_needed,
            recruitment_ads.c.genre,
        )
        .select_from(recruitment_ads.join(users, recruitment_ads.c.posted_by_user_id == users.c.user_id))
    )

    if instrument:
        stmt = stmt.where(recruitment_ads.c.instruments_needed.ilike(f"%{instrument}%"))

    if genre:
        stmt = stmt.where(recruitment_ads.c.genre.ilike(f"%{genre}%"))

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
        stmt = stmt.order_by(recruitment_ads.c.created_at.asc())
    else:
        stmt = stmt.order_by(recruitment_ads.c.created_at.desc())

    count_stmt = select(func.count(func.distinct(recruitment_ads.c.recruitment_id))).select_from(
        recruitment_ads
    )
    if instrument:
        count_stmt = count_stmt.where(recruitment_ads.c.instruments_needed.ilike(f"%{instrument}%"))
    if genre:
        count_stmt = count_stmt.where(recruitment_ads.c.genre.ilike(f"%{genre}%"))
    if filters:
        count_stmt = count_stmt.where(and_(*filters))

    total = db.execute(count_stmt).scalar_one() or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).mappings().all()

    return {
        "total": total,
        "page": page,
        "ads": [
            {
                "ad_id": row["recruitment_id"],
                "title": row["title"],
                "posted_by": f"{row['first_name']} {row['last_name']}".strip(),
                "instruments_needed": (
                    [s.strip() for s in row["instruments_needed"].split(",")]
                    if row.get("instruments_needed")
                    else []
                ),
                "genres": (
                    [s.strip() for s in row["genre"].split(",")]
                    if row.get("genre")
                    else []
                ),
                "city": row["city"],
                "posted_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
            for row in rows
        ],
    }


@router.get("/{ad_id}")
def get_ad(ad_id: int, db=Depends(get_db)):
    ad = (
        db.execute(
            select(recruitment_ads, users.c.first_name, users.c.last_name)
            .select_from(
                recruitment_ads.join(
                    users, recruitment_ads.c.posted_by_user_id == users.c.user_id
                )
            )
            .where(recruitment_ads.c.recruitment_id == ad_id)
        )
        .mappings()
        .first()
    )
    if not ad:
        raise_app_error("NOT_FOUND", "Recruitment ad not found", status_code=404)

    return {
        "ad_id": ad["recruitment_id"],
        "title": ad["title"],
        "description": ad["description"],
        "posted_by": {
            "user_id": ad["posted_by_user_id"],
            "name": f"{ad['first_name']} {ad['last_name']}".strip(),
        },
        "instruments_needed": (
            [s.strip() for s in ad["instruments_needed"].split(",")]
            if ad.get("instruments_needed")
            else []
        ),
        "genres": (
            [s.strip() for s in ad["genre"].split(",")]
            if ad.get("genre")
            else []
        ),
        "city": ad["city"],
        "posted_at": ad["created_at"].isoformat() if ad.get("created_at") else None,
    }


@router.post("", status_code=201, dependencies=[Depends(require_role("MUSICIAN", "ADMIN"))])
def create_ad(
    payload: RecruitmentAdCreateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    genre_value = ", ".join(payload.genres) if payload.genres else None
    instruments_value = ", ".join(payload.instruments_needed)

    row = (
        db.execute(
            insert(recruitment_ads)
            .values(
                band_id=payload.band_id,
                posted_by_user_id=current_user["user_id"],
                title=payload.title,
                description=payload.description,
                instruments_needed=instruments_value,
                genre=genre_value or "General",
                city=payload.city,
                ad_status="Active",
            )
            .returning(recruitment_ads.c.recruitment_id, recruitment_ads.c.created_at)
        )
        .mappings()
        .first()
    )

    return {
        "ad_id": row["recruitment_id"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.put("/{ad_id}")
def update_ad(
    ad_id: int,
    payload: RecruitmentAdUpdateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    ad = (
        db.execute(select(recruitment_ads).where(recruitment_ads.c.recruitment_id == ad_id))
        .mappings()
        .first()
    )
    if not ad:
        raise_app_error("NOT_FOUND", "Recruitment ad not found", status_code=404)
    if current_user["role"] != "ADMIN" and ad["posted_by_user_id"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Ad creator only", status_code=403)

    update_values = {}
    if payload.title is not None:
        update_values["title"] = payload.title
    if payload.description is not None:
        update_values["description"] = payload.description
    if payload.status is not None:
        update_values["ad_status"] = payload.status
    if payload.instruments_needed is not None:
        update_values["instruments_needed"] = ", ".join(payload.instruments_needed)
    if payload.genres is not None:
        update_values["genre"] = ", ".join(payload.genres) if payload.genres else None

    now = datetime.now(timezone.utc)
    if update_values:
        update_values["last_updated"] = now
        db.execute(
            update(recruitment_ads)
            .where(recruitment_ads.c.recruitment_id == ad_id)
            .values(**update_values)
        )

    return {"ad_id": ad_id, "updated_at": now.isoformat()}


@router.delete("/{ad_id}")
def delete_ad(ad_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    ad = (
        db.execute(select(recruitment_ads).where(recruitment_ads.c.recruitment_id == ad_id))
        .mappings()
        .first()
    )
    if not ad:
        raise_app_error("NOT_FOUND", "Recruitment ad not found", status_code=404)
    if current_user["role"] != "ADMIN" and ad["posted_by_user_id"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Ad creator only", status_code=403)

    db.execute(delete(recruitment_ads).where(recruitment_ads.c.recruitment_id == ad_id))

    return {"message": "Ad deleted"}
