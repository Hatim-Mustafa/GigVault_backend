from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, func, insert, select

from ..dependencies import get_current_user, get_db
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..tables import band_members, bookings_contracts, reviews_disputes, users

router = APIRouter(prefix="/disputes", tags=["disputes"])


class DisputeCreateRequest(BaseModel):
    booking_id: int
    reason: str
    description: str
    evidence_urls: list[str] | None = None


@router.post("", status_code=201)
def create_dispute(
    payload: DisputeCreateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    booking = db.execute(
        select(bookings_contracts).where(bookings_contracts.c.booking_id == payload.booking_id)
    ).mappings().first()
    if not booking:
        raise_app_error("NOT_FOUND", "Booking not found", status_code=404)

    band_ids = (
        db.execute(select(band_members.c.band_id).where(band_members.c.user_id == current_user["user_id"]))
        .scalars()
        .all()
    )
    is_venue_owner = booking["venue_owner_id"] == current_user["user_id"]
    is_band_member = booking["band_id"] in band_ids
    if current_user["role"] != "ADMIN" and not (is_venue_owner or is_band_member):
        raise_app_error("FORBIDDEN", "Booking parties only", status_code=403)

    row = (
        db.execute(
            insert(reviews_disputes)
            .values(
                booking_id=payload.booking_id,
                reviewer_id=current_user["user_id"],
                dispute_reason=payload.reason,
                review_text=payload.description,
                review_type="Dispute",
                status="Open",
            )
            .returning(reviews_disputes.c.review_id, reviews_disputes.c.created_at)
        )
        .mappings()
        .first()
    )

    return {
        "dispute_id": row["review_id"],
        "booking_id": payload.booking_id,
        "status": "Open",
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.get("/{dispute_id}")
def get_dispute(dispute_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    row = (
        db.execute(
            select(
                reviews_disputes.c.review_id,
                reviews_disputes.c.booking_id,
                reviews_disputes.c.reviewer_id,
                reviews_disputes.c.dispute_reason,
                reviews_disputes.c.review_text,
                reviews_disputes.c.status,
                reviews_disputes.c.admin_notes,
                reviews_disputes.c.created_at,
                reviews_disputes.c.resolved_at,
                users.c.first_name,
                users.c.last_name,
            )
            .select_from(
                reviews_disputes.join(users, reviews_disputes.c.reviewer_id == users.c.user_id)
            )
            .where(
                and_(
                    reviews_disputes.c.review_id == dispute_id,
                    reviews_disputes.c.review_type == "Dispute",
                )
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise_app_error("NOT_FOUND", "Dispute not found", status_code=404)

    return {
        "dispute_id": row["review_id"],
        "booking_id": row["booking_id"],
        "filed_by": {
            "user_id": row["reviewer_id"],
            "name": f"{row['first_name']} {row['last_name']}".strip(),
        },
        "reason": row["dispute_reason"],
        "description": row["review_text"],
        "status": row["status"],
        "resolution": row["admin_notes"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "resolved_at": row["resolved_at"].isoformat() if row.get("resolved_at") else None,
    }


@router.get("")
def list_disputes(
    user_id: int,
    status: str | None = None,
    page: int | None = None,
    limit: int | None = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if current_user["role"] != "ADMIN" and current_user["user_id"] != user_id:
        raise_app_error("FORBIDDEN", "User lacks permission", status_code=403)

    page, limit, offset = get_pagination(page, limit)

    stmt = select(
        reviews_disputes.c.review_id,
        reviews_disputes.c.booking_id,
        reviews_disputes.c.dispute_reason,
        reviews_disputes.c.status,
        reviews_disputes.c.created_at,
    ).where(reviews_disputes.c.review_type == "Dispute")

    if status:
        stmt = stmt.where(reviews_disputes.c.status == status)

    if current_user["role"] != "ADMIN":
        stmt = stmt.where(reviews_disputes.c.reviewer_id == user_id)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).mappings().all()

    return {
        "total": total,
        "disputes": [
            {
                "dispute_id": row["review_id"],
                "booking_id": row["booking_id"],
                "reason": row["dispute_reason"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
            for row in rows
        ],
    }
