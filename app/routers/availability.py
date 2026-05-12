from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, delete, insert, select

from ..dependencies import get_current_user, get_db
from ..errors import raise_app_error
from ..tables import availability_calendar, band_members, bookings_contracts, gig_listings

router = APIRouter(prefix="/availability", tags=["availability"])


class AvailabilityCreateRequest(BaseModel):
    user_id: int
    date: datetime
    reason: str
    notes: str | None = None


@router.get("/{user_id}")
def get_availability(
    user_id: int,
    month: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if current_user["role"] != "ADMIN" and current_user["user_id"] != user_id:
        raise_app_error("FORBIDDEN", "User lacks permission", status_code=403)

    stmt = select(availability_calendar).where(availability_calendar.c.user_id == user_id)
    if date_from:
        stmt = stmt.where(availability_calendar.c.busy_date >= date_from)
    if date_to:
        stmt = stmt.where(availability_calendar.c.busy_date <= date_to)

    busy_rows = db.execute(stmt).mappings().all()

    band_ids = (
        db.execute(select(band_members.c.band_id).where(band_members.c.user_id == user_id))
        .scalars()
        .all()
    )
    booking_stmt = (
        select(
            gig_listings.c.gig_id,
            gig_listings.c.performance_date,
            gig_listings.c.gig_title,
        )
        .select_from(
            bookings_contracts.join(gig_listings, bookings_contracts.c.gig_id == gig_listings.c.gig_id)
        )
    )
    if band_ids:
        booking_stmt = booking_stmt.where(bookings_contracts.c.band_id.in_(band_ids))
    else:
        booking_stmt = booking_stmt.where(bookings_contracts.c.venue_owner_id == user_id)

    booked_rows = db.execute(booking_stmt).mappings().all()

    return {
        "user_id": user_id,
        "busy_dates": [
            {
                "date": (
                    row["busy_date"].isoformat() if row.get("busy_date") else None
                ),
                "reason": row["reason"],
            }
            for row in busy_rows
        ],
        "booked_gigs": [
            {
                "gig_id": row["gig_id"],
                "date": (
                    row["performance_date"].isoformat()
                    if row.get("performance_date")
                    else None
                ),
                "title": row["gig_title"],
            }
            for row in booked_rows
        ],
    }


@router.post("", status_code=201)
def block_date(
    payload: AvailabilityCreateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if current_user["role"] != "ADMIN" and current_user["user_id"] != payload.user_id:
        raise_app_error("FORBIDDEN", "User can block own dates only", status_code=403)

    row = (
        db.execute(
            insert(availability_calendar)
            .values(
                user_id=payload.user_id,
                busy_date=payload.date,
                reason=payload.reason,
            )
            .returning(
                availability_calendar.c.availability_id,
                availability_calendar.c.busy_date,
                availability_calendar.c.created_at,
            )
        )
        .mappings()
        .first()
    )

    return {
        "availability_id": row["availability_id"],
        "date": row["busy_date"].isoformat() if row.get("busy_date") else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.delete("/{availability_id}")
def delete_availability(
    availability_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    row = (
        db.execute(
            select(availability_calendar.c.user_id).where(
                availability_calendar.c.availability_id == availability_id
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise_app_error("NOT_FOUND", "Availability entry not found", status_code=404)
    if current_user["role"] != "ADMIN" and row["user_id"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "User can unblock own dates only", status_code=403)

    db.execute(
        delete(availability_calendar).where(availability_calendar.c.availability_id == availability_id)
    )
    return {"message": "Date unblocked"}
