from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select, update, delete

from ..dependencies import get_current_user, get_db, require_role
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..security import hash_password
from ..tables import (
    applications,
    bookings_contracts,
    gig_listings,
    payments,
    reviews_disputes,
    users,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("ADMIN"))])


class AdminUserUpdateRequest(BaseModel):
    status: str | None = None
    role: str | None = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class AdminDisputeUpdateRequest(BaseModel):
    status: str
    resolution: str | None = None


class AdminReviewUpdateRequest(BaseModel):
    status: str


@router.get("/dashboard")
def admin_dashboard(db=Depends(get_db)):
    total_users = db.execute(select(func.count()).select_from(users)).scalar_one() or 0
    total_musicians = (
        db.execute(select(func.count()).select_from(users).where(users.c.role == "MUSICIAN"))
        .scalar_one()
        or 0
    )
    total_venue_owners = (
        db.execute(select(func.count()).select_from(users).where(users.c.role == "VENUE_OWNER"))
        .scalar_one()
        or 0
    )
    active_gigs = (
        db.execute(
            select(func.count()).select_from(gig_listings).where(gig_listings.c.status == "OPEN")
        )
        .scalar_one()
        or 0
    )
    total_bookings = db.execute(select(func.count()).select_from(bookings_contracts)).scalar_one() or 0
    platform_revenue = (
        db.execute(
            select(func.coalesce(func.sum(payments.c.amount), 0.0)).where(payments.c.status == "PAID")
        )
        .scalar_one()
        or 0.0
    )
    pending_disputes = (
        db.execute(
            select(func.count()).select_from(reviews_disputes).where(
                and_(reviews_disputes.c.type == "DISPUTE", reviews_disputes.c.status == "OPEN")
            )
        )
        .scalar_one()
        or 0
    )

    today = datetime.now(timezone.utc).date()
    new_users_today = (
        db.execute(
            select(func.count()).select_from(users).where(func.date(users.c.created_at) == today)
        )
        .scalar_one()
        or 0
    )
    new_gigs_today = (
        db.execute(
            select(func.count())
            .select_from(gig_listings)
            .where(func.date(gig_listings.c.created_at) == today)
        )
        .scalar_one()
        or 0
    )
    new_bookings_today = (
        db.execute(
            select(func.count())
            .select_from(bookings_contracts)
            .where(func.date(bookings_contracts.c.created_at) == today)
        )
        .scalar_one()
        or 0
    )

    return {
        "stats": {
            "total_users": total_users,
            "total_musicians": total_musicians,
            "total_venue_owners": total_venue_owners,
            "active_gigs": active_gigs,
            "total_bookings": total_bookings,
            "platform_revenue": float(platform_revenue),
            "pending_disputes": pending_disputes,
        },
        "recent_activity": {
            "new_users_today": new_users_today,
            "new_gigs_today": new_gigs_today,
            "new_bookings_today": new_bookings_today,
        },
    }


