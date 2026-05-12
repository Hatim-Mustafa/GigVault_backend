from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, delete, func, insert, select, update

from ..dependencies import get_current_user, get_db
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..tables import (
    applications,
    band_members,
    bands,
    bookings_contracts,
    gig_listings,
    payments,
    reviews_disputes,
    users,
)

router = APIRouter(prefix="/users", tags=["users"])


class UserUpdateRequest(BaseModel):
    name: str | None = None
    city: str | None = None
    bio: str | None = None
    profile_pic: str | None = None
    instruments: list[str] | None = None


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


@router.get("/{user_id}")
def get_user_profile(user_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    if current_user["role"] != "ADMIN" and current_user["user_id"] != user_id:
        raise_app_error("FORBIDDEN", "User lacks permission", status_code=403)

    user = db.execute(select(users).where(users.c.user_id == user_id)).mappings().first()
    if not user:
        raise_app_error("NOT_FOUND", "User not found", status_code=404)

    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": f"{user['first_name']} {user['last_name']}".strip(),
        "role": user["role"],
        "city": user.get("city"),
        "bio": user.get("bio"),
        "profile_pic": user.get("profile_picture_url"),
        "instruments": [],
        "created_at": (
            user["account_created_at"].isoformat()
            if user.get("account_created_at")
            else None
        ),
        "updated_at": user["last_updated"].isoformat() if user.get("last_updated") else None,
    }


