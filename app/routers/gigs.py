from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, delete, func, insert, or_, select, update

from ..dependencies import get_current_user, get_db, require_role
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..tables import applications, gig_genres, gig_listings, users, bands

router = APIRouter(prefix="/gigs", tags=["gigs"])


class GigCreateRequest(BaseModel):
    title: str
    description: str | None = None
    date: datetime
    end_time: datetime
    city: str
    location_details: str | None = None
    genres: list[str] | None = None
    pay_amount: float
    requirements: str | None = None


class GigUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    date: datetime | None = None
    pay_amount: float | None = None
    genres: list[str] | None = None


@router.get("/browse")
def browse_gigs(
    city: str | None = None,
    genre: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    pay_min: float | None = None,
    pay_max: float | None = None,
    search: str | None = None,
    status: str | None = "OPEN",
    sort_by: str | None = "date",
    page: int | None = None,
    limit: int | None = None,
    db=Depends(get_db),
):
    page, limit, offset = get_pagination(page, limit)

    base = select(
        gig_listings.c.gig_id,
        gig_listings.c.title,
        users.c.name.label("venue_name"),
        gig_listings.c.event_date,
        gig_listings.c.city,
        gig_listings.c.pay_amount,
        gig_listings.c.status,
    ).select_from(gig_listings.join(users, gig_listings.c.created_by == users.c.user_id))

    if genre:
        base = base.select_from(
            gig_listings.join(gig_genres, gig_listings.c.gig_id == gig_genres.c.gig_id).join(
                users, gig_listings.c.created_by == users.c.user_id
            )
        )
        base = base.where(gig_genres.c.genre == genre)

    filters = []
    if city:
        filters.append(gig_listings.c.city == city)
    if date_from:
        filters.append(gig_listings.c.event_date >= date_from)
    if date_to:
        filters.append(gig_listings.c.event_date <= date_to)
    if pay_min is not None:
        filters.append(gig_listings.c.pay_amount >= pay_min)
    if pay_max is not None:
        filters.append(gig_listings.c.pay_amount <= pay_max)
    if search:
        filters.append(
            or_(
                gig_listings.c.title.ilike(f"%{search}%"),
                gig_listings.c.description.ilike(f"%{search}%"),
            )
        )
    if status:
        filters.append(gig_listings.c.status == status)

    if filters:
        base = base.where(and_(*filters))

    if sort_by == "pay":
        base = base.order_by(gig_listings.c.pay_amount.desc())
    elif sort_by == "newest":
        base = base.order_by(gig_listings.c.created_at.desc())
    else:
        base = base.order_by(gig_listings.c.event_date.asc())

    count_stmt = select(func.count(func.distinct(gig_listings.c.gig_id)))
    count_stmt = count_stmt.select_from(gig_listings)
    if genre:
        count_stmt = count_stmt.select_from(
            gig_listings.join(gig_genres, gig_listings.c.gig_id == gig_genres.c.gig_id)
        )
        count_stmt = count_stmt.where(gig_genres.c.genre == genre)
    if filters:
        count_stmt = count_stmt.where(and_(*filters))

    total = db.execute(count_stmt).scalar_one() or 0
    rows = db.execute(base.limit(limit).offset(offset)).mappings().all()

    gig_ids = [row["gig_id"] for row in rows]
    genres_map = {}
    if gig_ids:
        genre_rows = (
            db.execute(select(gig_genres.c.gig_id, gig_genres.c.genre).where(gig_genres.c.gig_id.in_(gig_ids)))
            .mappings()
            .all()
        )
        for row in genre_rows:
            genres_map.setdefault(row["gig_id"], []).append(row["genre"])

    return {
        "total": total,
        "page": page,
        "gigs": [
            {
                "gig_id": row["gig_id"],
                "title": row["title"],
                "venue_name": row["venue_name"],
                "date": row["event_date"].isoformat() if row.get("event_date") else None,
                "city": row["city"],
                "genres": genres_map.get(row["gig_id"], []),
                "pay": float(row["pay_amount"]),
                "status": row["status"],
            }
            for row in rows
        ],
    }