@router.get("/users")
def list_users(
    role: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int | None = None,
    limit: int | None = None,
    db=Depends(get_db),
):
    page, limit, offset = get_pagination(page, limit)
    stmt = select(users.c.user_id, users.c.email, users.c.name, users.c.role, users.c.status, users.c.created_at)
    if role:
        stmt = stmt.where(users.c.role == role)
    if status:
        stmt = stmt.where(users.c.status == status)
    if search:
        stmt = stmt.where(users.c.email.ilike(f"%{search}%") | users.c.name.ilike(f"%{search}%"))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).mappings().all()

    return {
        "total": total,
        "users": [
            {
                "user_id": row["user_id"],
                "email": row["email"],
                "name": row["name"],
                "role": row["role"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
            for row in rows
        ],
    }


@router.put("/users/{user_id}")
def update_user(user_id: int, payload: AdminUserUpdateRequest, db=Depends(get_db)):
    update_values = {}
    if payload.status is not None:
        update_values["status"] = payload.status
    if payload.role is not None:
        update_values["role"] = payload.role

    if not update_values:
        raise_app_error("VALIDATION_ERROR", "No fields to update", status_code=400)

    now = datetime.now(timezone.utc)
    update_values["updated_at"] = now

    result = db.execute(
        update(users).where(users.c.user_id == user_id).values(**update_values)
    )
    if result.rowcount == 0:
        raise_app_error("NOT_FOUND", "User not found", status_code=404)

    return {"user_id": user_id, "status": update_values.get("status"), "updated_at": now.isoformat()}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, payload: AdminResetPasswordRequest, db=Depends(get_db)):
    password_hash = hash_password(payload.new_password)
    result = db.execute(
        update(users)
        .where(users.c.user_id == user_id)
        .values(password_hash=password_hash, updated_at=datetime.now(timezone.utc))
    )
    if result.rowcount == 0:
        raise_app_error("NOT_FOUND", "User not found", status_code=404)

    return {"message": "Password reset successfully"}


@router.get("/gigs")
def list_gigs(
    status: str | None = None,
    city: str | None = None,
    search: str | None = None,
    page: int | None = None,
    limit: int | None = None,
    db=Depends(get_db),
):
    page, limit, offset = get_pagination(page, limit)
    stmt = select(
        gig_listings.c.gig_id,
        gig_listings.c.title,
        gig_listings.c.status,
        gig_listings.c.event_date,
    )
    if status:
        stmt = stmt.where(gig_listings.c.status == status)
    if city:
        stmt = stmt.where(gig_listings.c.city == city)
    if search:
        stmt = stmt.where(gig_listings.c.title.ilike(f"%{search}%"))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).mappings().all()

    return {
        "total": total,
        "gigs": [
            {
                "gig_id": row["gig_id"],
                "title": row["title"],
                "status": row["status"],
                "date": row["event_date"].isoformat() if row.get("event_date") else None,
            }
            for row in rows
        ],
    }


@router.delete("/gigs/{gig_id}")
def delete_gig(gig_id: int, db=Depends(get_db)):
    result = db.execute(delete(gig_listings).where(gig_listings.c.gig_id == gig_id))
    if result.rowcount == 0:
        raise_app_error("NOT_FOUND", "Gig not found", status_code=404)
    return {"message": "Gig deleted"}


@router.get("/disputes")
def list_disputes(
    status: str | None = None,
    page: int | None = None,
    limit: int | None = None,
    db=Depends(get_db),
):
    page, limit, offset = get_pagination(page, limit)
    stmt = select(
        reviews_disputes.c.record_id,
        reviews_disputes.c.booking_id,
        reviews_disputes.c.reason,
        reviews_disputes.c.status,
        reviews_disputes.c.created_at,
    ).where(reviews_disputes.c.type == "DISPUTE")
    if status:
        stmt = stmt.where(reviews_disputes.c.status == status)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).mappings().all()

    return {
        "total": total,
        "disputes": [
            {
                "dispute_id": row["record_id"],
                "booking_id": row["booking_id"],
                "reason": row["reason"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
            for row in rows
        ],
    }


@router.put("/disputes/{dispute_id}")
def resolve_dispute(dispute_id: int, payload: AdminDisputeUpdateRequest, db=Depends(get_db)):
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(reviews_disputes)
        .where(reviews_disputes.c.record_id == dispute_id)
        .values(status=payload.status, resolution=payload.resolution, resolved_at=now)
    )
    if result.rowcount == 0:
        raise_app_error("NOT_FOUND", "Dispute not found", status_code=404)

    return {
        "dispute_id": dispute_id,
        "status": payload.status,
        "resolved_at": now.isoformat(),
    }


@router.get("/reviews")
def list_reviews(
    page: int | None = None,
    limit: int | None = None,
    db=Depends(get_db),
):
    page, limit, offset = get_pagination(page, limit)
    stmt = select(
        reviews_disputes.c.record_id,
        reviews_disputes.c.booking_id,
        reviews_disputes.c.rating,
        reviews_disputes.c.status,
        reviews_disputes.c.created_at,
    ).where(reviews_disputes.c.type == "REVIEW")

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).mappings().all()

    return {
        "total": total,
        "reviews": [
            {
                "review_id": row["record_id"],
                "booking_id": row["booking_id"],
                "rating": row["rating"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
            for row in rows
        ],
    }


@router.put("/reviews/{review_id}")
def moderate_review(review_id: int, payload: AdminReviewUpdateRequest, db=Depends(get_db)):
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(reviews_disputes)
        .where(reviews_disputes.c.record_id == review_id)
        .values(status=payload.status, resolved_at=now)
    )
    if result.rowcount == 0:
        raise_app_error("NOT_FOUND", "Review not found", status_code=404)

    return {"review_id": review_id, "status": payload.status}