@router.put("/{user_id}")
def update_user_profile(
    user_id: int,
    payload: UserUpdateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if current_user["user_id"] != user_id:
        raise_app_error("FORBIDDEN", "User can only update own profile", status_code=403)

    update_values = {}
    if payload.name is not None:
        first_name, last_name = _split_name(payload.name)
        update_values["first_name"] = first_name
        update_values["last_name"] = last_name
    if payload.city is not None:
        update_values["city"] = payload.city
    if payload.bio is not None:
        update_values["bio"] = payload.bio
    if payload.profile_pic is not None:
        update_values["profile_picture_url"] = payload.profile_pic

    now = datetime.now(timezone.utc)
    if update_values:
        update_values["last_updated"] = now
        db.execute(update(users).where(users.c.user_id == user_id).values(**update_values))

    return {
        "user_id": user_id,
        "updated_at": now.isoformat(),
        "message": "Profile updated successfully",
    }


@router.get("/{user_id}/dashboard")
def user_dashboard(user_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    if current_user["role"] != "ADMIN" and current_user["user_id"] != user_id:
        raise_app_error("FORBIDDEN", "User lacks permission", status_code=403)

    user = db.execute(select(users).where(users.c.user_id == user_id)).mappings().first()
    if not user:
        raise_app_error("NOT_FOUND", "User not found", status_code=404)

    band_ids = (
        db.execute(
            select(band_members.c.band_id)
            .where(band_members.c.user_id == user_id)
            .distinct()
        )
        .scalars()
        .all()
    )

    total_gigs_posted = 0
    total_gigs_played = 0
    if user["role"] == "VENUE_OWNER":
        total_gigs_posted = (
            db.execute(
                select(func.count()).select_from(gig_listings).where(
                    gig_listings.c.venue_owner_id == user_id
                )
            )
            .scalar_one()
            or 0
        )
    if user["role"] == "MUSICIAN" and band_ids:
        total_gigs_played = (
            db.execute(
                select(func.count())
                .select_from(bookings_contracts)
                .where(bookings_contracts.c.band_id.in_(band_ids))
            )
            .scalar_one()
            or 0
        )

    total_applications = 0
    if band_ids:
        total_applications = (
            db.execute(
                select(func.count())
                .select_from(applications)
                .where(applications.c.band_id.in_(band_ids))
            )
            .scalar_one()
            or 0
        )

    average_rating = (
        db.execute(
            select(func.avg(reviews_disputes.c.rating))
            .where(
                and_(
                    reviews_disputes.c.review_type == "Review",
                    reviews_disputes.c.reviewee_id == user_id,
                )
            )
        )
        .scalar_one()
    )

    pending_payments = 0.0
    if band_ids or user["role"] == "VENUE_OWNER":
        payments_stmt = select(func.coalesce(func.sum(payments.c.amount), 0.0)).select_from(
            payments.join(
                bookings_contracts,
                payments.c.booking_id == bookings_contracts.c.booking_id,
            )
        )
        if user["role"] == "VENUE_OWNER":
            payments_stmt = payments_stmt.where(bookings_contracts.c.venue_owner_id == user_id)
        if band_ids:
            payments_stmt = payments_stmt.where(bookings_contracts.c.band_id.in_(band_ids))
        payments_stmt = payments_stmt.where(payments.c.payment_status == "Pending")
        pending_payments = float(db.execute(payments_stmt).scalar_one() or 0.0)

    now = datetime.now(timezone.utc)
    upcoming_gigs = []
    if user["role"] == "VENUE_OWNER":
        stmt = (
            select(
                gig_listings.c.gig_id,
                gig_listings.c.gig_title,
                gig_listings.c.performance_date,
                gig_listings.c.offered_pay,
            )
            .where(
                and_(
                    gig_listings.c.venue_owner_id == user_id,
                    gig_listings.c.performance_date >= now,
                )
            )
            .order_by(gig_listings.c.performance_date.asc())
            .limit(5)
        )
        upcoming_gigs = db.execute(stmt).mappings().all()
    elif band_ids:
        stmt = (
            select(
                gig_listings.c.gig_id,
                gig_listings.c.gig_title,
                gig_listings.c.performance_date,
                gig_listings.c.offered_pay,
            )
            .select_from(
                bookings_contracts.join(
                    gig_listings,
                    bookings_contracts.c.gig_id == gig_listings.c.gig_id,
                )
            )
            .where(
                and_(
                    bookings_contracts.c.band_id.in_(band_ids),
                    gig_listings.c.performance_date >= now,
                )
            )
            .order_by(gig_listings.c.performance_date.asc())
            .limit(5)
        )
        upcoming_gigs = db.execute(stmt).mappings().all()

    pending_applications = []
    if user["role"] == "VENUE_OWNER":
        stmt = (
            select(
                applications.c.application_id,
                gig_listings.c.gig_title.label("gig_title"),
                bands.c.band_name.label("band_name"),
                applications.c.application_status,
            )
            .select_from(
                applications.join(gig_listings, applications.c.gig_id == gig_listings.c.gig_id)
                .join(bands, applications.c.band_id == bands.c.band_id)
            )
            .where(
                and_(
                    gig_listings.c.venue_owner_id == user_id,
                    applications.c.application_status == "Pending",
                )
            )
            .limit(5)
        )
        pending_applications = db.execute(stmt).mappings().all()
    elif band_ids:
        stmt = (
            select(
                applications.c.application_id,
                gig_listings.c.gig_title.label("gig_title"),
                bands.c.band_name.label("band_name"),
                applications.c.application_status,
            )
            .select_from(
                applications.join(gig_listings, applications.c.gig_id == gig_listings.c.gig_id)
                .join(bands, applications.c.band_id == bands.c.band_id)
            )
            .where(applications.c.band_id.in_(band_ids))
            .limit(5)
        )
        pending_applications = db.execute(stmt).mappings().all()

    pending_payments_list = []
    payments_list_stmt = (
        select(
            payments.c.payment_id,
            payments.c.booking_id,
            payments.c.amount,
            payments.c.payment_status,
        )
        .select_from(
            payments.join(
                bookings_contracts,
                payments.c.booking_id == bookings_contracts.c.booking_id,
            )
        )
        .where(payments.c.payment_status == "Pending")
        .limit(5)
    )
    if user["role"] == "VENUE_OWNER":
        payments_list_stmt = payments_list_stmt.where(
            bookings_contracts.c.venue_owner_id == user_id
        )
    if band_ids:
        payments_list_stmt = payments_list_stmt.where(bookings_contracts.c.band_id.in_(band_ids))
    pending_payments_list = db.execute(payments_list_stmt).mappings().all()

    return {
        "user_id": user["user_id"],
        "user_name": f"{user['first_name']} {user['last_name']}".strip(),
        "role": user["role"],
        "stats": {
            "total_gigs_posted": total_gigs_posted,
            "total_gigs_played": total_gigs_played,
            "total_applications": total_applications,
            "average_rating": float(average_rating or 0.0),
            "pending_payments": pending_payments,
        },
        "upcoming_gigs": [
            {
                "gig_id": row["gig_id"],
                "title": row["gig_title"],
                "date": (
                    row["performance_date"].isoformat()
                    if row.get("performance_date")
                    else None
                ),
                "pay": float(row["offered_pay"]),
            }
            for row in upcoming_gigs
        ],
        "pending_applications": [
            {
                "application_id": row["application_id"],
                "gig_title": row["gig_title"],
                "band_name": row["band_name"],
                "status": row["application_status"],
            }
            for row in pending_applications
        ],
        "pending_payments": [
            {
                "payment_id": row["payment_id"],
                "booking_id": row["booking_id"],
                "amount": float(row["amount"]),
                "status": row["payment_status"],
            }
            for row in pending_payments_list
        ],
    }
