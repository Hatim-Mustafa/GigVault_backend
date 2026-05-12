from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select, update

from ..dependencies import get_current_user, get_db
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..tables import band_members, bands, bookings_contracts, gig_listings, payments, users

router = APIRouter(prefix="/bookings", tags=["bookings"])


class BookingSignRequest(BaseModel):
    signed_by_role: Literal["MUSICIAN", "VENUE_OWNER"]


@router.get("")
def list_bookings(
    user_id: int,
    status: str | None = None,
    page: int | None = None,
    limit: int | None = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if current_user["role"] != "ADMIN" and current_user["user_id"] != user_id:
        raise_app_error("FORBIDDEN", "User lacks permission", status_code=403)

    band_ids = (
        db.execute(select(band_members.c.band_id).where(band_members.c.user_id == user_id))
        .scalars()
        .all()
    )

    stmt = (
        select(
            bookings_contracts.c.booking_id,
            bookings_contracts.c.gig_id,
            bookings_contracts.c.band_id,
            bookings_contracts.c.contract_status,
            bookings_contracts.c.agreed_fee,
            gig_listings.c.gig_title.label("gig_title"),
            bands.c.band_name.label("band_name"),
            gig_listings.c.performance_date,
        )
        .select_from(
            bookings_contracts.join(gig_listings, bookings_contracts.c.gig_id == gig_listings.c.gig_id)
            .join(bands, bookings_contracts.c.band_id == bands.c.band_id)
        )
    )

    if band_ids:
        stmt = stmt.where(
            or_(
                bookings_contracts.c.venue_owner_id == user_id,
                bookings_contracts.c.band_id.in_(band_ids),
            )
        )
    else:
        stmt = stmt.where(bookings_contracts.c.venue_owner_id == user_id)

    if status:
        stmt = stmt.where(bookings_contracts.c.contract_status == status)

    page, limit, offset = get_pagination(page, limit)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).mappings().all()

    return {
        "total": total,
        "page": page,
        "bookings": [
            {
                "booking_id": row["booking_id"],
                "gig_id": row["gig_id"],
                "gig_title": row["gig_title"],
                "band_id": row["band_id"],
                "band_name": row["band_name"],
                "date": (
                    row["performance_date"].isoformat()
                    if row.get("performance_date")
                    else None
                ),
                "pay_total": float(row["agreed_fee"]),
                "status": row["contract_status"],
            }
            for row in rows
        ],
    }


@router.get("/{booking_id}")
def get_booking(booking_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    row = (
        db.execute(
            select(
                bookings_contracts,
                gig_listings.c.gig_title.label("gig_title"),
                gig_listings.c.performance_date,
                gig_listings.c.venue_name,
                gig_listings.c.location_city,
                gig_listings.c.location_zip_code,
                bands.c.band_name.label("band_name"),
                users.c.first_name,
                users.c.last_name,
            )
            .select_from(
                bookings_contracts.join(gig_listings, bookings_contracts.c.gig_id == gig_listings.c.gig_id)
                .join(bands, bookings_contracts.c.band_id == bands.c.band_id)
                .join(users, bookings_contracts.c.venue_owner_id == users.c.user_id)
            )
            .where(bookings_contracts.c.booking_id == booking_id)
        )
        .mappings()
        .first()
    )
    if not row:
        raise_app_error("NOT_FOUND", "Booking not found", status_code=404)

    band_ids = (
        db.execute(select(band_members.c.band_id).where(band_members.c.user_id == current_user["user_id"]))
        .scalars()
        .all()
    )
    if current_user["role"] != "ADMIN" and row["venue_owner_id"] != current_user["user_id"]:
        if row["band_id"] not in band_ids:
            raise_app_error("FORBIDDEN", "User lacks permission", status_code=403)

    payment_rows = (
        db.execute(
            select(payments.c.payment_type, payments.c.amount, payments.c.payment_status).where(
                payments.c.booking_id == booking_id
            )
        )
        .mappings()
        .all()
    )

    deposit = next((p for p in payment_rows if p["payment_type"] == "DEPOSIT"), None)
    final_payment = next((p for p in payment_rows if p["payment_type"] == "FINAL"), None)

    return {
        "booking_id": row["booking_id"],
        "gig_id": row["gig_id"],
        "gig_details": {
            "title": row["gig_title"],
            "date": (
                row["performance_date"].isoformat() if row.get("performance_date") else None
            ),
            "location": {
                "venue": row["venue_name"],
                "city": row["location_city"],
                "zip_code": row["location_zip_code"],
            },
        },
        "band_id": row["band_id"],
        "band_name": row["band_name"],
        "venue_owner_id": row["venue_owner_id"],
        "venue_owner_name": f"{row['first_name']} {row['last_name']}".strip(),
        "pay_total": float(row["agreed_fee"]),
        "deposit_amount": float(row["deposit_amount"] or 0),
        "status": row["contract_status"],
        "deposit_status": row["deposit_status"],
        "contract_date": (
            row["contract_date"].isoformat() if row.get("contract_date") else None
        ),
        "signed_at": row["signed_at"].isoformat() if row.get("signed_at") else None,
        "completed_at": row["completed_at"].isoformat() if row.get("completed_at") else None,
    }


@router.put("/{booking_id}/sign")
def sign_booking(
    booking_id: int,
    payload: BookingSignRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    booking = db.execute(select(bookings_contracts).where(bookings_contracts.c.booking_id == booking_id)).mappings().first()
    if not booking:
        raise_app_error("NOT_FOUND", "Booking not found", status_code=404)

    band_ids = (
        db.execute(select(band_members.c.band_id).where(band_members.c.user_id == current_user["user_id"]))
        .scalars()
        .all()
    )

    if payload.signed_by_role == "MUSICIAN":
        if booking["band_id"] not in band_ids and current_user["role"] != "ADMIN":
            raise_app_error("FORBIDDEN", "Band member only", status_code=403)
        update_values = {"signed_at": datetime.now(timezone.utc)}
    else:
        if booking["venue_owner_id"] != current_user["user_id"] and current_user["role"] != "ADMIN":
            raise_app_error("FORBIDDEN", "Venue owner only", status_code=403)
        update_values = {"signed_at": datetime.now(timezone.utc)}

    db.execute(update(bookings_contracts).where(bookings_contracts.c.booking_id == booking_id).values(**update_values))

    db.execute(
        update(bookings_contracts)
        .where(bookings_contracts.c.booking_id == booking_id)
        .values(contract_status="Active")
    )

    return {
        "booking_id": booking_id,
        "signed_at": update_values[next(iter(update_values))].isoformat(),
        "status": "Active",
    }