@router.get("/{gig_id}")
def get_gig(gig_id: int, db=Depends(get_db)):
    row = (
        db.execute(
            select(
                gig_listings,
                users.c.name.label("venue_name"),
                users.c.email.label("venue_contact"),
            )
            .select_from(gig_listings.join(users, gig_listings.c.created_by == users.c.user_id))
            .where(gig_listings.c.gig_id == gig_id)
        )
        .mappings()
        .first()
    )
    if not row:
        raise_app_error("NOT_FOUND", "Gig not found", status_code=404)

    genres = (
        db.execute(select(gig_genres.c.genre).where(gig_genres.c.gig_id == gig_id))
        .scalars()
        .all()
    )

    return {
        "gig_id": row["gig_id"],
        "title": row["title"],
        "description": row["description"],
        "venue_owner": {
            "user_id": row["created_by"],
            "name": row["venue_name"],
            "contact": row["venue_contact"],
        },
        "date": row["event_date"].isoformat() if row.get("event_date") else None,
        "end_time": row["end_time"].isoformat() if row.get("end_time") else None,
        "city": row["city"],
        "location_details": row["location_details"],
        "genres": genres,
        "pay_amount": float(row["pay_amount"]),
        "requirements": row["requirements"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.post("", status_code=201, dependencies=[Depends(require_role("VENUE_OWNER", "ADMIN"))])
def create_gig(payload: GigCreateRequest, current_user=Depends(get_current_user), db=Depends(get_db)):
    if payload.pay_amount < 0:
        raise_app_error("VALIDATION_ERROR", "Pay amount must be >= 0", status_code=400)
    if payload.date <= datetime.now(timezone.utc):
        raise_app_error("VALIDATION_ERROR", "Gig date must be in the future", status_code=400)

    row = (
        db.execute(
            insert(gig_listings)
            .values(
                title=payload.title,
                description=payload.description,
                created_by=current_user["user_id"],
                event_date=payload.date,
                end_time=payload.end_time,
                city=payload.city,
                location_details=payload.location_details,
                pay_amount=payload.pay_amount,
                requirements=payload.requirements,
                status="OPEN",
            )
            .returning(gig_listings.c.gig_id, gig_listings.c.created_at)
        )
        .mappings()
        .first()
    )

    if payload.genres:
        for genre in payload.genres:
            db.execute(insert(gig_genres).values(gig_id=row["gig_id"], genre=genre))

    return {
        "gig_id": row["gig_id"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.put("/{gig_id}")
def update_gig(
    gig_id: int,
    payload: GigUpdateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    gig = db.execute(select(gig_listings).where(gig_listings.c.gig_id == gig_id)).mappings().first()
    if not gig:
        raise_app_error("NOT_FOUND", "Gig not found", status_code=404)
    if current_user["role"] != "ADMIN" and gig["created_by"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Venue owner only", status_code=403)

    update_values = {}
    if payload.title is not None:
        update_values["title"] = payload.title
    if payload.description is not None:
        update_values["description"] = payload.description
    if payload.date is not None:
        update_values["event_date"] = payload.date
    if payload.pay_amount is not None:
        if payload.pay_amount < 0:
            raise_app_error("VALIDATION_ERROR", "Pay amount must be >= 0", status_code=400)
        update_values["pay_amount"] = payload.pay_amount

    if update_values:
        update_values["updated_at"] = datetime.now(timezone.utc)
        db.execute(update(gig_listings).where(gig_listings.c.gig_id == gig_id).values(**update_values))

    if payload.genres is not None:
        db.execute(delete(gig_genres).where(gig_genres.c.gig_id == gig_id))
        for genre in payload.genres:
            db.execute(insert(gig_genres).values(gig_id=gig_id, genre=genre))

    return {"gig_id": gig_id, "updated_at": update_values.get("updated_at").isoformat() if update_values else None}


@router.delete("/{gig_id}")
def delete_gig(gig_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    gig = db.execute(select(gig_listings).where(gig_listings.c.gig_id == gig_id)).mappings().first()
    if not gig:
        raise_app_error("NOT_FOUND", "Gig not found", status_code=404)
    if current_user["role"] != "ADMIN" and gig["created_by"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Venue owner only", status_code=403)

    db.execute(
        update(gig_listings)
        .where(gig_listings.c.gig_id == gig_id)
        .values(status="CANCELLED", updated_at=datetime.now(timezone.utc))
    )
    return {"message": "Gig deleted"}


@router.get("/{gig_id}/applications")
def list_gig_applications(
    gig_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    gig = db.execute(select(gig_listings).where(gig_listings.c.gig_id == gig_id)).mappings().first()
    if not gig:
        raise_app_error("NOT_FOUND", "Gig not found", status_code=404)
    if current_user["role"] != "ADMIN" and gig["created_by"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Venue owner only", status_code=403)

    rows = (
        db.execute(
            select(
                applications.c.application_id,
                applications.c.status,
                bands.c.band_id,
                bands.c.name.label("band_name"),
            )
            .select_from(applications.join(bands, applications.c.band_id == bands.c.band_id))
            .where(applications.c.gig_id == gig_id)
        )
        .mappings()
        .all()
    )

    return {
        "gig_id": gig_id,
        "applications": [
            {
                "application_id": row["application_id"],
                "band_id": row["band_id"],
                "band_name": row["band_name"],
                "status": row["status"],
            }
            for row in rows
        ],
    }
