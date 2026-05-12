from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, func, insert, select, update

from ..dependencies import get_current_user, get_db, require_role
from ..errors import raise_app_error
from ..pagination import get_pagination
from ..tables import (
    applications,
    band_members,
    bands,
    bookings_contracts,
    gig_listings,
)

router = APIRouter(prefix="/applications", tags=["applications"])


class ApplicationCreateRequest(BaseModel):
    gig_id: int
    band_id: int


class ApplicationUpdateRequest(BaseModel):
    status: Literal["Accepted", "Rejected", "Shortlisted", "Withdrawn"]


@router.post("", status_code=201, dependencies=[Depends(require_role("MUSICIAN", "ADMIN"))])
def create_application(
    payload: ApplicationCreateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    gig = db.execute(
        select(gig_listings).where(gig_listings.c.gig_id == payload.gig_id)
    ).mappings().first()
    if not gig or str(gig.get("gig_status", "")).lower() != "open":
        raise_app_error("NOT_FOUND", "Gig not available", status_code=404)

    member = (
        db.execute(
            select(band_members.c.member_id).where(
                and_(
                    band_members.c.band_id == payload.band_id,
                    band_members.c.user_id == current_user["user_id"],
                )
            )
        ).first()
    )
    if not member and current_user["role"] != "ADMIN":
        raise_app_error("FORBIDDEN", "Must be a band member", status_code=403)

    existing = (
        db.execute(
            select(applications.c.application_id).where(
                and_(
                    applications.c.gig_id == payload.gig_id,
                    applications.c.band_id == payload.band_id,
                )
            )
        ).first()
    )
    if existing:
        raise_app_error("CONFLICT", "Application already exists", status_code=409)

    row = (
        db.execute(
            insert(applications)
            .values(
                gig_id=payload.gig_id,
                band_id=payload.band_id,
                application_status="Pending",
            )
            .returning(
                applications.c.application_id,
                applications.c.gig_id,
                applications.c.band_id,
                applications.c.application_status,
                applications.c.application_date,
            )
        )
        .mappings()
        .first()
    )

    return {
        "application_id": row["application_id"],
        "gig_id": row["gig_id"],
        "band_id": row["band_id"],
        "status": row["application_status"],
        "created_at": (
            row["application_date"].isoformat() if row.get("application_date") else None
        ),
    }


@router.get("/{application_id}")
def get_application(application_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    row = (
        db.execute(
            select(
                applications.c.application_id,
                applications.c.gig_id,
                applications.c.band_id,
                applications.c.application_status,
                applications.c.application_date,
                applications.c.last_updated,
                gig_listings.c.gig_title.label("gig_title"),
                bands.c.band_name.label("band_name"),
            )
            .select_from(
                applications.join(gig_listings, applications.c.gig_id == gig_listings.c.gig_id)
                .join(bands, applications.c.band_id == bands.c.band_id)
            )
            .where(applications.c.application_id == application_id)
        )
        .mappings()
        .first()
    )
    if not row:
        raise_app_error("NOT_FOUND", "Application not found", status_code=404)

    return {
        "application_id": row["application_id"],
        "gig_id": row["gig_id"],
        "gig_title": row["gig_title"],
        "band_id": row["band_id"],
        "band_name": row["band_name"],
        "status": row["application_status"],
        "applied_at": (
            row["application_date"].isoformat() if row.get("application_date") else None
        ),
        "updated_at": (
            row["last_updated"].isoformat() if row.get("last_updated") else None
        ),
    }


@router.get("")
def list_applications(
    gig_id: int | None = None,
    band_id: int | None = None,
    status: str | None = None,
    page: int | None = None,
    limit: int | None = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    page, limit, offset = get_pagination(page, limit)

    stmt = select(
        applications.c.application_id,
        applications.c.gig_id,
        applications.c.band_id,
        applications.c.application_status,
        gig_listings.c.gig_title.label("gig_title"),
        bands.c.band_name.label("band_name"),
    ).select_from(
        applications.join(gig_listings, applications.c.gig_id == gig_listings.c.gig_id)
        .join(bands, applications.c.band_id == bands.c.band_id)
    )

    if gig_id:
        gig = db.execute(select(gig_listings).where(gig_listings.c.gig_id == gig_id)).mappings().first()
        if not gig:
            raise_app_error("NOT_FOUND", "Gig not found", status_code=404)
        if current_user["role"] != "ADMIN" and gig["venue_owner_id"] != current_user["user_id"]:
            raise_app_error("FORBIDDEN", "Venue owner only", status_code=403)
        stmt = stmt.where(applications.c.gig_id == gig_id)

    if band_id:
        member = (
            db.execute(
                select(band_members.c.member_id).where(
                    and_(
                        band_members.c.band_id == band_id,
                        band_members.c.user_id == current_user["user_id"],
                    )
                )
            ).first()
        )
        if not member and current_user["role"] != "ADMIN":
            raise_app_error("FORBIDDEN", "Band member only", status_code=403)
        stmt = stmt.where(applications.c.band_id == band_id)

    if status:
        stmt = stmt.where(applications.c.application_status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one() or 0
    rows = db.execute(stmt.limit(limit).offset(offset)).mappings().all()

    return {
        "total": total,
        "page": page,
        "applications": [
            {
                "application_id": row["application_id"],
                "gig_id": row["gig_id"],
                "gig_title": row["gig_title"],
                "band_id": row["band_id"],
                "band_name": row["band_name"],
                "status": row["application_status"],
            }
            for row in rows
        ],
    }


@router.put("/{application_id}")
def update_application_status(
    application_id: int,
    payload: ApplicationUpdateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    row = (
        db.execute(
            select(
                applications,
                gig_listings.c.venue_owner_id,
                gig_listings.c.offered_pay,
                gig_listings.c.performance_date,
                gig_listings.c.performance_time,
            )
            .select_from(
                applications.join(gig_listings, applications.c.gig_id == gig_listings.c.gig_id)
            )
            .where(applications.c.application_id == application_id)
        )
        .mappings()
        .first()
    )
    if not row:
        raise_app_error("NOT_FOUND", "Application not found", status_code=404)

    if payload.status != "Withdrawn" and current_user["role"] != "ADMIN":
        if row["venue_owner_id"] != current_user["user_id"]:
            raise_app_error("FORBIDDEN", "Venue owner only", status_code=403)

    now = datetime.now(timezone.utc)
    db.execute(
        update(applications)
        .where(applications.c.application_id == application_id)
        .values(application_status=payload.status, last_updated=now)
    )

    if payload.status == "Accepted":
        db.execute(
            update(gig_listings)
            .where(gig_listings.c.gig_id == row["gig_id"])
            .values(gig_status="Booked", last_updated=now)
        )
        db.execute(
            update(applications)
            .where(
                and_(
                    applications.c.gig_id == row["gig_id"],
                    applications.c.application_id != application_id,
                )
            )
            .values(application_status="Rejected", last_updated=now)
        )
        db.execute(
            insert(bookings_contracts).values(
                gig_id=row["gig_id"],
                band_id=row["band_id"],
                venue_owner_id=row["venue_owner_id"],
                agreed_fee=row["offered_pay"],
                deposit_amount=0,
                deposit_status="Pending",
                contract_status="Active",
                performance_date=row["performance_date"],
                performance_time=row["performance_time"],
            )
        )

    return {
        "application_id": application_id,
        "status": payload.status,
        "updated_at": now.isoformat(),
    }


@router.put("/{application_id}/withdraw")
def withdraw_application(
    application_id: int,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    row = (
        db.execute(
            select(applications.c.band_id).where(applications.c.application_id == application_id)
        )
        .mappings()
        .first()
    )
    if not row:
        raise_app_error("NOT_FOUND", "Application not found", status_code=404)

    member = (
        db.execute(
            select(band_members.c.member_id).where(
                and_(
                    band_members.c.band_id == row["band_id"],
                    band_members.c.user_id == current_user["user_id"],
                )
            )
        ).first()
    )
    if not member and current_user["role"] != "ADMIN":
        raise_app_error("FORBIDDEN", "Application submitter only", status_code=403)

    now = datetime.now(timezone.utc)
    db.execute(
        update(applications)
        .where(applications.c.application_id == application_id)
        .values(application_status="Withdrawn", last_updated=now)
    )

    return {"message": "Application withdrawn"}
