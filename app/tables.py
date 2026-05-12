from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Boolean,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)

metadata = MetaData(schema="public")

users = Table(
    "users",
    metadata,
    Column("user_id", Integer, primary_key=True),
    Column("username", String(255), nullable=False, unique=True),
    Column("email", String(255), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("first_name", String(120), nullable=False),
    Column("last_name", String(120), nullable=False),
    Column("phone_number", String(30)),
    Column("role", String(20), nullable=False),
    Column("profile_picture_url", String(500)),
    Column("city", String(120)),
    Column("zip_code", String(20)),
    Column("bio", Text),
    Column("account_created_at", DateTime(timezone=True), server_default=text("NOW()")),
    Column("last_updated", DateTime(timezone=True), server_default=text("NOW()")),
    Column("is_active", Boolean, server_default=text("true")),
)

user_instruments = Table(
    "user_instruments",
    metadata,
    Column("user_instrument_id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.user_id"), nullable=False),
    Column("instrument", String(100), nullable=False),
    UniqueConstraint("user_id", "instrument", name="uq_user_instrument"),
)

bands = Table(
    "bands",
    metadata,
    Column("band_id", Integer, primary_key=True),
    Column("name", String(200), nullable=False),
    Column("description", Text),
    Column("created_by", Integer, ForeignKey("users.user_id"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), server_default=text("NOW()")),
    UniqueConstraint("created_by", "name", name="uq_band_owner_name"),
)

band_members = Table(
    "band_members",
    metadata,
    Column("member_id", Integer, primary_key=True),
    Column("band_id", Integer, ForeignKey("bands.band_id"), nullable=False),
    Column("user_id", Integer, ForeignKey("users.user_id"), nullable=False),
    Column("joined_at", DateTime(timezone=True), server_default=text("NOW()")),
    UniqueConstraint("band_id", "user_id", name="uq_band_member"),
)

band_genres = Table(
    "band_genres",
    metadata,
    Column("band_genre_id", Integer, primary_key=True),
    Column("band_id", Integer, ForeignKey("bands.band_id"), nullable=False),
    Column("genre", String(120), nullable=False),
    UniqueConstraint("band_id", "genre", name="uq_band_genre"),
)

gig_listings = Table(
    "gig_listings",
    metadata,
    Column("gig_id", Integer, primary_key=True),
    Column("title", String(200), nullable=False),
    Column("description", Text),
    Column("created_by", Integer, ForeignKey("users.user_id"), nullable=False),
    Column("event_date", DateTime(timezone=True), nullable=False),
    Column("end_time", DateTime(timezone=True), nullable=False),
    Column("city", String(120), nullable=False),
    Column("location_details", Text),
    Column("pay_amount", Numeric(12, 2), nullable=False),
    Column("requirements", Text),
    Column("status", String(20), nullable=False, server_default=text("'OPEN'")),
    Column("created_at", DateTime(timezone=True), server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), server_default=text("NOW()")),
)

gig_genres = Table(
    "gig_genres",
    metadata,
    Column("gig_genre_id", Integer, primary_key=True),
    Column("gig_id", Integer, ForeignKey("gig_listings.gig_id"), nullable=False),
    Column("genre", String(120), nullable=False),
    UniqueConstraint("gig_id", "genre", name="uq_gig_genre"),
)

applications = Table(
    "applications",
    metadata,
    Column("application_id", Integer, primary_key=True),
    Column("gig_id", Integer, ForeignKey("gig_listings.gig_id"), nullable=False),
    Column("band_id", Integer, ForeignKey("bands.band_id"), nullable=False),
    Column("status", String(20), nullable=False, server_default=text("'SUBMITTED'")),
    Column("created_at", DateTime(timezone=True), server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), server_default=text("NOW()")),
    UniqueConstraint("gig_id", "band_id", name="uq_application_once"),
)

