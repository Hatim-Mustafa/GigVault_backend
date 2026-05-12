from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, func, insert, select, update

from ..dependencies import get_current_user, get_db, require_role
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..tables import band_members, bookings_contracts, gig_listings, payments

router = APIRouter(prefix="/payments", tags=["payments"])


class PaymentCreateRequest(BaseModel):
    booking_id: int
    amount: float
    payment_type: str
    paid_date: datetime


class PaymentUpdateRequest(BaseModel):
    status: str
    notes: str | None = None


@router.get("")
def list_payments(
    user_id: int,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    booking_id: int | None = None,
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
            payments.c.payment_id,
            payments.c.booking_id,
            payments.c.amount,
            payments.c.payment_type,
            payments.c.status,
            payments.c.due_date,
            gig_listings.c.title.label("gig_title"),
        )
        .select_from(
            payments.join(bookings_contracts, payments.c.booking_id == bookings_contracts.c.booking_id)
            .join(gig_listings, bookings_contracts.c.gig_id == gig_listings.c.gig_id)
        )
    )

    if band_ids:
        stmt = stmt.where(
            (bookings_contracts.c.band_id.in_(band_ids))
            | (bookings_contracts.c.venue_owner_id == user_id)
        )
    else:
        stmt = stmt.where(bookings_contracts.c.venue_owner_id == user_id)

    if status:
        stmt = stmt.where(payments.c.status == status)
    if date_from:
        stmt = stmt.where(payments.c.due_date >= date_from)
    if date_to:
        stmt = stmt.where(payments.c.due_date <= date_to)
    if booking_id:
        stmt = stmt.where(payments.c.booking_id == booking_id)

    page, limit, offset = get_pagination(page, limit)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one() or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).mappings().all()

    return {
        "total": total,
        "page": page,
        "payments": [
            {
                "payment_id": row["payment_id"],
                "booking_id": row["booking_id"],
                "gig_title": row["gig_title"],
                "amount": float(row["amount"]),
                "payment_type": row["payment_type"],
                "status": row["status"],
                "due_date": row["due_date"].isoformat() if row.get("due_date") else None,
            }
            for row in rows
        ],
    }


@router.get("/{payment_id}")
def get_payment(payment_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    row = (
        db.execute(
            select(
                payments,
                bookings_contracts.c.gig_id,
                bookings_contracts.c.band_id,
                gig_listings.c.title.label("gig_title"),
            )
            .select_from(
                payments.join(bookings_contracts, payments.c.booking_id == bookings_contracts.c.booking_id)
                .join(gig_listings, bookings_contracts.c.gig_id == gig_listings.c.gig_id)
            )
            .where(payments.c.payment_id == payment_id)
        )
        .mappings()
        .first()
    )
    if not row:
        raise_app_error("NOT_FOUND", "Payment not found", status_code=404)

    band_ids = (
        db.execute(select(band_members.c.band_id).where(band_members.c.user_id == current_user["user_id"]))
        .scalars()
        .all()
    )
    if current_user["role"] != "ADMIN" and row["venue_owner_id"] != current_user["user_id"]:
        if row["band_id"] not in band_ids:
            raise_app_error("FORBIDDEN", "User lacks permission", status_code=403)

    return {
        "payment_id": row["payment_id"],
        "booking_id": row["booking_id"],
        "gig_id": row["gig_id"],
        "gig_title": row["gig_title"],
        "band_id": row["band_id"],
        "amount": float(row["amount"]),
        "payment_type": row["payment_type"],
        "status": row["status"],
        "due_date": row["due_date"].isoformat() if row.get("due_date") else None,
        "paid_date": row["paid_date"].isoformat() if row.get("paid_date") else None,
        "notes": row["notes"],
    }


@router.post("", status_code=201, dependencies=[Depends(require_role("VENUE_OWNER", "ADMIN"))])
def create_payment(
    payload: PaymentCreateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    booking = (
        db.execute(
            select(bookings_contracts).where(bookings_contracts.c.booking_id == payload.booking_id)
        )
        .mappings()
        .first()
    )
    if not booking:
        raise_app_error("NOT_FOUND", "Booking not found", status_code=404)
    if current_user["role"] != "ADMIN" and booking["venue_owner_id"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Venue owner only", status_code=403)
    if payload.amount <= 0:
        raise_app_error("VALIDATION_ERROR", "Amount must be > 0", status_code=400)

    row = (
        db.execute(
            insert(payments)
            .values(
                booking_id=payload.booking_id,
                amount=payload.amount,
                payment_type=payload.payment_type,
                paid_date=payload.paid_date,
                status="PAID",
            )
            .returning(payments.c.payment_id, payments.c.created_at)
        )
        .mappings()
        .first()
    )

    return {
        "payment_id": row["payment_id"],
        "booking_id": payload.booking_id,
        "status": "PAID",
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@router.put("/{payment_id}")
def update_payment(
    payment_id: int,
    payload: PaymentUpdateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    payment = (
        db.execute(
            select(payments, bookings_contracts.c.venue_owner_id)
            .select_from(
                payments.join(bookings_contracts, payments.c.booking_id == bookings_contracts.c.booking_id)
            )
            .where(payments.c.payment_id == payment_id)
        )
        .mappings()
        .first()
    )
    if not payment:
        raise_app_error("NOT_FOUND", "Payment not found", status_code=404)
    if current_user["role"] != "ADMIN" and payment["venue_owner_id"] != current_user["user_id"]:
        raise_app_error("FORBIDDEN", "Venue owner only", status_code=403)

    now = datetime.now(timezone.utc)
    db.execute(
        update(payments)
        .where(payments.c.payment_id == payment_id)
        .values(status=payload.status, notes=payload.notes, updated_at=now)
    )

    return {"payment_id": payment_id, "status": payload.status, "updated_at": now.isoformat()}
