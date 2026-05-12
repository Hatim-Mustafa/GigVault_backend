from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, insert, select

from ..dependencies import get_current_user, get_db
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..tables import band_members, bands, bookings_contracts, reviews_disputes, users

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewCreateRequest(BaseModel):
    booking_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


@router.post("", status_code=201)
def create_review(
    payload: ReviewCreateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    booking = (
        db.execute(
            select(bookings_contracts, bands.c.created_by)
            .select_from(bookings_contracts.join(bands, bookings_contracts.c.band_id == bands.c.band_id))
            .where(bookings_contracts.c.booking_id == payload.booking_id)
        )
        .mappings()
        .first()
    )
    if not booking:
        raise_app_error("NOT_FOUND", "Booking not found", status_code=404)

    band_ids = (
        db.execute(
            select(band_members.c.band_id).where(band_members.c.user_id == current_user["user_id"])
        )
        .scalars()
        .all()
    )
    is_venue_owner = booking["venue_owner_id"] == current_user["user_id"]
    is_band_member = booking["band_id"] in band_ids
    if current_user["role"] != "ADMIN" and not (is_venue_owner or is_band_member):
        raise_app_error("FORBIDDEN", "Booking parties only", status_code=403)

    reviewer_id = current_user["user_id"]
    reviewee_id = booking["venue_owner_id"] if is_band_member else booking["created_by"]

    existing = (
        db.execute(
            select(reviews_disputes.c.record_id).where(
                and_(
                    reviews_disputes.c.booking_id == payload.booking_id,
                    reviews_disputes.c.reviewer_id == reviewer_id,
                    reviews_disputes.c.type == "REVIEW",
                )
            )
        ).first()
    )
    if existing:
        raise_app_error("CONFLICT", "Review already submitted", status_code=409)

    row = (
        db.execute(
            insert(reviews_disputes)
            .values(
                booking_id=payload.booking_id,
                reviewer_id=reviewer_id,
                reviewee_id=reviewee_id,
                rating=payload.rating,
                comment=payload.comment,
                type="REVIEW",
                status="PENDING",
            )
            .returning(reviews_disputes.c.record_id, reviews_disputes.c.created_at)
        )
        .mappings()
        .first()
    )

    return {
        "review_id": row["record_id"],
        "booking_id": payload.booking_id,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.get("/{review_id}")
def get_review(review_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    row = (
        db.execute(
            select(
                reviews_disputes.c.record_id,
                reviews_disputes.c.booking_id,
                reviews_disputes.c.reviewer_id,
                reviews_disputes.c.rating,
                reviews_disputes.c.comment,
                reviews_disputes.c.created_at,
                users.c.name,
            )
            .select_from(reviews_disputes.join(users, reviews_disputes.c.reviewer_id == users.c.user_id))
            .where(
                and_(
                    reviews_disputes.c.record_id == review_id,
                    reviews_disputes.c.type == "REVIEW",
                )
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise_app_error("NOT_FOUND", "Review not found", status_code=404)

    return {
        "review_id": row["record_id"],
        "booking_id": row["booking_id"],
        "reviewer": {"user_id": row["reviewer_id"], "name": row["name"]},
        "rating": row["rating"],
        "comment": row["comment"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.get("")
def list_reviews(
    user_id: int | None = None,
    author_id: int | None = None,
    page: int | None = None,
    limit: int | None = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    page, limit, offset = get_pagination(page, limit)

    stmt = select(
        reviews_disputes.c.record_id,
        reviews_disputes.c.reviewer_id,
        reviews_disputes.c.reviewee_id,
        reviews_disputes.c.rating,
        reviews_disputes.c.comment,
        reviews_disputes.c.created_at,
        users.c.name.label("reviewer_name"),
    ).select_from(reviews_disputes.join(users, reviews_disputes.c.reviewer_id == users.c.user_id))

    stmt = stmt.where(reviews_disputes.c.type == "REVIEW")
    if user_id:
        stmt = stmt.where(reviews_disputes.c.reviewee_id == user_id)
    if author_id:
        stmt = stmt.where(reviews_disputes.c.reviewer_id == author_id)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).mappings().all()

    return {
        "total": total,
        "page": page,
        "reviews": [
            {
                "review_id": row["record_id"],
                "reviewer_name": row["reviewer_name"],
                "rating": row["rating"],
                "comment": row["comment"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
            for row in rows
        ],
    }