bookings_contracts = Table(
    "bookings_contracts",
    metadata,
    Column("booking_id", Integer, primary_key=True),
    Column("gig_id", Integer, ForeignKey("gig_listings.gig_id"), nullable=False),
    Column("band_id", Integer, ForeignKey("bands.band_id"), nullable=False),
    Column("venue_owner_id", Integer, ForeignKey("users.user_id"), nullable=False),
    Column("pay_total", Numeric(12, 2), nullable=False),
    Column("deposit_amount", Numeric(12, 2)),
    Column("final_payment", Numeric(12, 2)),
    Column("status", String(20), nullable=False, server_default=text("'PENDING'")),
    Column("band_signed_at", DateTime(timezone=True)),
    Column("venue_signed_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), server_default=text("NOW()")),
)

payments = Table(
    "payments",
    metadata,
    Column("payment_id", Integer, primary_key=True),
    Column("booking_id", Integer, ForeignKey("bookings_contracts.booking_id"), nullable=False),
    Column("amount", Numeric(12, 2), nullable=False),
    Column("payment_type", String(20), nullable=False),
    Column("status", String(20), nullable=False, server_default=text("'PENDING'")),
    Column("due_date", DateTime(timezone=True)),
    Column("paid_date", DateTime(timezone=True)),
    Column("notes", Text),
    Column("created_at", DateTime(timezone=True), server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), server_default=text("NOW()")),
)

availability_calendar = Table(
    "availability_calendar",
    metadata,
    Column("availability_id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.user_id"), nullable=False),
    Column("date", DateTime(timezone=True), nullable=False),
    Column("reason", String(20), nullable=False),
    Column("notes", Text),
    Column("created_at", DateTime(timezone=True), server_default=text("NOW()")),
)

setlists = Table(
    "setlists",
    metadata,
    Column("setlist_id", Integer, primary_key=True),
    Column("band_id", Integer, ForeignKey("bands.band_id"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("gig_id", Integer, ForeignKey("gig_listings.gig_id")),
    Column("created_at", DateTime(timezone=True), server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), server_default=text("NOW()")),
)

setlist_songs = Table(
    "setlist_songs",
    metadata,
    Column("song_id", Integer, primary_key=True),
    Column("setlist_id", Integer, ForeignKey("setlists.setlist_id"), nullable=False),
    Column("title", String(200), nullable=False),
    Column("artist", String(200)),
    Column("duration_minutes", Numeric(6, 2), nullable=False),
    Column("order", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), server_default=text("NOW()")),
)

recruitment_ads = Table(
    "recruitment_ads",
    metadata,
    Column("ad_id", Integer, primary_key=True),
    Column("title", String(200), nullable=False),
    Column("description", Text),
    Column("posted_by", Integer, ForeignKey("users.user_id"), nullable=False),
    Column("city", String(120), nullable=False),
    Column("status", String(20), nullable=False, server_default=text("'ACTIVE'")),
    Column("posted_at", DateTime(timezone=True), server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), server_default=text("NOW()")),
)

recruitment_ad_instruments = Table(
    "recruitment_ad_instruments",
    metadata,
    Column("ad_instrument_id", Integer, primary_key=True),
    Column("ad_id", Integer, ForeignKey("recruitment_ads.ad_id"), nullable=False),
    Column("instrument", String(120), nullable=False),
    UniqueConstraint("ad_id", "instrument", name="uq_recruitment_instrument"),
)

recruitment_ad_genres = Table(
    "recruitment_ad_genres",
    metadata,
    Column("ad_genre_id", Integer, primary_key=True),
    Column("ad_id", Integer, ForeignKey("recruitment_ads.ad_id"), nullable=False),
    Column("genre", String(120), nullable=False),
    UniqueConstraint("ad_id", "genre", name="uq_recruitment_genre"),
)

reviews_disputes = Table(
    "reviews_disputes",
    metadata,
    Column("record_id", Integer, primary_key=True),
    Column("booking_id", Integer, ForeignKey("bookings_contracts.booking_id"), nullable=False),
    Column("reviewer_id", Integer, ForeignKey("users.user_id")),
    Column("reviewee_id", Integer, ForeignKey("users.user_id")),
    Column("rating", Integer),
    Column("comment", Text),
    Column("filed_by", Integer, ForeignKey("users.user_id")),
    Column("reason", String(50)),
    Column("description", Text),
    Column("evidence_urls", JSON),
    Column("type", String(20), nullable=False),
    Column("status", String(20)),
    Column("resolution", Text),
    Column("created_at", DateTime(timezone=True), server_default=text("NOW()")),
    Column("resolved_at", DateTime(timezone=True)),
)

refresh_tokens = Table(
    "refresh_tokens",
    metadata,
    Column("token_id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.user_id"), nullable=False),
    Column("token", String(500), nullable=False, unique=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), server_default=text("NOW()")),
)
